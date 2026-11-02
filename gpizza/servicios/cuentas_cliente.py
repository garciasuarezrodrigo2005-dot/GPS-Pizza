"""Cuenta del cliente (decisión 18, CU-005 y CU-006): crear cuenta, entrar con teléfono y contraseña.

- El teléfono identifica al cliente y es único (RN-004): una sola cuenta por teléfono.
- Si el cajero ya lo había registrado por un pedido telefónico, el perfil existe pero sin contraseña;
  al crear su cuenta con ese teléfono la "activa" y conserva su historial.
- RN-018 también aplica: al tercer intento fallido la cuenta se bloquea (trigger trg_cliente_bloqueo)
  y solo el gerente la desbloquea.
- La sesión del cliente vive en la cookie firmada del navegador junto con una huella de su contraseña:
  si la contraseña cambia o la cuenta se bloquea, las sesiones abiertas dejan de valer.
"""
import hashlib

from sqlalchemy import update
from sqlalchemy.exc import DBAPIError

from gpizza import reglas, reloj
from gpizza.extensiones import db
from gpizza.modelos import Cliente
from gpizza.seguridad import contrasenas
from gpizza.servicios import clientes
from gpizza.servicios.errores import mensaje_bd

_HASH_FICTICIO = contrasenas.generar_hash('Ficticia2026')
MENSAJE_BLOQUEO = 'Tu cuenta se bloqueó tras 3 intentos fallidos. Llama a tu sucursal para desbloquearla.'
MENSAJE_INCORRECTO = 'Teléfono o contraseña incorrectos.'


def huella(cliente: Cliente) -> str:
    """Identifica la contraseña vigente sin guardarla en la cookie."""
    return hashlib.sha256((cliente.password_hash or '').encode()).hexdigest()[:20]


def de_la_sesion(id_cliente: int | None, huella_guardada: str | None) -> Cliente | None:
    """El cliente de la cookie, si su cuenta sigue vigente (misma contraseña y sin bloqueo)."""
    if not id_cliente or not huella_guardada:
        return None
    cliente = db.session.get(Cliente, id_cliente)
    if cliente is None or not cliente.tiene_cuenta or cliente.bloqueado or huella(cliente) != huella_guardada:
        return None
    return cliente


def crear_cuenta(datos: clientes.DatosCliente, contrasena: str, confirmacion: str) -> tuple[Cliente | None, dict[str, str]]:
    datos.telefono = clientes.normalizar_telefono(datos.telefono)
    errores = clientes.validar(datos, exigir_direccion=False)   # decisión 21: se pide en el primer pedido
    if contrasena != confirmacion:
        errores['confirmacion'] = 'La contraseña y su confirmación no coinciden.'
    problema = contrasenas.politica(contrasena or '')
    if problema:
        errores['contrasena'] = problema
    existente = clientes.por_telefono(datos.telefono) if 'telefono' not in errores else None
    if existente is not None and existente.tiene_cuenta:
        errores['telefono'] = 'Ya existe una cuenta con este teléfono. Inicia sesión o pide a tu sucursal que la desbloquee.'
    if errores:
        return None, errores

    cliente, errores = clientes.registrar_o_actualizar(datos, guardar_direccion=False, exigir_direccion=False)
    if errores:
        return None, errores
    cliente.password_hash = contrasenas.generar_hash(contrasena)
    cliente.fecha_alta_cuenta = reloj.ahora()
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return None, {'general': mensaje_bd(error)}
    return cliente, {}


def entrar(telefono: str, contrasena: str) -> tuple[Cliente | None, str]:
    """Devuelve (cliente, '') si entra, o (None, mensaje) si no."""
    cliente = clientes.por_telefono(telefono or '')
    if cliente is None or not cliente.tiene_cuenta:
        # Se verifica igual contra un hash cualquiera: así no se delata qué teléfonos tienen cuenta.
        contrasenas.verificar(_HASH_FICTICIO, contrasena or '')
        if cliente is not None:
            return None, 'Este teléfono todavía no tiene cuenta. Toca "Crear cuenta" para elegir tu contraseña.'
        return None, MENSAJE_INCORRECTO
    if cliente.bloqueado:
        return None, MENSAJE_BLOQUEO
    if not contrasenas.verificar(cliente.password_hash, contrasena or ''):
        intentos, bloqueado = db.session.execute(
            update(Cliente).where(Cliente.id_cliente == cliente.id_cliente)
            .values(intentos_fallidos=Cliente.intentos_fallidos + 1)
            .returning(Cliente.intentos_fallidos, Cliente.bloqueado)).one()
        db.session.commit()
        if bloqueado:
            return None, MENSAJE_BLOQUEO
        return None, f'{MENSAJE_INCORRECTO} Intento {intentos} de {reglas.MAX_INTENTOS_LOGIN}.'
    if cliente.intentos_fallidos:
        cliente.intentos_fallidos = 0
        db.session.commit()
    return cliente, ''


def cambiar_contrasena(cliente: Cliente, actual: str, nueva: str, confirmacion: str) -> str | None:
    if not contrasenas.verificar(cliente.password_hash, actual or ''):
        return 'La contraseña actual no es correcta.'
    if nueva != confirmacion:
        return 'La nueva contraseña y su confirmación no coinciden.'
    problema = contrasenas.politica(nueva or '')
    if problema:
        return problema
    cliente.password_hash = contrasenas.generar_hash(nueva)
    db.session.commit()
    return None


# ------------------------------------------------------------------------------ atención del gerente

def desbloquear(cliente: Cliente) -> str | None:
    """RN-018: el gerente desbloquea la cuenta (el trigger reinicia los intentos)."""
    cliente.bloqueado = False
    return _guardar()


def quitar_contrasena(cliente: Cliente) -> str | None:
    """El cliente olvidó su contraseña: se quita y él vuelve a crear su cuenta con su teléfono.
    Su perfil e historial de pedidos se conservan."""
    cliente.password_hash = None
    cliente.fecha_alta_cuenta = None
    cliente.bloqueado = False
    return _guardar()


def _guardar() -> str | None:
    try:
        db.session.commit()
    except DBAPIError as error:
        db.session.rollback()
        return mensaje_bd(error)
    return None
