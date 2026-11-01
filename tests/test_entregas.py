"""Fase 5: RF-010 Control de entregas con firma digital, RN-013 entrega en dos pasos, GPS del
repartidor y mapa del cliente (boceto 5)."""
import base64

from sqlalchemy import select

from gpizza.extensiones import db
from gpizza.modelos import AsignacionEntrega, Empleado, Pedido
from gpizza.servicios import geo
from seed.datos_demo import FIRMA_DEMO
from tests.conftest import iniciar_sesion, token_csrf
from tests.test_pedidos import entrar_como_cliente, folio_de, formulario, pedido_por_folio

FIRMA_PNG = 'data:image/png;base64,' + base64.b64encode(FIRMA_DEMO).decode()


def entrega_en_camino(app):
    """Una entrega aceptada de la demo (Coyol): asignación, folio, código, repartidor y cliente."""
    with app.app_context():
        a = db.session.scalar(select(AsignacionEntrega).join(Pedido).where(
            AsignacionEntrega.estado == 'CONFIRMADA', Pedido.id_sucursal == 1).order_by(AsignacionEntrega.id_asignacion))
        return {'id': a.id_asignacion, 'folio': a.pedido.folio, 'codigo': a.pedido.codigo_entrega,
                'repartidor': a.repartidor.username, 'telefono': a.pedido.cliente.telefono}


def como_repartidor(app, web, e):
    iniciar_sesion(web, e['repartidor'])
    return token_csrf(web, '/repartidor/')


def post(web, url, token, **datos):
    return web.post(url, data=datos | {'csrf_token': token}, follow_redirects=True).get_data(as_text=True)


# ------------------------------------------------------------------------------ RN-013 / RF-010

def test_rn013_entrega_en_dos_pasos_con_codigo(app_bd, web):
    e = entrega_en_camino(app_bd)
    token = como_repartidor(app_bd, web, e)
    html = web.get('/repartidor/').get_data(as_text=True)
    assert 'Paso 1 · El cliente firma aquí' in html and 'data-mapa' in html

    html = post(web, f'/repartidor/asignaciones/{e["id"]}/entregar', token)               # sin paso 1: no
    assert 'Primero el cliente debe firmar o darte su código (RN-013)' in html
    incorrecto = '0000' if e['codigo'] != '0000' else '1111'
    html = post(web, f'/repartidor/asignaciones/{e["id"]}/confirmacion-cliente', token, codigo=incorrecto)
    assert 'El código no coincide' in html

    html = post(web, f'/repartidor/asignaciones/{e["id"]}/confirmacion-cliente', token, codigo=e['codigo'])
    assert 'Confirmación del cliente registrada' in html and 'Paso 2 · Marcar como entregado' in html
    html = post(web, f'/repartidor/asignaciones/{e["id"]}/entregar', token)
    assert 'Pedido entregado. Se guardaron la fecha y la hora.' in html

    pedido = pedido_por_folio(app_bd, e['folio'])
    assert pedido.estado == 'Entregado' and pedido.fecha_entrega is not None
    assert e['folio'] in web.get('/repartidor/historial').get_data(as_text=True)


def test_rf010_firma_digital_se_guarda_y_se_ve_en_el_detalle(app_bd, web):
    e = entrega_en_camino(app_bd)
    token = como_repartidor(app_bd, web, e)
    post(web, f'/repartidor/asignaciones/{e["id"]}/confirmacion-cliente', token, firma=FIRMA_PNG)
    post(web, f'/repartidor/asignaciones/{e["id"]}/entregar', token)
    with app_bd.app_context():
        assert bytes(db.session.get(AsignacionEntrega, e['id']).firma_digital) == FIRMA_DEMO

    gerente = app_bd.test_client()
    iniciar_sesion(gerente, 'gerente.coyol')
    html = gerente.get(f'/seguimiento/{e["folio"]}').get_data(as_text=True)
    assert 'alt="Firma del cliente"' in html and '(RN-013)' in html
    imagen = gerente.get(f'/seguimiento/{e["folio"]}/firma.png')
    assert imagen.status_code == 200 and imagen.mimetype == 'image/png' and imagen.data == FIRMA_DEMO


def test_firma_invalida_o_vacia_se_rechaza(app_bd, web):
    e = entrega_en_camino(app_bd)
    token = como_repartidor(app_bd, web, e)
    for firma in ('', 'data:image/png;base64,no-es-base64!!', 'data:image/png;base64,' + base64.b64encode(b'GIF89a').decode(),
                  'data:image/png;base64,' + base64.b64encode(FIRMA_DEMO + b'0' * 250_000).decode()):
        html = post(web, f'/repartidor/asignaciones/{e["id"]}/confirmacion-cliente', token, firma=firma)
        assert 'Pide al cliente que firme' in html
    with app_bd.app_context():
        assert db.session.get(AsignacionEntrega, e['id']).fecha_confirmacion_cliente is None


