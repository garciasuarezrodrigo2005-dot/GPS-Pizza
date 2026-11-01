"""CU-006 Autenticar Usuario: inicio y cierre de sesión, y cambio de contraseña (RN-016 a RN-018).

La sesión funciona con un token aleatorio: el navegador lo guarda en su cookie firmada y la base
de datos guarda solo su huella SHA-256. Al entrar desde otro dispositivo, el trigger
trg_sesion_unica desactiva la sesión anterior (RN-017).
"""
import hashlib
import secrets
from dataclasses import dataclass

from sqlalchemy import select, update

from gpizza import reglas, reloj
from gpizza.extensiones import db
from gpizza.modelos import Empleado, Sesion
from gpizza.seguridad import contrasenas

# Hash de una contraseña cualquiera. Si el usuario no existe se verifica contra él igual:
# así responder "no existe" tarda lo mismo que "contraseña incorrecta" y no delata qué usuarios hay.
_HASH_FICTICIO = contrasenas.generar_hash('Ficticia2026')

MENSAJE_BLOQUEO = 'Tu cuenta se bloqueó tras 3 intentos fallidos. Contacta al gerente.'


@dataclass
class ResultadoLogin:
    ok: bool
    mensaje: str = ''
    token: str | None = None
    empleado: Empleado | None = None


def huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def iniciar_sesion(usuario: str, contrasena: str, dispositivo: str = '') -> ResultadoLogin:
    nombre = (usuario or '').strip().lower()
    empleado = db.session.scalar(select(Empleado).where(Empleado.username == nombre))

    if empleado is None or empleado.password_hash is None:
        contrasenas.verificar(_HASH_FICTICIO, contrasena or '')
        return ResultadoLogin(False, 'Usuario o contraseña incorrectos.')
    if not empleado.activo:
        return ResultadoLogin(False, 'Esta cuenta está dada de baja.')
    if empleado.bloqueado:
        return ResultadoLogin(False, MENSAJE_BLOQUEO)

    if not contrasenas.verificar(empleado.password_hash, contrasena or ''):
        # RN-018: se suma el intento en la BD (un solo UPDATE, sin carreras entre peticiones);
        # al tercero, el trigger trg_empleado_bloqueo bloquea la cuenta.
        intentos, bloqueado = db.session.execute(
            update(Empleado).where(Empleado.id_empleado == empleado.id_empleado)
            .values(intentos_fallidos=Empleado.intentos_fallidos + 1)
            .returning(Empleado.intentos_fallidos, Empleado.bloqueado)).one()
        db.session.commit()
        if bloqueado:
            return ResultadoLogin(False, MENSAJE_BLOQUEO)
        return ResultadoLogin(False, f'Usuario o contraseña incorrectos. Intento {intentos} de {reglas.MAX_INTENTOS_LOGIN}.')

    token = secrets.token_urlsafe(32)
    empleado.intentos_fallidos = 0
    db.session.add(Sesion(id_empleado=empleado.id_empleado, token_hash=huella(token), dispositivo=dispositivo[:100]))
    db.session.commit()
    return ResultadoLogin(True, token=token, empleado=empleado)


def sesion_activa(token: str) -> Sesion | None:
    """La sesión del token, si sigue activa y su empleado puede usar el sistema."""
    sesion = db.session.scalar(select(Sesion).where(Sesion.token_hash == huella(token)))
    if sesion is None or not sesion.activa or sesion.empleado.bloqueado or not sesion.empleado.activo:
        return None
    return sesion


def cerrar_sesion(token: str) -> None:
    db.session.execute(update(Sesion).where(Sesion.token_hash == huella(token), Sesion.activa)
                       .values(activa=False, fecha_fin=reloj.ahora()))
    db.session.commit()


def contrasena_vencida(empleado: Empleado) -> bool:
    return contrasenas.vencida(empleado.fecha_cambio_password, reloj.ahora().date())


def cambiar_contrasena(empleado: Empleado, actual: str, nueva: str, confirmacion: str) -> str | None:
    """Devuelve el problema (para mostrarlo) o None si la contraseña se cambió."""
    if not contrasenas.verificar(empleado.password_hash, actual or ''):
        return 'La contraseña actual no es correcta.'
    if nueva != confirmacion:
        return 'La nueva contraseña y su confirmación no coinciden.'
    if nueva == actual:
        return 'La nueva contraseña debe ser distinta de la actual.'
    problema = contrasenas.politica(nueva or '')
    if problema:
        return problema
    empleado.password_hash = contrasenas.generar_hash(nueva)
    empleado.fecha_cambio_password = reloj.ahora().date()
    db.session.commit()
    return None
