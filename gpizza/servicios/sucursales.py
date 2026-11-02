"""CU-011 Administrar sucursales y gerentes (decisión 19): alta y edición de sucursales.

Solo el Administrador las da de alta o las modifica (trigger trg_sucursal_permisos). Una sucursal
nueva aparece de inmediato en la lista del cliente, sin tocar el código (RNF-005). Desactivarla la
quita de esa lista; su historial se conserva.
"""
from dataclasses import dataclass
from datetime import time
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from gpizza.extensiones import db
from gpizza.modelos import Empleado, Sucursal
from gpizza.servicios.errores import mensaje_bd


@dataclass
class DatosSucursal:
    nombre: str
    direccion: str
    ciudad: str
    estado: str = 'Veracruz'
    radio: str = '4'
    apertura: str = '11:00'
    cierre: str = '22:00'


def listar() -> list[tuple[Sucursal, int]]:
    """Cada sucursal con su número de empleados activos."""
    activos = (select(Empleado.id_sucursal, func.count().label('n')).where(Empleado.activo)
               .group_by(Empleado.id_sucursal).subquery())
    return db.session.execute(select(Sucursal, func.coalesce(activos.c.n, 0))
                              .outerjoin(activos, activos.c.id_sucursal == Sucursal.id_sucursal)
                              .order_by(Sucursal.activa.desc(), Sucursal.nombre)).all()


def activas() -> list[Sucursal]:
    return db.session.scalars(select(Sucursal).where(Sucursal.activa).order_by(Sucursal.nombre)).all()


def _hora(texto: str) -> time | None:
    try:
        return time.fromisoformat((texto or '').strip())
    except ValueError:
        return None


def _validar(datos: DatosSucursal) -> tuple[dict, dict[str, str]]:
    errores, limpios = {}, {}
    for campo, etiqueta in (('nombre', 'el nombre'), ('direccion', 'la dirección'), ('ciudad', 'la ciudad'),
                            ('estado', 'el estado')):
        valor = getattr(datos, campo).strip()
        if not valor:
            errores[campo] = f'Escribe {etiqueta}.'
        limpios[campo] = valor
    try:
        limpios['radio_cobertura_km'] = Decimal(datos.radio.strip())
        if limpios['radio_cobertura_km'] <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errores['radio'] = 'El radio de cobertura es un número mayor que 0 (km).'
    apertura, cierre = _hora(datos.apertura), _hora(datos.cierre)
    if apertura is None or cierre is None:
        errores['horario'] = 'Escribe el horario como HH:MM.'
    elif apertura >= cierre:
        errores['horario'] = 'La hora de apertura debe ser antes de la de cierre (RN-002).'
    limpios['hora_apertura'], limpios['hora_cierre'] = apertura, cierre
    return limpios, errores


def crear(datos: DatosSucursal) -> tuple[Sucursal | None, dict[str, str]]:
    limpios, errores = _validar(datos)
    if errores:
        return None, errores
    sucursal = Sucursal(**limpios)
    db.session.add(sucursal)
    problema = _guardar()
    return (None, {'general': problema}) if problema else (sucursal, {})


def editar(sucursal: Sucursal, datos: DatosSucursal) -> dict[str, str]:
    limpios, errores = _validar(datos)
    if errores:
        return errores
    for campo, valor in limpios.items():
        setattr(sucursal, campo, valor)
    problema = _guardar()
    return {'general': problema} if problema else {}


def cambiar_activa(sucursal: Sucursal, activa: bool) -> str | None:
    sucursal.activa = activa
    return _guardar()


def _guardar() -> str | None:
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return mensaje_bd(error)
    return None
