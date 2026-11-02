"""Fase 0: disponibilidad (RNF-002), seguridad básica (RNF-003), medición de tiempos (RNF-001),
PWA (RNF-007) y pantalla de inicio con el horario de pedidos (RN-002)."""
from sqlalchemy import text

from gpizza.config import url_bd
from gpizza.extensiones import db
from tests.conftest import requiere_bd

# Puerto donde no escucha nadie: simula que PostgreSQL está caído.
URL_BD_CAIDA = url_bd('gpizza_test').set(port=1)


# ---------- RNF-002: chequeo de salud ----------

@requiere_bd
def test_salud_con_bd_disponible(cliente):
    respuesta = cliente.get('/salud')
    assert respuesta.status_code == 200
    assert respuesta.get_json()['estado'] == 'ok'
    assert respuesta.get_json()['bd'] == 'ok'


def test_salud_con_bd_caida_responde_503_sin_tumbar_la_app(crear_app):
    app = crear_app(SQLALCHEMY_DATABASE_URI=URL_BD_CAIDA)
    cliente = app.test_client()

    respuesta = cliente.get('/salud')
    assert respuesta.status_code == 503
    assert respuesta.get_json() | {'hora': None} == {
        'estado': 'degradado', 'bd': 'caida', 'version': respuesta.get_json()['version'], 'hora': None}
    # La app sigue atendiendo otras pantallas.
    assert cliente.get('/').status_code == 200


def test_pagina_que_usa_la_bd_caida_muestra_error_amable(crear_app):
    app = crear_app(SQLALCHEMY_DATABASE_URI=URL_BD_CAIDA)

    @app.get('/prueba-consulta')
    def _consulta():
        db.session.execute(text('SELECT 1'))
        return 'no debería llegar aquí'

    respuesta = app.test_client().get('/prueba-consulta')
    assert respuesta.status_code == 503
    assert 'No pudimos conectar con la base de datos' in respuesta.get_data(as_text=True)


def test_error_inesperado_muestra_pagina_amable_y_la_app_sigue(crear_app):
    app = crear_app(PROPAGATE_EXCEPTIONS=False)

    @app.get('/prueba-error')
    def _falla():
        raise ValueError('falla de prueba')

    cliente = app.test_client()
    respuesta = cliente.get('/prueba-error')
    assert respuesta.status_code == 500
    assert 'Algo salió mal' in respuesta.get_data(as_text=True)
    assert cliente.get('/').status_code == 200


def test_pagina_inexistente_muestra_404_en_espanol(cliente):
    respuesta = cliente.get('/no-existe')
    assert respuesta.status_code == 404
    assert 'Página no encontrada' in respuesta.get_data(as_text=True)


# ---------- RNF-003: seguridad básica ----------

def test_post_sin_token_csrf_es_rechazado(app):
    @app.post('/prueba-formulario')
    def _formulario():
        return 'aceptado'

    respuesta = app.test_client().post('/prueba-formulario', data={'dato': '1'})
    assert respuesta.status_code == 400
    assert 'El formulario expiró' in respuesta.get_data(as_text=True)


def test_cabeceras_de_seguridad(cliente):
    cabeceras = cliente.get('/').headers
    assert cabeceras['X-Content-Type-Options'] == 'nosniff'
    assert cabeceras['X-Frame-Options'] == 'DENY'
    # Solo el origen a otros sitios: suficiente para que OpenStreetMap entregue los mosaicos, sin filtrar rutas.
    assert cabeceras['Referrer-Policy'] == 'strict-origin-when-cross-origin'


# ---------- RNF-001: cada respuesta trae su tiempo ----------

def test_cada_respuesta_trae_su_tiempo_en_server_timing(cliente):
    valor = cliente.get('/').headers['Server-Timing']
    milisegundos = float(valor.removeprefix('app;dur='))
    assert milisegundos < 3000


# ---------- RNF-007: PWA ----------

def test_service_worker_y_manifest_disponibles(cliente):
    sw = cliente.get('/sw.js')
    assert sw.status_code == 200
    assert 'javascript' in sw.content_type
    manifest = cliente.get('/static/manifest.webmanifest')
    assert manifest.status_code == 200
    assert b'"display": "standalone"' in manifest.data


# ---------- RN-002: el cliente ve el horario de pedidos ----------

def test_inicio_en_horario_muestra_horario(crear_app):
    html = crear_app(HORA_DEMO='14:00').test_client().get('/').get_data(as_text=True)
    assert 'Recibimos pedidos de 11:00 a 22:00 h' in html


def test_inicio_fuera_de_horario_avisa_al_cliente(crear_app):
    html = crear_app(HORA_DEMO='08:30').test_client().get('/').get_data(as_text=True)
    assert 'Fuera de horario' in html