def test_otro_repartidor_no_confirma_entregas_ajenas(app_bd, web):
    e = entrega_en_camino(app_bd)
    otro = 'repartidor2.coyol' if e['repartidor'] == 'repartidor1.coyol' else 'repartidor1.coyol'
    iniciar_sesion(web, otro)
    token = token_csrf(web, '/repartidor/')
    assert 'no está asignada a ti' in post(web, f'/repartidor/asignaciones/{e["id"]}/confirmacion-cliente', token,
                                           codigo=e['codigo'])
    assert web.get(f'/seguimiento/{e["folio"]}/firma.png').status_code == 404


# ------------------------------------------------------------------------------ GPS y mapa del cliente

def test_gps_se_guarda_solo_durante_una_entrega(app_bd, web):
    e = entrega_en_camino(app_bd)
    token = como_repartidor(app_bd, web, e)
    r = web.post('/repartidor/ubicacion', data={'latitud': '19.160000', 'longitud': '-96.150000', 'csrf_token': token})
    assert r.status_code == 200 and r.get_json()['ok']
    with app_bd.app_context():
        yo = db.session.scalar(select(Empleado).where(Empleado.username == e['repartidor']))
        assert (float(yo.latitud_actual), float(yo.longitud_actual)) == (19.16, -96.15)
    r = web.post('/repartidor/ubicacion', data={'latitud': '999', 'longitud': '0', 'csrf_token': token})
    assert r.status_code == 400

    libre = app_bd.test_client()                       # repartidor sin entregas en camino
    iniciar_sesion(libre, 'repartidor1.pmoreno')
    r = libre.post('/repartidor/ubicacion', data={'latitud': '19.1', 'longitud': '-96.1',
                                                  'csrf_token': token_csrf(libre, '/repartidor/')})
    assert r.status_code == 409


def test_el_cliente_ve_al_repartidor_en_el_mapa(app_bd, web):
    e = entrega_en_camino(app_bd)
    repartidor = app_bd.test_client()
    token = como_repartidor(app_bd, repartidor, e)
    repartidor.post('/repartidor/ubicacion', data={'latitud': '19.170000', 'longitud': '-96.160000', 'csrf_token': token})

    entrar_como_cliente(web, e['telefono'])
    html = web.get(f'/mi-pedido/{e["folio"]}').get_data(as_text=True)
    assert 'Tu pedido va en camino' in html and 'data-mapa' in html and e['codigo'] in html
    d = web.get(f'/mi-pedido/{e["folio"]}/ubicacion').get_json()
    assert d['estado'] == 'En Camino' and (d['latitud'], d['longitud']) == (19.17, -96.16)
    assert d['repartidor'] and len(d['telefono']) == 10
    assert d['minutos'] == geo.minutos_estimados(19.17, -96.16, d['destino_latitud'], d['destino_longitud'])

    # Al entregar, el GPS deja de compartirse.
    post(repartidor, f'/repartidor/asignaciones/{e["id"]}/confirmacion-cliente', token, codigo=e['codigo'])
    post(repartidor, f'/repartidor/asignaciones/{e["id"]}/entregar', token)
    assert web.get(f'/mi-pedido/{e["folio"]}/ubicacion').get_json() == {'estado': 'Entregado'}


def test_otro_cliente_no_ve_la_ubicacion(app_bd, web):
    e = entrega_en_camino(app_bd)
    entrar_como_cliente(web, '2290001111')
    assert web.get(f'/mi-pedido/{e["folio"]}/ubicacion').status_code == 404


def test_usar_mi_ubicacion_guarda_el_domicilio_para_el_mapa(app_bd, web):
    entrar_como_cliente(web, '2290001111')
    datos = formulario(app_bd, web, nombre='Cliente Mapa', latitud='19.180000', longitud='-96.140000')
    pedido = pedido_por_folio(app_bd, folio_de(web.post('/pedido', data=datos)))
    assert (float(pedido.latitud_entrega), float(pedido.longitud_entrega)) == (19.18, -96.14)


def test_coordenadas_invalidas_se_ignoran(app_bd, web):
    entrar_como_cliente(web, '2290001111')
    datos = formulario(app_bd, web, nombre='Cliente Mapa', latitud='abc', longitud='-500')
    pedido = pedido_por_folio(app_bd, folio_de(web.post('/pedido', data=datos)))
    assert pedido.latitud_entrega is None


def test_minutos_estimados():
    assert geo.distancia_km(19.17, -96.16, 19.17, -96.16) == 0
    assert 3.5 < geo.distancia_km(19.1563, -96.1590, 19.1880, -96.1370) < 4.5   # Coyol → Centro, ~4 km
    assert geo.minutos_estimados(19.17, -96.16, 19.17, -96.16) == 1
