"""Fase 2: CU-006 Autenticar Usuario, RF-012 acceso por rol, RN-016 a RN-018 y RNF-003."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select, text

from gpizza import reloj
from gpizza.extensiones import db
from gpizza.modelos import Auditoria, Empleado, Sesion
from gpizza.seguridad import contrasenas
from tests.conftest import iniciar_sesion, token_csrf


def empleado(usuario):
    return db.session.scalar(select(Empleado).where(Empleado.username == usuario))


# ---------------------------------------------------------------- CU-006 / RF-012

@pytest.mark.parametrize('usuario, panel, texto', [
    ('cajero1.coyol', '/cajero/', 'Por confirmar'),
    ('repartidor1.coyol', '/repartidor/', 'Mis entregas'),
    ('gerente.coyol', '/gerente/', 'Solo verás la información de tu sucursal'),
])
def test_cada_rol_entra_a_su_panel(web, usuario, panel, texto):
    respuesta = iniciar_sesion(web, usuario)
    assert respuesta.status_code == 302 and respuesta.headers['Location'] == panel
    assert texto in web.get(panel).get_data(as_text=True)


def test_inicio_de_sesion_queda_en_la_auditoria(web, app_bd):
    iniciar_sesion(web, 'cajero1.coyol')
    with app_bd.app_context():
        cajero = empleado('cajero1.coyol')
        ultimo = db.session.scalar(select(Auditoria).where(Auditoria.entidad == 'sesion')
                                   .order_by(Auditoria.id_log.desc()))
        assert (ultimo.accion, ultimo.id_empleado) == ('LOGIN', cajero.id_empleado)


@pytest.mark.parametrize('ruta, rol_correcto', [('/gerente/', 'Gerente'), ('/repartidor/', 'Repartidor')])
def test_rf012_otro_rol_recibe_403(web, ruta, rol_correcto):
    iniciar_sesion(web, 'cajero1.coyol')
    respuesta = web.get(ruta)
    assert respuesta.status_code == 403
    assert 'Acceso no permitido' in respuesta.get_data(as_text=True)


def test_sin_sesion_se_pide_iniciarla_y_luego_regresa(web):
    respuesta = web.get('/gerente/')
    assert respuesta.status_code == 302 and '/login?siguiente=/gerente/' in respuesta.headers['Location']
    respuesta = web.post('/login?siguiente=/gerente/', data={
        'usuario': 'gerente.coyol', 'contrasena': 'Pizza2026', 'csrf_token': token_csrf(web)})
    assert respuesta.headers['Location'] == '/gerente/'


def test_no_redirige_a_sitios_externos_despues_del_login(web):
    respuesta = web.post('/login?siguiente=https://sitio-malo.example/robo', data={
        'usuario': 'cajero1.coyol', 'contrasena': 'Pizza2026', 'csrf_token': token_csrf(web)})
    assert respuesta.headers['Location'] == '/cajero/'


def test_cerrar_sesion(web, app_bd):
    iniciar_sesion(web, 'cajero1.coyol')
    web.post('/salir', data={'csrf_token': token_csrf(web, '/cajero/')})
    assert web.get('/cajero/').status_code == 302
    with app_bd.app_context():
        cajero = empleado('cajero1.coyol')
        assert db.session.scalar(select(Sesion).where(Sesion.id_empleado == cajero.id_empleado, Sesion.activa)) is None


# ---------------------------------------------------------------- RN-017 sesión única

def test_rn017_entrar_desde_otro_dispositivo_cierra_la_sesion_anterior(app_bd):
    celular, computadora = app_bd.test_client(), app_bd.test_client()
    iniciar_sesion(celular, 'cajero1.coyol')
    assert celular.get('/cajero/').status_code == 200
    iniciar_sesion(computadora, 'cajero1.coyol')
    respuesta = celular.get('/cajero/', follow_redirects=True)
    assert 'iniciaste sesión en otro dispositivo' in respuesta.get_data(as_text=True)
    assert computadora.get('/cajero/').status_code == 200


# ---------------------------------------------------------------- RN-018 contraseñas

def test_rn018_avisa_el_numero_de_intento_y_bloquea_al_tercero(web, app_bd):
    for intento in (1, 2):
        html = iniciar_sesion(web, 'cajero1.coyol', 'Equivocada1').get_data(as_text=True)
        assert f'Intento {intento} de 3' in html
    html = iniciar_sesion(web, 'cajero1.coyol', 'Equivocada1').get_data(as_text=True)
    assert 'se bloqueó tras 3 intentos' in html
    # Ya bloqueada, ni la contraseña correcta funciona.
    html = iniciar_sesion(web, 'cajero1.coyol').get_data(as_text=True)
    assert 'se bloqueó tras 3 intentos' in html
    with app_bd.app_context():
        assert empleado('cajero1.coyol').bloqueado
        acciones = db.session.scalars(select(Auditoria.accion).where(
            Auditoria.entidad == 'empleado', Auditoria.id_entidad == empleado('cajero1.coyol').id_empleado)).all()
        assert acciones.count('LOGIN_FALLIDO') == 2 and 'BLOQUEO' in acciones


def test_rn018_un_acierto_reinicia_el_contador(web, app_bd):
    iniciar_sesion(web, 'cajero1.coyol', 'Equivocada1')
    iniciar_sesion(web, 'cajero1.coyol')
    with app_bd.app_context():
        assert empleado('cajero1.coyol').intentos_fallidos == 0


def test_rn018_cuenta_bloqueada_de_la_demo(web):
    html = iniciar_sesion(web, 'repartidor3.coyol').get_data(as_text=True)
    assert 'se bloqueó tras 3 intentos' in html


def test_usuario_inexistente_recibe_mensaje_generico(web):
    html = iniciar_sesion(web, 'nadie.coyol').get_data(as_text=True)
    assert 'Usuario o contraseña incorrectos.' in html and 'Intento' not in html


def test_rnf003_inyeccion_sql_en_el_usuario_no_funciona(web):
    respuesta = iniciar_sesion(web, "' OR '1'='1' --", "' OR '1'='1' --")
    assert respuesta.status_code == 200
    assert 'Usuario o contraseña incorrectos.' in respuesta.get_data(as_text=True)


def test_rn018_contrasena_vencida_obliga_a_cambiarla(web, app_bd):
    respuesta = iniciar_sesion(web, 'cajero2.coyol')  # en la demo tiene 95 días
    assert respuesta.headers['Location'] == '/cambiar-contrasena'
    assert web.get('/cajero/').headers['Location'] == '/cambiar-contrasena'  # no puede ir a otro lado

    token = token_csrf(web, '/cambiar-contrasena')
    datos = {'actual': 'Pizza2026', 'csrf_token': token}
    html = web.post('/cambiar-contrasena', data=datos | {'nueva': 'corta1', 'confirmacion': 'corta1'}).get_data(as_text=True)
    assert 'al menos 8 caracteres' in html
    html = web.post('/cambiar-contrasena', data=datos | {'nueva': 'SoloLetras', 'confirmacion': 'SoloLetras'}).get_data(as_text=True)
    assert 'letras y números' in html

    respuesta = web.post('/cambiar-contrasena', data=datos | {'nueva': 'Nueva2026x', 'confirmacion': 'Nueva2026x'})
    assert respuesta.headers['Location'] == '/cajero/'
    assert web.get('/cajero/').status_code == 200
    with app_bd.app_context():
        cajero = empleado('cajero2.coyol')
        assert cajero.fecha_cambio_password == reloj.ahora().date()
        assert contrasenas.verificar(cajero.password_hash, 'Nueva2026x')


def test_rn018_politica_de_contrasenas():
    assert contrasenas.politica('Pizza2026') is None
    assert 'al menos 8' in contrasenas.politica('Piz2026')
    assert 'letras y números' in contrasenas.politica('12345678')
    assert 'letras y números' in contrasenas.politica('SoloLetras')
    hoy = date(2026, 11, 1)
    assert contrasenas.vencida(hoy - timedelta(days=90), hoy)
    assert not contrasenas.vencida(hoy - timedelta(days=89), hoy)


def test_rnf003_contrasenas_guardadas_con_argon2id(app_bd):
    with app_bd.app_context():
        hashes = db.session.scalars(text('SELECT password_hash FROM empleado WHERE username IS NOT NULL')).all()
        assert hashes and all(h.startswith('$argon2id$') for h in hashes)
        assert 'Pizza2026' not in ' '.join(hashes)


def test_rnf003_la_bd_guarda_la_huella_del_token_no_el_token(web, app_bd):
    iniciar_sesion(web, 'cajero1.coyol')
    with web.session_transaction() as cookie:
        token = cookie['token']
    with app_bd.app_context():
        huellas = db.session.scalars(text('SELECT token_hash FROM sesion WHERE activa')).all()
        assert token not in huellas and len(huellas[0]) == 64


# ---------------------------------------------------------------- comando de desbloqueo

def test_comando_desbloquear(app_bd):
    with app_bd.app_context():
        r3 = empleado('repartidor3.coyol')
        assert r3.bloqueado
    resultado = app_bd.test_cli_runner().invoke(args=['desbloquear', 'repartidor3.coyol'])
    assert 'desbloqueada' in resultado.output
    with app_bd.app_context():
        db.session.expire_all()
        r3 = empleado('repartidor3.coyol')
        assert not r3.bloqueado and r3.intentos_fallidos == 0
