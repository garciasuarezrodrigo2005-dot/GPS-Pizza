"""Rutas del sistema: chequeo de salud, PWA y páginas de error (RNF-002, RNF-007)."""
from flask import Blueprint, current_app, jsonify, render_template, send_from_directory
from flask_wtf.csrf import CSRFError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from gpizza import __version__, reloj
from gpizza.extensiones import db

bp = Blueprint('sistema', __name__)


@bp.get('/salud')
def salud():
    """Health check (RNF-002). Responde aunque la base de datos esté caída:
    200 si todo está bien, 503 si la BD no contesta."""
    try:
        db.session.execute(text('SELECT 1'))
        estado_bd = 'ok'
    except Exception as error:  # cualquier fallo de BD se reporta, nunca tumba la app
        db.session.rollback()
        current_app.logger.warning('Chequeo de salud: la BD no responde (%s)', error)
        estado_bd = 'caida'
    cuerpo = {
        'estado': 'ok' if estado_bd == 'ok' else 'degradado',
        'bd': estado_bd,
        'version': __version__,
        'hora': reloj.ahora().isoformat(timespec='seconds'),
    }
    return jsonify(cuerpo), 200 if estado_bd == 'ok' else 503


# ---------- PWA: la app se instala en el celular (RNF-007) ----------

@bp.get('/sw.js')
def service_worker():
    """El service worker se sirve desde la raíz para que controle todas las rutas de la app."""
    respuesta = send_from_directory(current_app.static_folder, 'sw.js', mimetype='application/javascript')
    respuesta.headers['Cache-Control'] = 'no-cache'
    return respuesta


@bp.get('/favicon.ico')
def favicon():
    return send_from_directory(current_app.static_folder, 'img/icono-192.png', mimetype='image/png')


@bp.get('/offline')
def sin_conexion():
    return render_template('offline.html')


# ---------- Páginas de error amables, en español (RNF-002, RNF-004) ----------

def _pagina_error(codigo, titulo, mensaje):
    return render_template('errores/error.html', codigo=codigo, titulo=titulo, mensaje=mensaje), codigo


@bp.app_errorhandler(403)
def prohibido(_error):
    return _pagina_error(403, 'Acceso no permitido', 'Tu usuario no tiene permiso para ver esta pantalla.')


@bp.app_errorhandler(404)
def no_encontrado(_error):
    return _pagina_error(404, 'Página no encontrada', 'La dirección que abriste no existe.')


@bp.app_errorhandler(CSRFError)
def csrf_invalido(_error):
    return _pagina_error(400, 'El formulario expiró', 'Recarga la página e inténtalo de nuevo.')


@bp.app_errorhandler(OperationalError)
def bd_caida(error):
    db.session.rollback()
    current_app.logger.error('Base de datos no disponible: %s', error)
    return _pagina_error(503, 'Servicio no disponible por un momento',
                         'No pudimos conectar con la base de datos. Inténtalo de nuevo en unos minutos.')


@bp.app_errorhandler(500)
def error_interno(error):
    current_app.logger.exception('Error interno: %s', getattr(error, 'original_exception', error))
    return _pagina_error(500, 'Algo salió mal', 'Ocurrió un error inesperado. Ya quedó registrado; inténtalo de nuevo.')
