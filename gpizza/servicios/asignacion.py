"""CU-002 Asignar Repartidor a Pedido (RF-003): automática, con aceptación del repartidor, y manual
del gerente.

Criterio automático: repartidores de la sucursal activos, disponibles y con menos de 2 pedidos
(RN-011); gana el de menor carga y, si empatan, el que lleva más tiempo sin entregar. La base de
datos vuelve a revisar RN-011 al insertar (trg_asignacion_validar con FOR UPDATE).
"""
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import selectinload

from gpizza import reglas
from gpizza.extensiones import db
from gpizza.modelos import AsignacionEntrega, Empleado, Notificacion, Pedido
from gpizza.servicios.errores import mensaje_bd

VIVAS = ('PENDIENTE', 'CONFIRMADA')


def carga(id_repartidor: int) -> int:
    return db.session.scalar(select(func.count()).select_from(AsignacionEntrega).where(
        AsignacionEntrega.id_repartidor == id_repartidor, AsignacionEntrega.estado.in_(VIVAS)))


def candidatos(id_sucursal: int, excluir=()) -> list[tuple[Empleado, int]]:
    """Repartidores que pueden recibir un pedido, en orden de preferencia, con su carga actual."""
    viva = (select(func.count()).where(AsignacionEntrega.id_repartidor == Empleado.id_empleado,
                                       AsignacionEntrega.estado.in_(VIVAS)).correlate(Empleado).scalar_subquery())
    ultima_entrega = (select(func.max(AsignacionEntrega.fecha_hora_entrega))
                      .where(AsignacionEntrega.id_repartidor == Empleado.id_empleado)
                      .correlate(Empleado).scalar_subquery())
    consulta = (select(Empleado, viva.label('carga'))
                .where(Empleado.id_sucursal == id_sucursal, Empleado.puesto == 'Repartidor', Empleado.activo,
                       Empleado.disponible, ~Empleado.bloqueado, viva < reglas.MAX_PEDIDOS_ACTIVOS_REPARTIDOR)
                .order_by(viva, ultima_entrega.asc().nulls_first(), Empleado.id_empleado))
    if excluir:
        consulta = consulta.where(Empleado.id_empleado.not_in(excluir))
    return [(e, c) for e, c in db.session.execute(consulta)]


def asignacion_viva(id_pedido: int) -> AsignacionEntrega | None:
    return db.session.scalar(select(AsignacionEntrega).where(
        AsignacionEntrega.id_pedido == id_pedido, AsignacionEntrega.estado.in_(VIVAS)))


def asignar_automatico(pedido: Pedido) -> AsignacionEntrega | None:
    """Pasos 2 a 4 de CU-002. Si nadie puede recibirlo, avisa al gerente (FA-1) y el pedido espera."""
    if pedido.estado != 'Listo para Entrega' or asignacion_viva(pedido.id_pedido):
        return None
    # FA-2: no se le vuelve a ofrecer a quien ya lo dejó vencer.
    vencidos = db.session.scalars(select(AsignacionEntrega.id_repartidor).where(
        AsignacionEntrega.id_pedido == pedido.id_pedido, AsignacionEntrega.estado == 'EXPIRADA')).all()
    for repartidor, _ in candidatos(pedido.id_sucursal, excluir=vencidos):
        try:
            with db.session.begin_nested():  # si la BD rechaza a este repartidor, se prueba el siguiente
                asignacion = AsignacionEntrega(id_pedido=pedido.id_pedido, id_repartidor=repartidor.id_empleado,
                                               tipo='AUTOMATICA')
                db.session.add(asignacion)
            return asignacion
        except DBAPIError:
            continue
    _avisar_sin_repartidor(pedido)
    return None


def _avisar_sin_repartidor(pedido: Pedido) -> None:
    ya_avisado = db.session.scalar(select(Notificacion.id_notificacion).where(
        Notificacion.id_pedido == pedido.id_pedido, Notificacion.tipo_evento == 'SIN_REPARTIDOR',
        ~Notificacion.leida))
    if not ya_avisado:
        db.session.add(Notificacion(id_pedido=pedido.id_pedido, rol_destino='Gerente', tipo_evento='SIN_REPARTIDOR',
                                    mensaje=f'No hay repartidor disponible para el pedido {pedido.folio}; '
                                            'asígnalo manualmente cuando se libere uno.'))


def reasignar_pendientes() -> int:
    """Pedidos listos sin repartidor (porque nadie estaba libre o porque el asignado no aceptó a
    tiempo): se vuelven a intentar. La llama la revisión periódica (ciclo.revisar_tiempos)."""
    listos = db.session.scalars(select(Pedido).where(Pedido.estado == 'Listo para Entrega')).all()
    return sum(1 for p in listos if asignar_automatico(p))


def asignar_manual(id_pedido: int, id_sucursal: int, id_repartidor: int, id_gerente: int) -> str | None:
    """CU-002 FA-3: el gerente elige al repartidor (también para reasignar uno que no responde)."""
    pedido = db.session.get(Pedido, id_pedido, with_for_update=True)
    if pedido is None or pedido.id_sucursal != id_sucursal:
        return 'Ese pedido no existe en tu sucursal.'
    if pedido.estado != 'Listo para Entrega':
        db.session.rollback()
        return 'Solo se asignan pedidos "Listo para Entrega".'
    viva = asignacion_viva(id_pedido)
    if viva and viva.estado == 'CONFIRMADA':
        db.session.rollback()
        return 'El repartidor ya aceptó este pedido.'
    if viva:
        viva.estado = 'CANCELADA'
    db.session.add(AsignacionEntrega(id_pedido=id_pedido, id_repartidor=id_repartidor, tipo='MANUAL',
                                     id_gerente=id_gerente))
    return _guardar()


def aceptar(id_asignacion: int, id_repartidor: int) -> str | None:
    """CU-002 paso 5: el repartidor acepta; el trigger pone el pedido "En Camino" (paso 6)."""
    asignacion = db.session.get(AsignacionEntrega, id_asignacion, with_for_update=True)
    if asignacion is None or asignacion.id_repartidor != id_repartidor:
        return 'Esa entrega no está asignada a ti.'
    if asignacion.estado != 'PENDIENTE':
        db.session.rollback()
        return 'Esta asignación ya no está pendiente (venció o se reasignó).'
    asignacion.estado = 'CONFIRMADA'
    return _guardar()


def del_repartidor(id_repartidor: int) -> list[AsignacionEntrega]:
    """Entregas activas del repartidor (boceto 9), primero las que ya va entregando."""
    return db.session.scalars(
        select(AsignacionEntrega).options(selectinload(AsignacionEntrega.pedido).selectinload(Pedido.detalles))
        .where(AsignacionEntrega.id_repartidor == id_repartidor, AsignacionEntrega.estado.in_(VIVAS))
        .order_by(AsignacionEntrega.estado.desc(), AsignacionEntrega.fecha_asignacion)).all()


def cambiar_disponibilidad(id_repartidor: int, disponible: bool) -> None:
    db.session.get(Empleado, id_repartidor).disponible = disponible
    db.session.commit()


def _guardar() -> str | None:
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return mensaje_bd(error)
    return None
