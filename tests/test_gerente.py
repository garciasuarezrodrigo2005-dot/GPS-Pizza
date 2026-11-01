"""Fase 6a: panel del gerente. Catálogo y precios (RF-002, RN-007), clientes (RF-005), personal
(CU-009, 009a, 009b, RF-006), códigos de descuento (RN-008), devoluciones (RF-011, RN-015) y
etiquetas QR (RF-009)."""
import re
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from gpizza.extensiones import db
from gpizza.modelos import CodigoDescuento, Devolucion, Empleado, Pedido, Producto
from tests.conftest import iniciar_sesion, token_csrf
from tests.test_ciclo import poner_hora
from tests.test_pedidos import entrar_como_cliente, folio_de, formulario, id_producto


@pytest.fixture
def gerente(app_bd):
    cliente_web = app_bd.test_client()
    iniciar_sesion(cliente_web, 'gerente.coyol')
    return cliente_web


def enviar(web, url, origen, **datos):
    return web.post(url, data=datos | {'csrf_token': token_csrf(web, origen)}, follow_redirects=True)


def empleado(app, usuario):
    with app.app_context():
        return db.session.scalar(select(Empleado).where(Empleado.username == usuario))


# ------------------------------------------------------------------------------ RN-007 catálogo

def test_rn007_el_gerente_cambia_precio_y_el_menu_lo_refleja(app_bd, gerente):
    pizza = id_producto(app_bd, 'Pepperoni', 'Mediana')
    html = enviar(gerente, f'/gerente/catalogo/{pizza}', '/gerente/catalogo', precio='155.50',
                  disponible='on', activo='on').get_data(as_text=True)
    assert 'Producto actualizado' in html
    cliente = app_bd.test_client()
    entrar_como_cliente(cliente)
    assert 'data-precio="155.50"' in cliente.get('/pedido').get_data(as_text=True)


def test_agotar_un_producto_lo_quita_del_pedido(app_bd, gerente):
    pizza = id_producto(app_bd, 'Pepperoni', 'Mediana')
    enviar(gerente, f'/gerente/catalogo/{pizza}', '/gerente/catalogo', precio='149', activo='on')   # sin "disponible"
    cliente = app_bd.test_client()
    entrar_como_cliente(cliente)
    assert 'está agotado' in cliente.post('/pedido', data=formulario(app_bd, cliente)).get_data(as_text=True)


def test_precio_invalido_y_cajero_sin_acceso(app_bd, gerente, web):
    pizza = id_producto(app_bd, 'Pepperoni', 'Mediana')
    html = enviar(gerente, f'/gerente/catalogo/{pizza}', '/gerente/catalogo', precio='-5', activo='on').get_data(as_text=True)
    assert 'precio válido' in html
    iniciar_sesion(web, 'cajero1.coyol')
    assert web.post(f'/gerente/catalogo/{pizza}', data={'precio': '1', 'csrf_token': token_csrf(web, '/cajero/')}).status_code == 403


def test_agregar_producto_con_codigo_qr(app_bd, gerente):
    html = enviar(gerente, '/gerente/catalogo/nuevo', '/gerente/catalogo', nombre='Pizza Choripán', descripcion='De la casa',
                  categoria='Pizza', tamano='Grande', precio='239').get_data(as_text=True)
    assert 'agregado al menú' in html
    with app_bd.app_context():
        nueva = db.session.scalar(select(Producto).where(Producto.nombre == 'Pizza Choripán'))
        assert nueva.codigo_qr_barras.startswith('YP') and nueva.precio == Decimal('239.00')
    respuesta = enviar(gerente, '/gerente/catalogo/nuevo', '/gerente/catalogo', nombre='Pizza Choripán', categoria='Pizza',
                       tamano='Grande', precio='239')
    assert respuesta.status_code == 422 and 'Ya existe ese producto' in respuesta.get_data(as_text=True)
    assert 'Las pizzas llevan tamaño' in enviar(gerente, '/gerente/catalogo/nuevo', '/gerente/catalogo', nombre='X',
                                                categoria='Pizza', tamano='', precio='10').get_data(as_text=True)


def test_rf009_qr_de_producto_y_hoja_de_etiquetas(app_bd, gerente):
    pizza = id_producto(app_bd, 'Pepperoni', 'Mediana')
    imagen = gerente.get(f'/gerente/catalogo/{pizza}/qr.png')
    assert imagen.status_code == 200 and imagen.data.startswith(b'\x89PNG')
    assert 'Etiquetas QR del menú' in gerente.get('/gerente/catalogo/etiquetas').get_data(as_text=True)


# ------------------------------------------------------------------------------ RF-005 clientes

def test_gerente_busca_y_edita_un_cliente(app_bd, gerente):
    html = gerente.get('/gerente/clientes?q=2295865835').get_data(as_text=True)
    id_cliente = re.search(r'/gerente/clientes/(\d+)', html).group(1)
    html = gerente.get(f'/gerente/clientes/{id_cliente}').get_data(as_text=True)
    assert 'Ana López Martínez' in html and 'Pedidos en Coyol (matriz)' in html
    html = enviar(gerente, f'/gerente/clientes/{id_cliente}', f'/gerente/clientes/{id_cliente}', nombre='Ana López M.',
                  direccion='Calle Nueva 10', colonia='Centro', codigo_postal='91700').get_data(as_text=True)
    assert 'Datos del cliente actualizados' in html and 'Calle Nueva 10' in html
    respuesta = enviar(gerente, f'/gerente/clientes/{id_cliente}', f'/gerente/clientes/{id_cliente}', nombre='',
                       direccion='', colonia='', codigo_postal='')
    assert respuesta.status_code == 422


# ------------------------------------------------------------------------------ CU-009 personal

def test_cu009a_alta_de_cajero_con_contrasena_temporal_vencida(app_bd, gerente):
    html = enviar(gerente, '/gerente/personal/nuevo', '/gerente/personal', puesto='Cajero', nombre='Nora', apellidos='Prueba',
                  telefono='2291112233', username='cajero3.coyol').get_data(as_text=True)
    temporal = re.search(r'contraseña temporal: (\w+)', html).group(1)
    nuevo = app_bd.test_client()
    respuesta = iniciar_sesion(nuevo, 'cajero3.coyol', temporal)
    assert respuesta.headers['Location'] == '/cambiar-contrasena'          # RN-018: debe elegir la suya


def test_cu009_alta_de_cocinero_sin_usuario(app_bd, gerente):
    html = enviar(gerente, '/gerente/personal/nuevo', '/gerente/personal', puesto='Cocinero', nombre='Toño', apellidos='Horno',
                  telefono='2291112244', username='').get_data(as_text=True)
    assert 'como cocinero (no inicia sesión)' in html
    with app_bd.app_context():
        assert db.session.scalar(select(Empleado.username).where(Empleado.nombre == 'Toño')) is None


def test_cu009_validaciones_y_usuario_repetido(app_bd, gerente):
    r = enviar(gerente, '/gerente/personal/nuevo', '/gerente/personal', puesto='Cajero', nombre='', apellidos='X',
               telefono='12', username='A')
    html = r.get_data(as_text=True)
    assert r.status_code == 422 and 'Escribe el nombre' in html and '10 dígitos' in html and 'minúsculas' in html
    html = enviar(gerente, '/gerente/personal/nuevo', '/gerente/personal', puesto='Cajero', nombre='Otro', apellidos='Cajero',
                  telefono='2291112255', username='cajero1.coyol').get_data(as_text=True)
    assert 'Ya existe un empleado con ese usuario' in html


def test_cu009_baja_impide_entrar_y_reactivar_lo_permite(app_bd, gerente):
    cajero = empleado(app_bd, 'cajero1.coyol')
    enviar(gerente, f'/gerente/personal/{cajero.id_empleado}/baja', '/gerente/personal')
    web = app_bd.test_client()
    assert 'dada de baja' in iniciar_sesion(web, 'cajero1.coyol').get_data(as_text=True)
    enviar(gerente, f'/gerente/personal/{cajero.id_empleado}/reactivar', '/gerente/personal')
    assert iniciar_sesion(web, 'cajero1.coyol').headers['Location'] == '/cajero/'


def test_cu009b_no_se_da_de_baja_a_un_repartidor_en_ruta(app_bd, gerente):
    with app_bd.app_context():
        en_ruta = db.session.scalar(select(Empleado).where(Empleado.username == 'repartidor1.coyol'))
    html = enviar(gerente, f'/gerente/personal/{en_ruta.id_empleado}/baja', '/gerente/personal').get_data(as_text=True)
    assert 'tiene entregas en curso' in html


