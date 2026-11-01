"""Control de acceso por rol (RF-012, RN-016, RNF-003).

- cargar_usuario(): en cada petición identifica al empleado por su token de sesión y lo deja
  en g.usuario. Si la sesión se cerró en otro dispositivo (RN-017), lo saca con un aviso.
- @rol_requerido('Gerente'): protege una ruta; sin sesión manda al login y con otro rol da 403.
"""
from dataclasses import dataclass
from functools import wraps
from urllib.parse import urlparse

from flask import abort, flash, g, redirect, request, session, url_for

from gpizza import reloj
from gpizza.bd import fijar_contexto
from gpizza.extensiones import db
from gpizza.servicios import autenticacion

# Pantalla principal de cada rol, a donde llega después del login.
INICIO_POR_ROL = {'Cajero': 'cajero.inicio', 'Repartidor': 'repartidor.inicio', 'Gerente': 'gerente.inicio'}


@dataclass(frozen=True)
class UsuarioActual:
    id_empleado: int
    id_sesion: int
    nombre: str
    rol: str
    id_sucursal: int
    sucursal: str
    debe_cambiar_contrasena: bool


def cargar_usuario() -> None:
    g.usuario = None
    # /salud debe responder su JSON aunque la BD esté caída (RNF-002), así que no busca sesiones.
    if request.endpoint in ('static', 'sistema.salud', 'sistema.service_worker'):
        return
    token = session.get('token')
    if not token:
        return
    sesion = autenticacion.sesion_activa(token)
    if sesion is None:
        session.clear()
        flash('Tu sesión se cerró: iniciaste sesión en otro dispositivo o tu cuenta cambió. '
              'Vuelve a entrar.', 'aviso')
        return
    e = sesion.empleado
    g.usuario = UsuarioActual(
        id_empleado=e.id_empleado, id_sesion=sesion.id_sesion, nombre=e.nombre_completo, rol=e.puesto,
        id_sucursal=e.id_sucursal, sucursal=e.sucursal.nombre,
        debe_cambiar_contrasena=autenticacion.contrasena_vencida(e))
    # La transacción ya había empezado (para buscar la sesión) sin usuario: se le avisa a la BD
    # quién es, para que los triggers y la auditoría lo sepan (RN-019).
    fijar_contexto(db.session, rol=e.puesto, id_empleado=e.id_empleado,
                   ahora=reloj.ahora() if reloj.simulada() else None)


def destino_seguro(siguiente: str | None) -> str | None:
    """Solo se permite regresar a rutas de esta misma app (evita redirecciones a otros sitios)."""
    if not siguiente:
        return None
    partes = urlparse(siguiente)
    if partes.scheme or partes.netloc or not siguiente.startswith('/') or siguiente.startswith('//'):
        return None
    return siguiente


def rol_requerido(*roles: str):
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            usuario = g.get('usuario')
            if usuario is None:
                flash('Inicia sesión para continuar.', 'aviso')
                return redirect(url_for('auth.login', siguiente=request.path))
            if usuario.debe_cambiar_contrasena:
                return redirect(url_for('auth.cambiar_contrasena'))
            if roles and usuario.rol not in roles:
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador
