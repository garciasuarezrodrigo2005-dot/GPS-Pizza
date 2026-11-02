"""Fase 3: CU-001 Registrar Pedido (RF-001), CU-010 Menú (RF-002), CU-005 Clientes (RF-005),
confirmación y rechazo del cajero, descuentos (RN-008), pago y cambio (RN-009, RN-010)."""
import re
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from gpizza.extensiones import db
from gpizza.modelos import Cliente, CodigoDescuento, Notificacion, Pedido, Producto
from tests.conftest import iniciar_sesion, token_csrf

TEL_ANA = '2295865835'      # clienta de la demo (Coyol)
TEL_NUEVO = '2290001111'    # no existe en la demo


# ------------------------------------------------------------------------------ ayudantes

def id_producto(app, nombre, tamano=None):
    with app.app_context():
        return db.session.scalar(select(Producto.id_producto).where(Producto.nombre == nombre,
                                                                     Producto.tamano.is_not_distinct_from(tamano)))


def id_sucursal(app, nombre='Coyol (matriz)'):
    with app.app_context():
        return db.session.scalar(text('SELECT id_sucursal FROM sucursal WHERE nombre = :n'), {'n': nombre})


def entrar_como_cliente(web, telefono=TEL_ANA, contrasena='Pizza2026'):
    """Entra con la cuenta del cliente (decisión 18); si el teléfono aún no tiene cuenta, la crea."""
    respuesta = web.post('/entrar', data={'telefono': telefono, 'contrasena': contrasena,
                                          'csrf_token': token_csrf(web, '/crear-cuenta')})
    if respuesta.status_code != 302:
        web.post('/crear-cuenta', data={
            'telefono': telefono, 'nombre': 'Cliente Prueba', 'direccion': 'Calle Prueba 1', 'colonia': 'Centro',
            'codigo_postal': '91700', 'contrasena': contrasena, 'confirmacion': contrasena,
            'csrf_token': token_csrf(web, '/crear-cuenta')})


def formulario(app, web, **cambios):
    """Formulario de pedido válido: 2 Pepperoni medianas ($298), efectivo, paga con $500."""
    datos = {'csrf_token': token_csrf(web, '/pedido'), 'nombre': 'Ana López Martínez',
             'direccion': 'Calle Pino Suárez 120', 'colonia': 'Las Palmas', 'codigo_postal': '91750',
             'id_sucursal': id_sucursal(app), f'cantidad_{id_producto(app, "Pepperoni", "Mediana")}': 2,
             'forma_pago': 'Efectivo', 'monto_recibido': '500'}
    return datos | cambios


def pedido_por_folio(app, folio):
    with app.app_context():
        return db.session.scalar(select(Pedido).where(Pedido.folio == folio))


def folio_de(respuesta):
    return re.search(r'/mi-pedido/(YP-\d+)', respuesta.headers['Location']).group(1)


# ------------------------------------------------------------------------------ CU-001 desde la app

def test_cliente_registra_su_pedido_y_queda_por_confirmar(app_bd, web):
    entrar_como_cliente(web)
    html = web.get('/pedido').get_data(as_text=True)
    assert 'Ana López Martínez' in html and 'Pepperoni' in html            # CU-005 autocompleta / CU-010
    respuesta = web.post('/pedido', data=formulario(app_bd, web))
    assert respuesta.status_code == 302
    folio = folio_de(respuesta)
    pedido = pedido_por_folio(app_bd, folio)
    assert pedido.estado == 'Por Confirmar' and pedido.origen == 'APP'
    assert (pedido.subtotal, pedido.total, pedido.cambio) == (Decimal('298.00'), Decimal('298.00'), Decimal('202.00'))
    assert pedido.direccion_entrega == 'Calle Pino Suárez 120, Col. Las Palmas, C.P. 91750'  # copia completa
    html = web.get(f'/mi-pedido/{folio}').get_data(as_text=True)
    assert 'Pedido enviado' in html and 'Registrado en' in html            # RNF-001 visible
    with app_bd.app_context():                                              # CU-007: aviso al cajero
        assert db.session.scalar(select(Notificacion).where(Notificacion.id_pedido == pedido.id_pedido,
                                                            Notificacion.rol_destino == 'Cajero'))


