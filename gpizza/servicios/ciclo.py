"""Ciclo de vida del pedido después de confirmarse (RF-004): listo para entrega, cancelaciones de
acuerdo mutuo (RN-005), revisión periódica de tiempos (RN-006, RN-014, CU-002 FA-2) y búsqueda para
el seguimiento (CU-003).

Máquina de estados (la hace cumplir trg_pedido_cambio en la BD):
  Por Confirmar → En Preparación → Listo para Entrega → En Camino → Entregado
  (Rechazado / Cancelado como salidas, según RN-005)
"""
import time

from flask import current_app
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import selectinload

from gpizza import reglas, reloj
from gpizza.extensiones import db
from gpizza.modelos import AsignacionEntrega, Cliente, Pedido
from gpizza.servicios import asignacion, clientes
from gpizza.servicios.errores import mensaje_bd

ESTADOS_PEDIDOS = ('En Preparación', 'Listo para Entrega', 'En Camino', 'Entregado', 'Cancelado')
SEGUNDOS_ENTRE_REVISIONES = 15


# ------------------------------------------------------------------------------ consultas

def por_estado(id_sucursal: int, estado: str, limite: int = 50) -> list[Pedido]:
    """Boceto 8. Los entregados y cancelados solo de hoy (los históricos están en reportes)."""
    consulta = (select(Pedido).options(selectinload(Pedido.detalles), selectinload(Pedido.cliente))
                .where(Pedido.id_sucursal == id_sucursal, Pedido.estado == estado))
    if estado in ('Entregado', 'Cancelado'):
        inicio_del_dia = reloj.ahora().replace(hour=0, minute=0, second=0, microsecond=0)
        consulta = consulta.where(Pedido.fecha_registro >= inicio_del_dia).order_by(Pedido.fecha_registro.desc())
    else:
        consulta = consulta.order_by(Pedido.fecha_registro)
    return db.session.scalars(consulta.limit(limite)).all()


def conteos(id_sucursal: int) -> dict[str, int]:
    """Cuántos pedidos hay en cada pestaña (entregados y cancelados: solo los de hoy)."""
    inicio_del_dia = reloj.ahora().replace(hour=0, minute=0, second=0, microsecond=0)
    filas = db.session.execute(
        select(Pedido.estado, func.count()).where(
            Pedido.id_sucursal == id_sucursal,
            or_(Pedido.estado.in_(('En Preparación', 'Listo para Entrega', 'En Camino')),
                Pedido.fecha_registro >= inicio_del_dia))
        .group_by(Pedido.estado))
    return dict(filas.all())


def asignaciones_vivas(pedidos: list[Pedido]) -> dict[int, AsignacionEntrega]:
    if not pedidos:
        return {}
    filas = db.session.scalars(select(AsignacionEntrega).options(selectinload(AsignacionEntrega.repartidor)).where(
        AsignacionEntrega.id_pedido.in_([p.id_pedido for p in pedidos]),
        AsignacionEntrega.estado.in_(asignacion.VIVAS)))
    return {a.id_pedido: a for a in filas}


