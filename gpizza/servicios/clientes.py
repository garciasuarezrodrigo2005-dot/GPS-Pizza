"""CU-005 Registrar Perfil de Cliente (RF-005) y búsqueda por teléfono."""
import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.exc import DBAPIError

from gpizza.extensiones import db
from gpizza.modelos import Cliente
from gpizza.servicios import geo
from gpizza.servicios.errores import mensaje_bd

PATRON_TELEFONO = re.compile(r'^[0-9]{10}$')
PATRON_CP = re.compile(r'^[0-9]{5}$')


def normalizar_telefono(telefono: str | None) -> str:
    """Quita espacios y guiones: '229 586-5835' -> '2295865835'."""
    return re.sub(r'[\s\-().]', '', telefono or '')


def telefono_valido(telefono: str) -> bool:
    return bool(PATRON_TELEFONO.match(telefono))


def por_telefono(telefono: str) -> Cliente | None:
    return db.session.scalar(select(Cliente).where(Cliente.telefono == normalizar_telefono(telefono)))


def buscar(texto: str, limite: int = 30) -> list[Cliente]:
    """Por teléfono o por nombre. El texto va como parámetro de la consulta, nunca pegado al SQL."""
    texto = (texto or '').strip()
    consulta = select(Cliente).order_by(Cliente.nombre).limit(limite)
    if texto:
        consulta = consulta.where(or_(Cliente.telefono.startswith(normalizar_telefono(texto)),
                                      Cliente.nombre.ilike(f'%{texto}%')))
    return db.session.scalars(consulta).all()


@dataclass
class DatosCliente:
    nombre: str
    telefono: str
    direccion: str
    colonia: str = ''
    codigo_postal: str = ''
    latitud: str = ''    # opcionales: "Usar mi ubicación" para que el domicilio aparezca en el mapa
    longitud: str = ''


def direccion_completa(cliente: Cliente) -> str:
    """'Calle Laurel 33, Col. Floresta, C.P. 91940': lo que se copia al pedido y ve el repartidor."""
    partes = [cliente.direccion]
    if cliente.colonia:
        partes.append(f'Col. {cliente.colonia}')
    if cliente.codigo_postal:
        partes.append(f'C.P. {cliente.codigo_postal}')
    return ', '.join(partes)


def validar(datos: DatosCliente) -> dict[str, str]:
    """RN-004: nombre, teléfono (10 dígitos) y dirección son obligatorios."""
    errores = {}
    if not datos.nombre.strip():
        errores['nombre'] = 'Escribe el nombre del cliente.'
    if not telefono_valido(datos.telefono):
        errores['telefono'] = 'El teléfono debe tener 10 dígitos, solo números.'
    if not datos.direccion.strip():
        errores['direccion'] = 'Escribe la dirección de entrega.'
    if datos.codigo_postal and not PATRON_CP.match(datos.codigo_postal):
        errores['codigo_postal'] = 'El código postal tiene 5 dígitos.'
    return errores


def registrar_o_actualizar(datos: DatosCliente) -> tuple[Cliente | None, dict[str, str]]:
    """Crea el perfil si el teléfono es nuevo (CU-005) o actualiza nombre y dirección si ya existía.
    No hace commit: el pedido y el cliente se guardan juntos en la misma transacción."""
    datos.telefono = normalizar_telefono(datos.telefono)
    errores = validar(datos)
    if errores:
        return None, errores
    cliente = por_telefono(datos.telefono)
    if cliente is None:
        cliente = Cliente(telefono=datos.telefono)
        db.session.add(cliente)
    cliente.nombre = datos.nombre.strip()
    cliente.direccion = datos.direccion.strip()
    cliente.colonia = datos.colonia.strip() or None
    cliente.codigo_postal = datos.codigo_postal.strip() or None
    if datos.latitud and geo.coordenadas_validas(datos.latitud, datos.longitud):
        cliente.latitud, cliente.longitud = round(float(datos.latitud), 6), round(float(datos.longitud), 6)
    try:
        db.session.flush()
    except DBAPIError as error:
        db.session.rollback()
        return None, {'general': mensaje_bd(error)}
    return cliente, {}