@pytest.mark.parametrize('cambios, mensaje', [
    ({'nombre': '  '}, 'Escribe el nombre'),                                                    # RN-004
    ({'direccion': ''}, 'Escribe la dirección'),                                                # RN-004
    ({'monto_recibido': '200'}, 'El pago debe cubrir el total de $298.00 (RN-010)'),            # RN-010
    ({'monto_recibido': 'mucho'}, 'solo números'),
    ({'forma_pago': 'Bitcoin'}, 'RN-009'),                                                      # RN-009
    ({'codigo': 'VENCIDO20'}, 'no está vigente'),                                               # RN-008
    ({'codigo': 'USADO15'}, 'ya fue usado'),                                                    # RN-008
    ({'codigo': 'INVENTADO'}, 'no existe'),                                                     # RN-008
])
def test_errores_del_pedido_se_explican_en_espanol(app_bd, web, cambios, mensaje):
    entrar_como_cliente(web)
    respuesta = web.post('/pedido', data=formulario(app_bd, web, **cambios))
    assert respuesta.status_code == 422
    assert mensaje in respuesta.get_data(as_text=True)


def test_rn001_subtotal_minimo(app_bd, web):
    entrar_como_cliente(web)
    datos = formulario(app_bd, web)
    datos[f'cantidad_{id_producto(app_bd, "Pepperoni", "Mediana")}'] = 0
    datos[f'cantidad_{id_producto(app_bd, "Pepperoni", "Personal")}'] = 1   # $89
    html = web.post('/pedido', data=datos).get_data(as_text=True)
    assert 'te faltan $11.00 (RN-001)' in html


def test_rn003_limites_de_productos(app_bd, web):
    entrar_como_cliente(web)
    datos = formulario(app_bd, web)
    datos[f'cantidad_{id_producto(app_bd, "Pepperoni", "Mediana")}'] = 6
    assert 'Máximo 5 unidades' in web.post('/pedido', data=datos).get_data(as_text=True)
    with app_bd.app_context():
        once = db.session.scalars(select(Producto.id_producto).where(Producto.disponible).limit(11)).all()
    datos = formulario(app_bd, web) | {f'cantidad_{p}': 1 for p in once}
    assert 'Máximo 10 productos distintos' in web.post('/pedido', data=datos).get_data(as_text=True)


def test_producto_agotado_no_se_acepta(app_bd, web):
    entrar_como_cliente(web)
    datos = formulario(app_bd, web) | {f'cantidad_{id_producto(app_bd, "Yungla Especial", "Familiar")}': 1}
    assert 'está agotado' in web.post('/pedido', data=datos).get_data(as_text=True)


@pytest.mark.hora_demo('09:30')
def test_rn002_fuera_de_horario(app_bd, web):
    entrar_como_cliente(web)
    html = web.post('/pedido', data=formulario(app_bd, web)).get_data(as_text=True)
    assert 'Los pedidos se reciben de 11:00 a 22:00 h (RN-002)' in html


def test_rn007_el_precio_lo_pone_el_servidor(app_bd, web):
    """Aunque alguien mande precios o totales inventados, se usan los de la base de datos."""
    entrar_como_cliente(web)
    datos = formulario(app_bd, web, precio='1', subtotal='1', total='1', descuento='290')
    folio = folio_de(web.post('/pedido', data=datos))
    pedido = pedido_por_folio(app_bd, folio)
    assert (pedido.total, pedido.descuento) == (Decimal('298.00'), Decimal('0.00'))


def test_rn008_codigo_de_descuento(app_bd, web):
    entrar_como_cliente(web)
    r = web.post('/pedido/codigo', data={'codigo': 'bienvenida10', 'subtotal': '298',
                                         'csrf_token': token_csrf(web, '/pedido')}).get_json()
    assert r['ok'] and r['descuento'] == '29.80'
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web, codigo='BIENVENIDA10')))
    pedido = pedido_por_folio(app_bd, folio)
    assert (pedido.descuento, pedido.total, pedido.cambio) == (Decimal('29.80'), Decimal('268.20'), Decimal('231.80'))
    with app_bd.app_context():
        assert db.session.scalar(select(CodigoDescuento.usado).where(CodigoDescuento.codigo == 'BIENVENIDA10'))
    html = web.post('/pedido', data=formulario(app_bd, web, codigo='BIENVENIDA10')).get_data(as_text=True)
    assert 'ya fue usado' in html


def test_cliente_solo_ve_sus_pedidos(app_bd, web):
    entrar_como_cliente(web)
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web)))
    otro = app_bd.test_client()
    entrar_como_cliente(otro, '2291234567')
    assert otro.get(f'/mi-pedido/{folio}').status_code == 404


def test_cliente_cancela_mientras_esta_por_confirmar(app_bd, web):
    entrar_como_cliente(web)
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web)))
    web.post(f'/mi-pedido/{folio}/cancelar', data={'csrf_token': token_csrf(web, f'/mi-pedido/{folio}')})
    assert pedido_por_folio(app_bd, folio).estado == 'Cancelado'


def test_cliente_nuevo_queda_registrado_con_su_pedido(app_bd, web):
    """CU-001 FA-1 / CU-005: el teléfono no existía; crea su cuenta y su pedido actualiza su perfil."""
    entrar_como_cliente(web, TEL_NUEVO)
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web, nombre='Laura Prueba')))
    with app_bd.app_context():
        cliente = db.session.scalar(select(Cliente).where(Cliente.telefono == TEL_NUEVO))
        assert cliente.nombre == 'Laura Prueba' and cliente.direccion == 'Calle Pino Suárez 120'
    assert pedido_por_folio(app_bd, folio).id_cliente == cliente.id_cliente


def test_telefono_invalido_no_entra(web):
    respuesta = web.post('/entrar', data={'telefono': '229-ABC', 'contrasena': 'Pizza2026',
                                          'csrf_token': token_csrf(web, '/')})
    assert '10 dígitos' in respuesta.get_data(as_text=True)


# ------------------------------------------------------------------------------ cajero: confirmar / rechazar

def _pedido_nuevo_de_la_app(app_bd):
    cliente = app_bd.test_client()
    entrar_como_cliente(cliente)
    return folio_de(cliente.post('/pedido', data=formulario(app_bd, cliente))), cliente


def _cocinero(app, sucursal='Coyol (matriz)'):
    with app.app_context():
        return db.session.scalar(text("SELECT id_empleado FROM empleado JOIN sucursal s USING (id_sucursal) "
                                      "WHERE puesto = 'Cocinero' AND s.nombre = :s LIMIT 1"), {'s': sucursal})


def test_cajero_confirma_con_tiempo_y_cocinero(app_bd, web):
    folio, cliente = _pedido_nuevo_de_la_app(app_bd)
    iniciar_sesion(web, 'cajero1.coyol')
    assert folio in web.get('/cajero/').get_data(as_text=True)
    pedido = pedido_por_folio(app_bd, folio)
    respuesta = web.post(f'/cajero/pedidos/{pedido.id_pedido}/confirmar', follow_redirects=True, data={
        'tiempo': 45, 'id_cocinero': _cocinero(app_bd), 'csrf_token': token_csrf(web, '/cajero/')})
    assert 'Pedido confirmado' in respuesta.get_data(as_text=True)
    with app_bd.app_context():
        pedido = db.session.scalar(select(Pedido).where(Pedido.folio == folio))
        assert pedido.estado == 'En Preparación' and pedido.tiempo_estimado_min == 45
        assert pedido.cajero.username == 'cajero1.coyol' and pedido.cocinero.puesto == 'Cocinero'
    html = cliente.get(f'/mi-pedido/{folio}').get_data(as_text=True)          # barra de progreso del cliente
    assert 'Pedido confirmado' in html and '45 min' in html


def test_cajero_no_confirma_sin_cocinero_ni_dos_veces(app_bd, web):
    folio, _ = _pedido_nuevo_de_la_app(app_bd)
    iniciar_sesion(web, 'cajero1.coyol')
    id_pedido = pedido_por_folio(app_bd, folio).id_pedido
    url = f'/cajero/pedidos/{id_pedido}/confirmar'
    html = web.post(url, data={'tiempo': 60, 'csrf_token': token_csrf(web, '/cajero/')}, follow_redirects=True).get_data(as_text=True)
    assert 'Elige el cocinero' in html
    datos = {'tiempo': 60, 'id_cocinero': _cocinero(app_bd), 'csrf_token': token_csrf(web, '/cajero/')}
    web.post(url, data=datos)
    html = web.post(url, data=datos, follow_redirects=True).get_data(as_text=True)
    assert 'ya fue atendido' in html


def test_cajero_rechaza_con_motivo_y_el_cliente_lo_ve(app_bd, web):
    folio, cliente = _pedido_nuevo_de_la_app(app_bd)
    iniciar_sesion(web, 'cajero1.coyol')
    url = f'/cajero/pedidos/{pedido_por_folio(app_bd, folio).id_pedido}/rechazar'
    html = web.post(url, data={'motivo': '', 'csrf_token': token_csrf(web, '/cajero/')}, follow_redirects=True).get_data(as_text=True)
    assert 'Escribe el motivo' in html
    web.post(url, data={'motivo': 'Nos quedamos sin queso.', 'csrf_token': token_csrf(web, '/cajero/')})
    assert pedido_por_folio(app_bd, folio).estado == 'Rechazado'
    assert 'Nos quedamos sin queso.' in cliente.get(f'/mi-pedido/{folio}').get_data(as_text=True)


def test_cajero_no_atiende_pedidos_de_otra_sucursal(app_bd, web):
    folio, _ = _pedido_nuevo_de_la_app(app_bd)        # es de Coyol
    iniciar_sesion(web, 'cajero1.pmoreno')
    html = web.post(f'/cajero/pedidos/{pedido_por_folio(app_bd, folio).id_pedido}/confirmar', follow_redirects=True,
                    data={'tiempo': 45, 'id_cocinero': _cocinero(app_bd, 'Puente Moreno'),
                          'csrf_token': token_csrf(web, '/cajero/')}).get_data(as_text=True)
    assert 'no existe en tu sucursal' in html
    assert folio not in web.get('/cajero/').get_data(as_text=True)


def test_aviso_de_pedidos_nuevos_al_cajero(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    conteo = web.get('/cajero/').get_data(as_text=True).count('class="gp-tarjeta gp-tarjeta-pedido"')
    _pedido_nuevo_de_la_app(app_bd)
    html = web.get(f'/cajero/por-confirmar/aviso?mostrados={conteo}').get_data(as_text=True)
    assert '1 pedido nuevo por confirmar' in html


# ------------------------------------------------------------------------------ cajero: pedido por teléfono y clientes

def test_cajero_registra_pedido_telefonico_de_cliente_nuevo(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    assert 'Cliente nuevo' in web.get(f'/cajero/nuevo?telefono={TEL_NUEVO}').get_data(as_text=True)
    datos = {'csrf_token': token_csrf(web, f'/cajero/nuevo?telefono={TEL_NUEVO}'), 'telefono': TEL_NUEVO,
             'nombre': 'Pedro Teléfono', 'direccion': 'Av. Independencia 5', 'origen': 'TELEFONO',
             f'cantidad_{id_producto(app_bd, "Hawaiana", "Grande")}': 1, 'forma_pago': 'Tarjeta',
             'referencia_pago': '****4321', 'tiempo': 90, 'id_cocinero': _cocinero(app_bd)}
    respuesta = web.post('/cajero/nuevo', data=datos, follow_redirects=True)
    assert 'ya está en preparación' in respuesta.get_data(as_text=True)
    with app_bd.app_context():
        pedido = db.session.scalar(select(Pedido).join(Cliente).where(Cliente.telefono == TEL_NUEVO))
        assert pedido.estado == 'En Preparación' and pedido.origen == 'TELEFONO'
        assert pedido.cajero.username == 'cajero1.coyol' and pedido.referencia_pago == '****4321'
        assert pedido.codigo_entrega and len(pedido.codigo_entrega) == 4


def test_cajero_registra_cliente_y_valida_rn004(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    token = token_csrf(web, '/cajero/clientes/nuevo')
    html = web.post('/cajero/clientes/nuevo', data={'csrf_token': token, 'nombre': 'X', 'telefono': '123',
                                                     'direccion': ''}).get_data(as_text=True)
    assert '10 dígitos' in html and 'Escribe la dirección' in html
    respuesta = web.post('/cajero/clientes/nuevo', follow_redirects=True, data={
        'csrf_token': token, 'nombre': 'Marta Ruiz', 'telefono': TEL_NUEVO, 'direccion': 'Calle 5 #10'})
    assert 'Marta Ruiz' in respuesta.get_data(as_text=True)
    html = web.post('/cajero/clientes/nuevo', data={'csrf_token': token, 'nombre': 'Otra', 'telefono': TEL_NUEVO,
                                                     'direccion': 'Calle 1'}).get_data(as_text=True)
    assert 'Ya existe un cliente con ese teléfono' in html


def test_rnf003_busqueda_de_clientes_resiste_inyeccion_sql(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    html = web.get("/cajero/clientes?q=' OR '1'='1").get_data(as_text=True)
    assert 'No se encontraron clientes' in html


def test_repartidor_no_entra_a_pantallas_del_cajero(app_bd, web):
    iniciar_sesion(web, 'repartidor1.coyol')
    assert web.get('/cajero/nuevo').status_code == 403
