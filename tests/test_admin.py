"""Fase 8 · CU-011 Administrar sucursales y gerentes, y la auditoría del Administrador (decisiones 19 y 20)."""
import re

import pytest
from sqlalchemy import func, select

from gpizza.extensiones import db
from gpizza.modelos import Empleado, Pedido, Sucursal
from tests.conftest import iniciar_sesion, token_csrf
from tests.test_pedidos import entrar_como_cliente


@pytest.fixture
def admin(app_bd):
    web = app_bd.test_client()
    iniciar_sesion(web, 'admin.yungla')
    return web


@pytest.fixture
def gerente(app_bd):
    web = app_bd.test_client()
    iniciar_sesion(web, 'gerente.coyol')
    return web


def _post(web, url, **datos):
    return web.post(url, data=datos | {'csrf_token': token_csrf(web, '/admin/')})


# ------------------------------------------------------------------------------ acceso

def test_el_administrador_entra_a_su_zona(app_bd):
    web = app_bd.test_client()
    assert iniciar_sesion(web, 'admin.yungla').headers['Location'] == '/admin/'
    html = web.get('/admin/').get_data(as_text=True)
    assert 'Toda la cadena' in html and 'Sucursales activas' in html


def test_el_gerente_ya_no_ve_la_auditoria_ni_la_zona_de_administracion(gerente):
    """Decisión 20: separación de funciones; el gerente no revisa su propia bitácora."""
    assert gerente.get('/gerente/auditoria').status_code == 404
    assert 'Auditoría' not in gerente.get('/gerente/').get_data(as_text=True)
    assert gerente.get('/admin/auditoria').status_code == 403


# ------------------------------------------------------------------------------ sucursales

def test_el_administrador_abre_una_sucursal_y_el_cliente_la_ve(app_bd, admin, web):
    r = _post(admin, '/admin/sucursales/nueva', nombre='Boca del Río', direccion='Blvd. Ávila Camacho 2000',
              ciudad='Boca del Río', estado='Veracruz', radio='4', apertura='12:00', cierre='23:00')
    assert r.status_code == 302 and '/admin/gerentes' in r.headers['Location']
    entrar_como_cliente(web)
    assert 'Boca del Río' in web.get('/pedido').get_data(as_text=True)          # RNF-005: solo datos


def test_sucursal_con_horario_invalido_o_nombre_repetido(admin):
    html = _post(admin, '/admin/sucursales/nueva', nombre='Nueva', direccion='Calle 1', ciudad='Veracruz',
                 radio='4', apertura='22:00', cierre='11:00').get_data(as_text=True)
    assert 'antes de la de cierre (RN-002)' in html
    html = _post(admin, '/admin/sucursales/nueva', nombre='Tejería', direccion='Calle 1', ciudad='Veracruz',
                 radio='4', apertura='11:00', cierre='22:00').get_data(as_text=True)
    assert 'Ya existe una sucursal con ese nombre' in html


def test_desactivar_una_sucursal_la_quita_de_la_lista_del_cliente(app_bd, admin, web):
    with app_bd.app_context():
        id_carranza = db.session.scalar(select(Sucursal.id_sucursal).where(Sucursal.nombre == 'Carranza'))
    _post(admin, f'/admin/sucursales/{id_carranza}/desactivar')
    entrar_como_cliente(web)
    assert '>\n        Carranza' not in web.get('/pedido').get_data(as_text=True)
    with app_bd.app_context():
        assert db.session.get(Sucursal, id_carranza).activa is False


def test_solo_el_administrador_cambia_sucursales_en_la_bd(bd):
    """trg_sucursal_permisos: aunque alguien se salte la app, el gerente no crea ni edita sucursales."""
    bd.como('Gerente', 'gerente.coyol')
    bd.debe_fallar('CU-011', "UPDATE sucursal SET hora_cierre = '23:00' WHERE nombre = 'Coyol (matriz)'")
    bd.como('Administrador', 'admin.yungla')
    bd.sql("UPDATE sucursal SET hora_cierre = '23:00' WHERE nombre = 'Coyol (matriz)'")


# ------------------------------------------------------------------------------ gerentes

def test_el_administrador_da_de_alta_un_gerente_con_contrasena_temporal(app_bd, admin):
    with app_bd.app_context():
        id_tejeria = db.session.scalar(select(Sucursal.id_sucursal).where(Sucursal.nombre == 'Tejería'))
    r = _post(admin, '/admin/gerentes/nuevo', id_sucursal=id_tejeria, nombre='Laura', apellidos='Mendoza Ruiz',
              telefono='2291234500', username='gerente2.tejeria')
    mensaje = admin.get(r.headers['Location']).get_data(as_text=True)
    temporal = re.search(r'contraseña temporal: (\w+)', mensaje).group(1)
    nuevo = app_bd.test_client()
    assert iniciar_sesion(nuevo, 'gerente2.tejeria', temporal).headers['Location'] == '/cambiar-contrasena'  # RN-018


