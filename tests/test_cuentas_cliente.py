"""Fase 8 · cuenta del cliente (decisión 18): crear cuenta, entrar con teléfono y contraseña, RN-018."""
import pytest
from sqlalchemy import select

from gpizza.extensiones import db
from gpizza.modelos import Cliente
from tests.conftest import iniciar_sesion, token_csrf
from tests.test_pedidos import TEL_ANA

TEL_SIN_CUENTA = '2295678901'   # Diego: lo registró la sucursal por teléfono (seed)


def entrar(web, telefono, contrasena='Pizza2026'):
    return web.post('/entrar', data={'telefono': telefono, 'contrasena': contrasena,
                                     'csrf_token': token_csrf(web, '/crear-cuenta')})


def crear(web, telefono, contrasena='Pizza2026', **cambios):
    datos = {'telefono': telefono, 'nombre': 'Laura Prueba', 'direccion': 'Calle Prueba 1', 'colonia': 'Centro',
             'codigo_postal': '91700', 'contrasena': contrasena, 'confirmacion': contrasena,
             'csrf_token': token_csrf(web, '/crear-cuenta')}
    return web.post('/crear-cuenta', data=datos | cambios)


def cliente(app, telefono) -> Cliente:
    with app.app_context():
        return db.session.scalar(select(Cliente).where(Cliente.telefono == telefono))


def test_crear_cuenta_y_entrar(app_bd, web):
    r = crear(web, '2290002222')
    assert r.status_code == 302 and r.headers['Location'] == '/pedido'
    assert 'Laura Prueba' in web.get('/pedido').get_data(as_text=True)
    nuevo = cliente(app_bd, '2290002222')
    assert nuevo.password_hash.startswith('$argon2id$') and nuevo.fecha_alta_cuenta is not None   # RNF-003


def test_el_telefono_es_unico_una_cuenta_por_telefono(web):
    html = crear(web, TEL_ANA).get_data(as_text=True)
    assert 'Ya existe una cuenta con este teléfono' in html


@pytest.mark.parametrize('cambios, mensaje', [
    ({'confirmacion': 'Otra2026'}, 'no coinciden'),
    ({'contrasena': 'corta1', 'confirmacion': 'corta1'}, 'al menos 8'),
    ({'contrasena': 'sinnumeros', 'confirmacion': 'sinnumeros'}, 'letras y números'),
    ({'telefono': '229-123'}, '10 dígitos'),
    ({'direccion': ''}, 'dirección'),
])
def test_crear_cuenta_valida_los_datos(web, cambios, mensaje):
    r = crear(web, cambios.pop('telefono', '2290003333'), **cambios)
    assert r.status_code == 422 and mensaje in r.get_data(as_text=True)


def test_el_cliente_registrado_por_telefono_activa_su_cuenta(app_bd, web):
    """El cajero lo registró sin contraseña: al crear su cuenta conserva su perfil e historial."""
    antes = cliente(app_bd, TEL_SIN_CUENTA)
    assert not antes.tiene_cuenta
    assert 'todavía no tiene cuenta' in entrar(web, TEL_SIN_CUENTA).get_data(as_text=True)
    assert crear(web, TEL_SIN_CUENTA, nombre='Diego Navarro Báez').status_code == 302
    despues = cliente(app_bd, TEL_SIN_CUENTA)
    assert despues.id_cliente == antes.id_cliente and despues.tiene_cuenta


def test_sin_sesion_no_hay_pedido(web):
    r = web.get('/pedido')
    assert r.status_code == 302 and r.headers['Location'] == '/'


def test_rn018_tres_intentos_bloquean_la_cuenta_y_el_gerente_la_desbloquea(app_bd, web):
    assert 'Intento 1 de 3' in entrar(web, TEL_ANA, 'Equivocada1').get_data(as_text=True)
    entrar(web, TEL_ANA, 'Equivocada1')
    assert 'se bloqueó' in entrar(web, TEL_ANA, 'Equivocada1').get_data(as_text=True)
    assert 'se bloqueó' in entrar(web, TEL_ANA).get_data(as_text=True)   # ni con la correcta

    gerente = app_bd.test_client()
    iniciar_sesion(gerente, 'gerente.coyol')
    id_ana = cliente(app_bd, TEL_ANA).id_cliente
    assert 'Bloqueada' in gerente.get(f'/gerente/clientes/{id_ana}').get_data(as_text=True)
    gerente.post(f'/gerente/clientes/{id_ana}/cuenta/desbloquear',
                 data={'csrf_token': token_csrf(gerente, f'/gerente/clientes/{id_ana}')})
    assert entrar(web, TEL_ANA).status_code == 302
    assert cliente(app_bd, TEL_ANA).intentos_fallidos == 0


def test_cliente_olvido_su_contrasena(app_bd, web):
    """El gerente quita la contraseña; el cliente vuelve a crear su cuenta y conserva su historial."""
    gerente = app_bd.test_client()
    iniciar_sesion(gerente, 'gerente.coyol')
    id_ana = cliente(app_bd, TEL_ANA).id_cliente
    gerente.post(f'/gerente/clientes/{id_ana}/cuenta/quitar-contrasena',
                 data={'csrf_token': token_csrf(gerente, f'/gerente/clientes/{id_ana}')})
    assert 'todavía no tiene cuenta' in entrar(web, TEL_ANA).get_data(as_text=True)
    assert crear(web, TEL_ANA, 'Nueva2026', nombre='Ana López Martínez').status_code == 302
    assert cliente(app_bd, TEL_ANA).id_cliente == id_ana


def test_cambiar_contrasena_cierra_las_otras_sesiones(app_bd):
    celular, computadora = app_bd.test_client(), app_bd.test_client()
    entrar(celular, TEL_ANA)
    entrar(computadora, TEL_ANA)
    r = celular.post('/mi-cuenta', data={'actual': 'Pizza2026', 'nueva': 'Nueva2026', 'confirmacion': 'Nueva2026',
                                         'csrf_token': token_csrf(celular, '/mi-cuenta')})
    assert r.status_code == 302
    assert celular.get('/pedido').status_code == 200          # quien la cambió sigue dentro
    assert computadora.get('/pedido').status_code == 302      # la otra sesión ya no vale


def test_salir_cierra_la_sesion_del_cliente(web):
    entrar(web, TEL_ANA)
    web.post('/mi-cuenta/salir', data={'csrf_token': token_csrf(web, '/mi-cuenta')})
    assert web.get('/pedido').status_code == 302


def test_la_contrasena_del_cliente_no_va_a_la_auditoria(app_bd, web, bd):
    crear(web, '2290004444')
    detalles = ' '.join(d for d, in bd.sql("SELECT detalle::text FROM auditoria WHERE entidad = 'cliente'"))
    assert '$argon2' not in detalles
