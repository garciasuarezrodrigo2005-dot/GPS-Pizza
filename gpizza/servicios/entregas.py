"""RF-010 Control de entregas (RN-013): ubicación del repartidor y entrega en dos pasos.

Paso 1 (cliente): firma digital en el celular del repartidor o código de 4 dígitos que el cliente
ve en su app. Paso 2 (repartidor): confirma la entrega con su sesión. Sin los dos, el pedido no
pasa a "Entregado"; la base de datos lo vuelve a exigir (rn013_*, trg_pedido_cambio).
"""
import base64
import binascii
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from gpizza import reloj
from gpizza.extensiones import db
from gpizza.modelos import AsignacionEntrega, Empleado, Pedido
from gpizza.servicios import geo
from gpizza.servicios.errores import mensaje_bd

FIRMA_MAX_BYTES = 200_000
CABECERA_PNG = b'\x89PNG\r\n\x1a\n'


def en_camino(id_repartidor: int) -> list[AsignacionEntrega]:
    return db.session.scalars(select(AsignacionEntrega).where(
        AsignacionEntrega.id_repartidor == id_repartidor, AsignacionEntrega.estado == 'CONFIRMADA')).all()


def actualizar_ubicacion(id_repartidor: int, latitud, longitud) -> str | None:
    """GPS del repartidor. Solo se guarda mientras lleva una entrega: "El GPS se activa solo cuando
    se asigna un repartidor y se apaga al entregar" (boceto 5)."""
    if not geo.coordenadas_validas(latitud, longitud):
        return 'Coordenadas inválidas.'
    if not en_camino(id_repartidor):
        return 'Sin entregas en camino: no se registra la ubicación.'
    repartidor = db.session.get(Empleado, id_repartidor)
    repartidor.latitud_actual, repartidor.longitud_actual = round(float(latitud), 6), round(float(longitud), 6)
    db.session.commit()
    return None


def ubicacion_para_cliente(pedido: Pedido) -> dict:
    """Lo que el mapa del cliente necesita (boceto 5). Fuera de "En Camino" no se comparte la ubicación."""
    if pedido.estado != 'En Camino':
        return {'estado': pedido.estado}
    asignacion = db.session.scalar(select(AsignacionEntrega).where(
        AsignacionEntrega.id_pedido == pedido.id_pedido, AsignacionEntrega.estado == 'CONFIRMADA'))
    repartidor = asignacion.repartidor
    datos = {'estado': pedido.estado, 'repartidor': repartidor.nombre_completo, 'telefono': repartidor.telefono,
             'latitud': _num(repartidor.latitud_actual), 'longitud': _num(repartidor.longitud_actual),
             'destino_latitud': _num(pedido.latitud_entrega), 'destino_longitud': _num(pedido.longitud_entrega),
             'minutos': None}
    if None not in (datos['latitud'], datos['destino_latitud']):
        datos['minutos'] = geo.minutos_estimados(datos['latitud'], datos['longitud'],
                                                 datos['destino_latitud'], datos['destino_longitud'])
    return datos


def _num(valor):
    return None if valor is None else float(valor)


def _mi_asignacion(id_asignacion: int, id_repartidor: int) -> AsignacionEntrega | None:
    asignacion = db.session.get(AsignacionEntrega, id_asignacion, with_for_update=True)
    if asignacion is None or asignacion.id_repartidor != id_repartidor:
        db.session.rollback()
        return None
    return asignacion


def leer_firma(data_url: str) -> bytes | None:
    """El canvas manda 'data:image/png;base64,....'. Se aceptan solo PNG reales y de tamaño razonable."""
    if not data_url or not data_url.startswith('data:image/png;base64,'):
        return None
    try:
        datos = base64.b64decode(data_url.split(',', 1)[1], validate=True)
    except (binascii.Error, ValueError):
        return None
    if not datos.startswith(CABECERA_PNG) or len(datos) > FIRMA_MAX_BYTES:
        return None
    return datos


def confirmar_cliente(id_asignacion: int, id_repartidor: int, firma: str = '', codigo: str = '') -> str | None:
    """Paso 1 de RN-013: firma del cliente o su código de entrega."""
    asignacion = _mi_asignacion(id_asignacion, id_repartidor)
    if asignacion is None:
        return 'Esa entrega no está asignada a ti.'
    if asignacion.estado != 'CONFIRMADA' or asignacion.pedido.estado != 'En Camino':
        db.session.rollback()
        return 'Esta entrega no está en camino.'
    if asignacion.fecha_confirmacion_cliente is not None:
        db.session.rollback()
        return 'El cliente ya confirmó la recepción.'
    codigo = (codigo or '').strip()
    if codigo:
        if codigo != asignacion.pedido.codigo_entrega:
            db.session.rollback()
            return 'El código no coincide con el que ve el cliente en su app (RN-013).'
        asignacion.codigo_confirmacion = codigo
    else:
        png = leer_firma(firma)
        if png is None:
            db.session.rollback()
            return 'Pide al cliente que firme en el recuadro o que te dé su código de entrega (RN-013).'
        asignacion.firma_digital = png
    return _guardar()


def entregar(id_asignacion: int, id_repartidor: int) -> str | None:
    """Paso 2 de RN-013: el repartidor confirma; se guardan fecha y hora y el pedido queda "Entregado"."""
    asignacion = _mi_asignacion(id_asignacion, id_repartidor)
    if asignacion is None:
        return 'Esa entrega no está asignada a ti.'
    if asignacion.fecha_confirmacion_cliente is None:
        db.session.rollback()
        return 'Primero el cliente debe firmar o darte su código (RN-013).'
    asignacion.estado = 'ENTREGADA'
    return _guardar()


def historial_hoy(id_repartidor: int) -> list[AsignacionEntrega]:
    inicio = reloj.ahora().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.session.scalars(select(AsignacionEntrega).where(
        AsignacionEntrega.id_repartidor == id_repartidor, AsignacionEntrega.estado == 'ENTREGADA',
        AsignacionEntrega.fecha_hora_entrega >= inicio, AsignacionEntrega.fecha_hora_entrega < inicio + timedelta(days=1))
        .order_by(AsignacionEntrega.fecha_hora_entrega.desc())).all()


def firma_de(pedido: Pedido) -> bytes | None:
    return db.session.scalar(select(AsignacionEntrega.firma_digital).where(
        AsignacionEntrega.id_pedido == pedido.id_pedido, AsignacionEntrega.estado == 'ENTREGADA'))


def _guardar() -> str | None:
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return mensaje_bd(error)
    return None