def minutos_en_estado(pedido: Pedido) -> int | None:
    """Minutos en preparación (RN-006) o en camino (RN-014); None en otros estados."""
    inicio = {'En Preparación': pedido.fecha_preparacion, 'En Camino': pedido.fecha_en_camino}.get(pedido.estado)
    if inicio is None:
        return None
    return int((reloj.ahora() - inicio).total_seconds() // 60)


def alerta(pedido: Pedido) -> str | None:
    minutos = minutos_en_estado(pedido)
    if pedido.estado == 'En Preparación' and minutos is not None and minutos > reglas.ALERTA_PREPARACION_MIN:
        return f'Alerta: {minutos} min en preparación (límite {reglas.ALERTA_PREPARACION_MIN}, RN-006)'
    if pedido.estado == 'En Camino' and minutos is not None and minutos > reglas.ALERTA_ENTREGA_MIN:
        return f'Alerta: {minutos} min en camino (límite {reglas.ALERTA_ENTREGA_MIN}, RN-014)'
    return None


def buscar(id_sucursal: int, texto: str) -> list[Pedido]:
    """CU-003 paso 2: por folio (YP-0001 o solo 1) o por teléfono del cliente."""
    texto = (texto or '').strip().upper()
    if not texto:
        return []
    digitos = clientes.normalizar_telefono(texto)
    condiciones = [Pedido.folio == texto]
    if texto.isdigit() and len(texto) <= 4:
        condiciones.append(Pedido.folio == f'YP-{int(texto):04d}')
    if digitos.isdigit() and len(digitos) == 10:
        condiciones.append(Cliente.telefono == digitos)
    return db.session.scalars(select(Pedido).join(Cliente).where(Pedido.id_sucursal == id_sucursal, or_(*condiciones))
                              .order_by(Pedido.fecha_registro.desc()).limit(20)).all()


def por_folio(folio: str) -> Pedido | None:
    return db.session.scalar(select(Pedido).where(Pedido.folio == folio.upper()))


def asignaciones_de(pedido: Pedido) -> list[AsignacionEntrega]:
    return db.session.scalars(select(AsignacionEntrega).where(AsignacionEntrega.id_pedido == pedido.id_pedido)
                              .order_by(AsignacionEntrega.fecha_asignacion)).all()


# ------------------------------------------------------------------------------ acciones

def _bloquear(id_pedido: int, id_sucursal: int) -> Pedido | None:
    pedido = db.session.get(Pedido, id_pedido, with_for_update=True)
    if pedido is None or pedido.id_sucursal != id_sucursal:
        db.session.rollback()
        return None
    return pedido


def marcar_listo(id_pedido: int, id_sucursal: int) -> str:
    """Decisión 2: el cajero lo marca cuando cocina termina; de inmediato se asigna repartidor (CU-002)."""
    pedido = _bloquear(id_pedido, id_sucursal)
    if pedido is None:
        return 'Ese pedido no existe en tu sucursal.'
    if pedido.estado != 'En Preparación':
        db.session.rollback()
        return f'El pedido {pedido.folio} ya no está en preparación.'
    if pedido.cancelacion_solicitada_por:
        db.session.rollback()
        return 'Hay una solicitud de cancelación pendiente; resuélvela primero (RN-005).'
    pedido.estado = 'Listo para Entrega'
    problema = _guardar()
    if problema:
        return problema
    nueva = asignacion.asignar_automatico(pedido)
    problema = _guardar()
    if problema:
        return problema
    if nueva:
        return (f'Pedido {pedido.folio} listo. Se asignó a {nueva.repartidor.nombre_completo}; '
                f'tiene {reglas.PLAZO_ACEPTAR_ASIGNACION_MIN} min para aceptarlo.')
    return f'Pedido {pedido.folio} listo. No hay repartidor disponible: se avisó al gerente.'


def solicitar_cancelacion(pedido: Pedido, parte: str, motivo: str) -> str | None:
    """RN-005 (decisión 7): una parte pide la cancelación y la otra debe aceptarla."""
    if pedido.estado != 'En Preparación':
        return 'Solo se puede pedir la cancelación de un pedido en preparación.'
    if pedido.cancelacion_solicitada_por:
        return 'Ya hay una solicitud de cancelación pendiente.'
    if len((motivo or '').strip()) < 5:
        return 'Escribe el motivo de la cancelación.'
    pedido.cancelacion_solicitada_por, pedido.motivo_cancelacion = parte, motivo.strip()[:200]
    return _guardar()


def responder_cancelacion(pedido: Pedido, parte: str, aceptar: bool) -> str | None:
    """La otra parte acepta (el pedido se cancela) o rechaza (el pedido sigue)."""
    otra = {'CLIENTE': 'CAJERO', 'CAJERO': 'CLIENTE'}[parte]
    if pedido.estado != 'En Preparación' or pedido.cancelacion_solicitada_por != otra:
        return 'No hay una solicitud de cancelación que responder.'
    if aceptar:
        pedido.estado = 'Cancelado'
    else:
        pedido.cancelacion_solicitada_por = None
    return _guardar()


def cancelar_por_telefono(id_pedido: int, id_sucursal: int, motivo: str) -> str | None:
    """Pedido hecho por teléfono o en sucursal: el cajero registra que el cliente confirmó."""
    pedido = _bloquear(id_pedido, id_sucursal)
    if pedido is None:
        return 'Ese pedido no existe en tu sucursal.'
    if pedido.origen == 'APP':
        db.session.rollback()
        return 'Este pedido se hizo en la app: el cliente debe aceptar la cancelación desde ahí.'
    if len((motivo or '').strip()) < 5:
        db.session.rollback()
        return 'Escribe el motivo de la cancelación.'
    pedido.estado, pedido.motivo_cancelacion = 'Cancelado', motivo.strip()[:200]
    pedido.cancelacion_confirmada_por_telefono = True
    return _guardar()


def cancelar_gerente(id_pedido: int, id_sucursal: int, motivo: str) -> str | None:
    """RN-005: después de "En Preparación" solo el gerente cancela (también lo puede hacer antes)."""
    pedido = _bloquear(id_pedido, id_sucursal)
    if pedido is None:
        return 'Ese pedido no existe en tu sucursal.'
    if pedido.estado not in ('Por Confirmar', 'En Preparación', 'Listo para Entrega', 'En Camino'):
        db.session.rollback()
        return f'El pedido ya está "{pedido.estado}".'
    if len((motivo or '').strip()) < 5:
        db.session.rollback()
        return 'Escribe el motivo de la cancelación.'
    pedido.estado, pedido.motivo_cancelacion = 'Cancelado', motivo.strip()[:200]
    return _guardar()


# ------------------------------------------------------------------------------ revisión periódica

def revisar_tiempos(forzar: bool = False) -> int:
    """Alertas de 45 y 90 min (RN-006, RN-014), asignaciones vencidas a los 5 min y reasignación
    (CU-002 FA-2). Se llama desde el polling de las pantallas del personal; como puede haber varias
    abiertas, se ejecuta como máximo una vez cada 15 s por proceso."""
    ahora = time.monotonic()
    ultima = current_app.extensions.get('gpizza_ultima_revision')
    if not forzar and ultima is not None and ahora - ultima < SEGUNDOS_ENTRE_REVISIONES:
        return 0
    current_app.extensions['gpizza_ultima_revision'] = ahora
    alertas = db.session.execute(text('SELECT fn_generar_alertas()')).scalar_one()
    asignacion.reasignar_pendientes()
    problema = _guardar()
    if problema:
        current_app.logger.warning('Revisión periódica: %s', problema)
    return alertas


def _guardar() -> str | None:
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return mensaje_bd(error)
    return None