def test_rn018_el_gerente_desbloquea_y_reinicia_contrasenas(app_bd, gerente):
    bloqueado = empleado(app_bd, 'repartidor3.coyol')
    assert 'desbloqueada' in enviar(gerente, f'/gerente/personal/{bloqueado.id_empleado}/desbloquear',
                                    '/gerente/personal').get_data(as_text=True)
    html = enviar(gerente, f'/gerente/personal/{bloqueado.id_empleado}/contrasena', '/gerente/personal').get_data(as_text=True)
    temporal = re.search(r'Contraseña temporal de repartidor3.coyol: (\w+)', html).group(1)
    assert iniciar_sesion(app_bd.test_client(), 'repartidor3.coyol', temporal).headers['Location'] == '/cambiar-contrasena'


def test_el_gerente_solo_administra_su_sucursal(app_bd, gerente):
    otro = empleado(app_bd, 'cajero1.pmoreno')
    assert gerente.post(f'/gerente/personal/{otro.id_empleado}/baja',
                        data={'csrf_token': token_csrf(gerente, '/gerente/personal')}).status_code == 404
    assert 'cajero1.pmoreno' not in gerente.get('/gerente/personal').get_data(as_text=True)


# ------------------------------------------------------------------------------ RN-008 códigos

def test_rn008_el_gerente_emite_un_codigo_que_sirve_una_vez(app_bd, gerente):
    html = enviar(gerente, '/gerente/descuentos/codigos', '/gerente/descuentos', tipo='MONTO', valor='40', dias='3',
                  codigo='feria40').get_data(as_text=True)
    assert 'Código FERIA40 emitido' in html and 'Vigente' in html
    with app_bd.app_context():
        assert db.session.scalar(select(CodigoDescuento.id_gerente).where(CodigoDescuento.codigo == 'FERIA40')) == \
            empleado(app_bd, 'gerente.coyol').id_empleado
    cliente = app_bd.test_client()
    entrar_como_cliente(cliente)
    pedido = folio_de(cliente.post('/pedido', data=formulario(app_bd, cliente, codigo='FERIA40')))
    assert pedido
    assert 'Usado' in gerente.get('/gerente/descuentos').get_data(as_text=True)


def test_rn008_validaciones_del_codigo(app_bd, gerente):
    html = enviar(gerente, '/gerente/descuentos/codigos', '/gerente/descuentos', tipo='PORCENTAJE', valor='150', dias='0',
                  codigo='BIENVENIDA10').get_data(as_text=True)
    assert 'El porcentaje va de 1 a 100' in html and 'La vigencia va de 1 a 90 días' in html
    html = enviar(gerente, '/gerente/descuentos/codigos', '/gerente/descuentos', tipo='PORCENTAJE', valor='5', dias='5',
                  codigo='BIENVENIDA10').get_data(as_text=True)
    assert 'Ese código ya existe' in html


# ------------------------------------------------------------------------------ RN-015 devoluciones

def _entregado_reciente(app):
    with app.app_context():
        p = db.session.scalar(select(Pedido).where(Pedido.estado == 'Entregado', Pedido.id_sucursal == 1,
                                                   Pedido.id_pedido.not_in(select(Devolucion.id_pedido)))
                              .order_by(Pedido.fecha_entrega.desc()))
        return p.id_pedido, p.folio, p.fecha_entrega


def test_rn015_devolucion_dentro_de_2_horas(app_bd, gerente):
    id_pedido, folio, entrega = _entregado_reciente(app_bd)
    poner_hora(app_bd, entrega + timedelta(minutes=30))
    assert folio in gerente.get('/gerente/descuentos').get_data(as_text=True)
    html = enviar(gerente, '/gerente/devoluciones', '/gerente/descuentos', id_pedido=id_pedido, motivo='Llegó fría',
                  accion='Reposición sin costo').get_data(as_text=True)
    assert 'Devolución registrada (RN-015)' in html
    html = enviar(gerente, '/gerente/devoluciones', '/gerente/descuentos', id_pedido=id_pedido, motivo='Otra vez',
                  accion='Otra acción').get_data(as_text=True)
    assert 'ya tiene una devolución' in html


def test_rn015_fuera_de_plazo_se_rechaza(app_bd, gerente):
    id_pedido, folio, entrega = _entregado_reciente(app_bd)
    poner_hora(app_bd, entrega + timedelta(hours=3))
    assert folio not in gerente.get('/gerente/descuentos').get_data(as_text=True).split('Registrar devolución')[1].split('Devoluciones registradas')[0]
    html = enviar(gerente, '/gerente/devoluciones', '/gerente/descuentos', id_pedido=id_pedido, motivo='Llegó fría',
                  accion='Reposición').get_data(as_text=True)
    assert 'RN-015: el plazo de devolución venció' in html
