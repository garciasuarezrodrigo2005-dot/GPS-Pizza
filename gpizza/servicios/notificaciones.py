"""CU-007 Notificar Estado (RF-007): lectura de las notificaciones que generan los triggers.

Un empleado recibe las dirigidas a él y las dirigidas a su rol en su sucursal (p. ej. "todos los
gerentes de Coyol"). Solo se muestran las recientes (últimas 24 h): los avisos de pedidos de días
anteriores ya no sirven en la operación y están en la auditoría y los reportes.
"""
from datetime import timedelta

from sqlalchemy import and_, func, or_, select, update

from gpizza import reloj
from gpizza.extensiones import db
from gpizza.modelos import Notificacion, Pedido


def _del_empleado(usuario):
    recientes = Notificacion.fecha_envio >= reloj.ahora() - timedelta(hours=24)
    de_mi_rol = and_(Notificacion.rol_destino == usuario.rol,
                     Notificacion.id_pedido.in_(select(Pedido.id_pedido).where(Pedido.id_sucursal == usuario.id_sucursal)))
    return and_(recientes, or_(Notificacion.id_empleado == usuario.id_empleado, de_mi_rol))


def no_leidas(usuario) -> int:
    return db.session.scalar(select(func.count()).select_from(Notificacion)
                             .where(_del_empleado(usuario), ~Notificacion.leida))


def recientes(usuario, limite: int = 40) -> list[Notificacion]:
    return db.session.scalars(select(Notificacion).where(_del_empleado(usuario))
                              .order_by(Notificacion.fecha_envio.desc(), Notificacion.id_notificacion.desc())
                              .limit(limite)).all()


def marcar_leidas(usuario) -> None:
    db.session.execute(update(Notificacion).where(_del_empleado(usuario), ~Notificacion.leida)
                       .values(leida=True).execution_options(synchronize_session=False))
    db.session.commit()


def del_pedido_para_cliente(pedido: Pedido, limite: int = 3) -> list[Notificacion]:
    """Los últimos avisos del pedido para el cliente (pantalla "Tu pedido")."""
    return db.session.scalars(select(Notificacion).where(
        Notificacion.id_pedido == pedido.id_pedido, Notificacion.id_cliente == pedido.id_cliente)
        .order_by(Notificacion.id_notificacion.desc()).limit(limite)).all()
