"""CU-009 Gestionar Personal (RF-006), con sus especializaciones CU-009a (cajeros) y CU-009b
(repartidores). El gerente administra cajeros, cocineros y repartidores de SU sucursal.

Contraseñas: al dar de alta o al reiniciar, se genera una temporal que nace vencida; así RN-018
obliga al empleado a elegir la suya en su primer acceso y el gerente nunca conoce la definitiva.
"""
import re
import secrets
import string
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from gpizza import reglas, reloj
from gpizza.extensiones import db
from gpizza.modelos import AsignacionEntrega, Empleado, Sesion
from gpizza.seguridad import contrasenas
from gpizza.servicios.errores import mensaje_bd

PUESTOS_ADMINISTRABLES = ('Cajero', 'Cocinero', 'Repartidor')
PATRON_USUARIO = re.compile(r'^[a-z0-9._-]{4,40}$')


def listar(id_sucursal: int, puesto: str | None = None) -> list[Empleado]:
    consulta = (select(Empleado).where(Empleado.id_sucursal == id_sucursal, Empleado.puesto.in_(PUESTOS_ADMINISTRABLES))
                .order_by(Empleado.activo.desc(), Empleado.puesto, Empleado.nombre))
    if puesto in PUESTOS_ADMINISTRABLES:
        consulta = consulta.where(Empleado.puesto == puesto)
    return db.session.scalars(consulta).all()


def del_sucursal(id_empleado: int, id_sucursal: int) -> Empleado | None:
    e = db.session.get(Empleado, id_empleado)
    if e is None or e.id_sucursal != id_sucursal or e.puesto not in PUESTOS_ADMINISTRABLES:
        return None
    return e


def contrasena_temporal() -> str:
    """Cumple RN-018 (8+ caracteres con letras y números) y es fácil de dictar."""
    letras = ''.join(secrets.choice(string.ascii_uppercase.replace('O', '').replace('I', '')) for _ in range(4))
    return f'{letras}{secrets.randbelow(9000) + 1000}'


def _vencida_desde_hoy():
    return reloj.ahora().date() - timedelta(days=reglas.CONTRASENA_VIGENCIA_DIAS)


@dataclass
class DatosEmpleado:
    nombre: str
    apellidos: str
    telefono: str
    puesto: str = ''
    username: str = ''


def _validar(datos: DatosEmpleado, nuevo: bool) -> dict[str, str]:
    errores = {}
    if not datos.nombre.strip():
        errores['nombre'] = 'Escribe el nombre.'
    if not datos.apellidos.strip():
        errores['apellidos'] = 'Escribe los apellidos.'
    if not re.fullmatch(r'[0-9]{10}', datos.telefono.strip()):
        errores['telefono'] = 'El teléfono debe tener 10 dígitos.'
    if nuevo:
        if datos.puesto not in PUESTOS_ADMINISTRABLES:
            errores['puesto'] = 'Elige el puesto: cajero, cocinero o repartidor.'
        elif datos.puesto != 'Cocinero' and not PATRON_USUARIO.match(datos.username.strip().lower()):
            errores['username'] = 'Usuario de 4 a 40 caracteres: minúsculas, números, punto o guion.'
    return errores


def crear(id_sucursal: int, datos: DatosEmpleado) -> tuple[Empleado | None, str | None, dict[str, str]]:
    """Devuelve (empleado, contraseña temporal o None si es cocinero, errores)."""
    errores = _validar(datos, nuevo=True)
    if errores:
        return None, None, errores
    temporal = None if datos.puesto == 'Cocinero' else contrasena_temporal()
    empleado = Empleado(
        id_sucursal=id_sucursal, nombre=datos.nombre.strip(), apellidos=datos.apellidos.strip(),
        telefono=datos.telefono.strip(), puesto=datos.puesto,
        username=datos.username.strip().lower() if temporal else None,
        password_hash=contrasenas.generar_hash(temporal) if temporal else None,
        fecha_cambio_password=_vencida_desde_hoy() if temporal else None,
        disponible=True if datos.puesto == 'Repartidor' else None)
    db.session.add(empleado)
    problema = _guardar()
    if problema:
        return None, None, {'username' if 'usuario' in problema else 'general': problema}
    return empleado, temporal, {}


def editar(empleado: Empleado, datos: DatosEmpleado) -> dict[str, str]:
    errores = _validar(datos, nuevo=False)
    if errores:
        return errores
    empleado.nombre, empleado.apellidos, empleado.telefono = (datos.nombre.strip(), datos.apellidos.strip(),
                                                              datos.telefono.strip())
    problema = _guardar()
    return {'general': problema} if problema else {}


def dar_de_baja(empleado: Empleado) -> str | None:
    vivas = db.session.scalar(select(AsignacionEntrega.id_asignacion).where(
        AsignacionEntrega.id_repartidor == empleado.id_empleado, AsignacionEntrega.estado.in_(('PENDIENTE', 'CONFIRMADA'))))
    if vivas:
        return 'Este repartidor tiene entregas en curso; espera a que termine o reasígnalas.'
    empleado.activo = False
    if empleado.puesto == 'Repartidor':
        empleado.disponible = False
    db.session.execute(update(Sesion).where(Sesion.id_empleado == empleado.id_empleado, Sesion.activa)
                       .values(activa=False, fecha_fin=reloj.ahora()))
    return _guardar()


def reactivar(empleado: Empleado) -> str | None:
    empleado.activo = True
    return _guardar()


def desbloquear(empleado: Empleado) -> str | None:
    """RN-018: el gerente desbloquea a su personal (el trigger reinicia el contador de intentos)."""
    empleado.bloqueado = False
    return _guardar()


def reiniciar_contrasena(empleado: Empleado) -> tuple[str | None, str | None]:
    """Devuelve (contraseña temporal, problema)."""
    if empleado.username is None:
        return None, 'Este puesto no inicia sesión.'
    temporal = contrasena_temporal()
    empleado.password_hash = contrasenas.generar_hash(temporal)
    empleado.fecha_cambio_password = _vencida_desde_hoy()
    empleado.bloqueado = False
    problema = _guardar()
    return (None, problema) if problema else (temporal, None)


def _guardar() -> str | None:
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return mensaje_bd(error)
    return None