def test_el_gerente_no_puede_dar_de_alta_gerentes(app_bd, gerente):
    """CU-009: el panel del gerente solo ofrece cajero, cocinero y repartidor; la BD también lo impide."""
    r = gerente.post('/gerente/personal/nuevo', data={
        'puesto': 'Gerente', 'nombre': 'Otro', 'apellidos': 'Gerente', 'telefono': '2291234501',
        'username': 'gerente2.coyol', 'csrf_token': token_csrf(gerente, '/gerente/personal')})
    assert r.status_code == 422 and 'Elige el puesto' in r.get_data(as_text=True)


def test_reglas_de_alta_en_la_bd(bd):
    bd.como('Gerente', 'gerente.coyol')
    alta = ("INSERT INTO empleado (id_sucursal, nombre, apellidos, telefono, puesto, username, password_hash, "
            "fecha_cambio_password) VALUES ({s}, 'X', 'Y', '2290000000', '{p}', '{u}', 'h', current_date)")
    bd.debe_fallar('solo el administrador', alta.format(s=1, p='Gerente', u='gerente9.coyol'))
    bd.debe_fallar('de su sucursal', alta.format(s=2, p='Cajero', u='cajero9.pmoreno'))
    bd.debe_fallar('desde la consola', alta.format(s='NULL', p='Administrador', u='admin.dos'))
    bd.como('Administrador', 'admin.yungla')
    bd.debe_fallar('el resto del personal', alta.format(s=1, p='Cajero', u='cajero9.coyol'))
    bd.sql(alta.format(s=1, p='Gerente', u='gerente9.coyol'))
    # RN-016: el administrador es de toda la cadena; ningún otro puesto queda sin sucursal.
    bd.como(None)
    bd.debe_fallar('rn016_administrador_sin_sucursal', alta.format(s=1, p='Administrador', u='admin.tres'))
    bd.debe_fallar('rn016_administrador_sin_sucursal', alta.format(s='NULL', p='Cajero', u='cajero.suelto'))


def test_el_administrador_desbloquea_a_un_gerente(app_bd, admin):
    bloqueado = app_bd.test_client()
    for _ in range(3):
        iniciar_sesion(bloqueado, 'gerente.pmoreno', 'Equivocada1')
    with app_bd.app_context():
        id_gerente = db.session.scalar(select(Empleado.id_empleado).where(Empleado.username == 'gerente.pmoreno'))
    _post(admin, f'/admin/gerentes/{id_gerente}/desbloquear')
    assert iniciar_sesion(app_bd.test_client(), 'gerente.pmoreno').headers['Location'] == '/gerente/'


def test_crear_admin_por_consola(app_bd):
    salida = app_bd.test_cli_runner().invoke(args=['crear-admin', '--usuario', 'admin.dos', '--nombre', 'Pablo',
                                                   '--apellidos', 'Ruiz', '--telefono', '2290000002']).output
    temporal = re.search(r'contraseña temporal: (\w+)', salida).group(1)
    web = app_bd.test_client()
    assert iniciar_sesion(web, 'admin.dos', temporal).headers['Location'] == '/cambiar-contrasena'


# ------------------------------------------------------------------------------ auditoría (RN-019, decisión 20)

def test_rn019_el_administrador_consulta_la_bitacora_de_toda_la_cadena(app_bd, admin):
    iniciar_sesion(app_bd.test_client(), 'cajero1.coyol')
    iniciar_sesion(app_bd.test_client(), 'cajero1.pmoreno')          # otra sucursal
    html = admin.get('/admin/auditoria?accion=LOGIN').get_data(as_text=True)
    assert 'cajero1.coyol' in html and 'cajero1.pmoreno' in html
    assert 'Editar' not in html and 'Borrar' not in html             # solo lectura
    html = admin.get('/admin/auditoria?accion=LOGIN&sucursal=1').get_data(as_text=True)
    assert 'cajero1.coyol' in html and 'cajero1.pmoreno' not in html
    html = admin.get('/admin/auditoria?usuario=cajero1.coyol').get_data(as_text=True)
    assert 'admin.yungla</td>' not in html


def test_rn019_muestra_los_cambios_de_estado_de_los_pedidos(app_bd, admin):
    with app_bd.app_context():
        dia = db.session.scalar(select(func.min(Pedido.fecha_registro)).where(Pedido.id_sucursal == 1)).date()
    html = admin.get(f'/admin/auditoria?desde={dia}&hasta={dia}&entidad=pedido').get_data(as_text=True)
    assert 'estado: Por Confirmar → En Preparación' in html or 'estado: En Preparación → Listo para Entrega' in html
