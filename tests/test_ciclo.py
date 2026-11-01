"""Fase 4: ciclo del pedido (RF-004), CU-002 Asignar Repartidor (RF-003), CU-003 Seguimiento,
CU-007 Notificaciones (RF-007), cancelación de acuerdo mutuo (RN-005), alertas (RN-006, RN-014)
y máximo 2 entregas por repartidor (RN-011)."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text, update

from gpizza import reloj
from gpizza.extensiones import db
from gpizza.modelos import AsignacionEntrega, Empleado, Notificacion, Pedido
from gpizza.servicios import ciclo
from tests.conftest import iniciar_sesion, token_csrf
from tests.test_pedidos import _cocinero, entrar_como_cliente, folio_de, formulario, pedido_por_folio


# ------------------------------------------------------------------------------ ayudantes

def poner_hora(app, momento: datetime):
    """Mueve el reloj de la app de prueba (y con él el de la BD) a `momento`."""
    with app.app_context():
        real = datetime.now(ZoneInfo(app.config['ZONA_HORARIA']))
        app.extensions['gpizza_desfase'] = momento - real


def adelantar(app, minutos: int):
    with app.app_context():
        poner_hora(app, reloj.ahora() + timedelta(minutes=minutos))


def en_preparacion(app, cuantos=1, origen=None):
    """Pedidos de Coyol en preparación, sin solicitud de cancelación (de los datos de demo)."""
    with app.app_context():
        consulta = select(Pedido).where(Pedido.estado == 'En Preparación', Pedido.cancelacion_solicitada_por.is_(None),
                                        Pedido.id_sucursal == 1).order_by(Pedido.id_pedido)
        if origen:
            consulta = consulta.where(Pedido.origen == origen)
        return [(p.id_pedido, p.folio) for p in db.session.scalars(consulta).all()[:cuantos]]


def asignaciones(app, id_pedido):
    with app.app_context():
        return [(a.estado, a.tipo, a.repartidor.username) for a in db.session.scalars(
            select(AsignacionEntrega).where(AsignacionEntrega.id_pedido == id_pedido)
            .order_by(AsignacionEntrega.id_asignacion))]


def marcar_listo(web, id_pedido):
    return web.post(f'/cajero/pedidos/{id_pedido}/listo', follow_redirects=True,
                    data={'csrf_token': token_csrf(web, '/cajero/pedidos')}).get_data(as_text=True)


def sin_repartidores_disponibles(app):
    with app.app_context():
        db.session.execute(update(Empleado).where(Empleado.puesto == 'Repartidor', Empleado.id_sucursal == 1)
                           .values(disponible=False))
        db.session.commit()


def pedido_confirmado_de_la_app(app):
    """Un cliente pide desde la app y cajero1 lo confirma. Devuelve (folio, navegador del cliente)."""
    cliente = app.test_client()
    entrar_como_cliente(cliente)
    folio = folio_de(cliente.post('/pedido', data=formulario(app, cliente)))
    cajero = app.test_client()
    iniciar_sesion(cajero, 'cajero1.coyol')
    cajero.post(f'/cajero/pedidos/{pedido_por_folio(app, folio).id_pedido}/confirmar',
                data={'tiempo': 60, 'id_cocinero': _cocinero(app), 'csrf_token': token_csrf(cajero, '/cajero/')})
    return folio, cliente


# ------------------------------------------------------------------------------ CU-002 asignación

def test_marcar_listo_asigna_repartidor_automaticamente(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    [(id_pedido, folio)] = en_preparacion(app_bd)
    html = marcar_listo(web, id_pedido)
    assert f'Pedido {folio} listo. Se asignó a' in html
    [(estado, tipo, repartidor)] = asignaciones(app_bd, id_pedido)
    assert (estado, tipo) == ('PENDIENTE', 'AUTOMATICA') and repartidor in ('repartidor1.coyol', 'repartidor2.coyol')
    with app_bd.app_context():   # CU-007: al repartidor le llega el aviso
        assert db.session.scalar(select(Notificacion).where(Notificacion.id_pedido == id_pedido,
                                                            Notificacion.tipo_evento == 'ASIGNACION'))


def test_repartidor_acepta_y_el_pedido_sale_en_camino(app_bd, web):
    folio, cliente = pedido_confirmado_de_la_app(app_bd)
    cajero = app_bd.test_client()
    iniciar_sesion(cajero, 'cajero1.coyol')
    marcar_listo(cajero, pedido_por_folio(app_bd, folio).id_pedido)
    [(_, _, asignado)] = asignaciones(app_bd, pedido_por_folio(app_bd, folio).id_pedido)
    otro = 'repartidor2.coyol' if asignado == 'repartidor1.coyol' else 'repartidor1.coyol'
    with app_bd.app_context():
        id_asignacion = db.session.scalar(select(AsignacionEntrega.id_asignacion).join(Pedido).where(Pedido.folio == folio))

    intruso = app_bd.test_client()                     # solo el asignado puede aceptar
    iniciar_sesion(intruso, otro)
    html = intruso.post(f'/repartidor/asignaciones/{id_asignacion}/aceptar', follow_redirects=True,
                        data={'csrf_token': token_csrf(intruso, '/repartidor/')}).get_data(as_text=True)
    assert 'no está asignada a ti' in html

    iniciar_sesion(web, asignado)
    assert folio in web.get('/repartidor/').get_data(as_text=True)
    html = web.post(f'/repartidor/asignaciones/{id_asignacion}/aceptar', follow_redirects=True,
                    data={'csrf_token': token_csrf(web, '/repartidor/')}).get_data(as_text=True)
    assert 'Entrega aceptada' in html and 'Tiempo en camino' in html
    pedido = pedido_por_folio(app_bd, folio)
    assert pedido.estado == 'En Camino'
    html = cliente.get(f'/mi-pedido/{folio}').get_data(as_text=True)
    assert 'Tu pedido va en camino' in html and pedido.codigo_entrega in html


def test_sin_repartidor_disponible_se_avisa_al_gerente(app_bd, web):
    sin_repartidores_disponibles(app_bd)
    iniciar_sesion(web, 'cajero1.coyol')
    [(id_pedido, folio)] = en_preparacion(app_bd)
    assert 'No hay repartidor disponible: se avisó al gerente' in marcar_listo(web, id_pedido)
    gerente = app_bd.test_client()
    iniciar_sesion(gerente, 'gerente.coyol')
    assert 'No hay repartidor disponible para el pedido ' + folio in gerente.get('/notificaciones/').get_data(as_text=True)


def test_rn011_nadie_recibe_un_tercer_pedido(app_bd, web):
    """repartidor1 y repartidor2 ya llevan 1 cada uno; con 2 pedidos más quedan llenos y el
    tercero espera (repartidor3 está bloqueado)."""
    iniciar_sesion(web, 'cajero1.coyol')
    tres = en_preparacion(app_bd, cuantos=3)
    for id_pedido, _ in tres[:2]:
        assert 'Se asignó a' in marcar_listo(web, id_pedido)
    assert 'No hay repartidor disponible' in marcar_listo(web, tres[2][0])
    with app_bd.app_context():
        for usuario in ('repartidor1.coyol', 'repartidor2.coyol'):
            carga = db.session.scalar(text(
                "SELECT count(*) FROM asignacion_entrega a JOIN empleado e ON e.id_empleado = a.id_repartidor "
                "WHERE e.username = :u AND a.estado IN ('PENDIENTE', 'CONFIRMADA')"), {'u': usuario})
            assert carga == 2


def test_cu002_fa2_si_no_acepta_en_5_minutos_se_reasigna(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    [(id_pedido, _)] = en_preparacion(app_bd)
    marcar_listo(web, id_pedido)
    [(_, _, primero)] = asignaciones(app_bd, id_pedido)
    adelantar(app_bd, 6)
    with app_bd.app_context():
        ciclo.revisar_tiempos(forzar=True)
    historial = asignaciones(app_bd, id_pedido)
    assert historial[0] == ('EXPIRADA', 'AUTOMATICA', primero)
    assert historial[1][0] == 'PENDIENTE' and historial[1][2] != primero   # no se le vuelve a ofrecer al mismo


def test_gerente_asigna_manualmente(app_bd, web):
    sin_repartidores_disponibles(app_bd)
    iniciar_sesion(web, 'cajero1.coyol')
    [(id_pedido, _)] = en_preparacion(app_bd)
    marcar_listo(web, id_pedido)                       # se queda sin repartidor
    with app_bd.app_context():
        db.session.execute(update(Empleado).where(Empleado.username == 'repartidor2.coyol').values(disponible=True))
        db.session.commit()
        r2 = db.session.scalar(select(Empleado.id_empleado).where(Empleado.username == 'repartidor2.coyol'))
    gerente = app_bd.test_client()
    iniciar_sesion(gerente, 'gerente.coyol')
    assert 'Repartidor…' in gerente.get('/gerente/pedidos?estado=Listo para Entrega').get_data(as_text=True)
    html = gerente.post(f'/gerente/pedidos/{id_pedido}/asignar', follow_redirects=True, data={
        'id_repartidor': r2, 'csrf_token': token_csrf(gerente, '/gerente/pedidos')}).get_data(as_text=True)
    assert 'Repartidor asignado' in html
    assert asignaciones(app_bd, id_pedido)[-1] == ('PENDIENTE', 'MANUAL', 'repartidor2.coyol')
    assert web.post(f'/gerente/pedidos/{id_pedido}/asignar', data={'csrf_token': token_csrf(web, '/cajero/')}).status_code == 403


def test_repartidor_cambia_su_disponibilidad(app_bd, web):
    iniciar_sesion(web, 'repartidor1.coyol')
    html = web.post('/repartidor/disponibilidad', follow_redirects=True,
                    data={'disponible': 'no', 'csrf_token': token_csrf(web, '/repartidor/')}).get_data(as_text=True)
    assert 'No disponible' in html
    with app_bd.app_context():
        assert db.session.scalar(select(Empleado.disponible).where(Empleado.username == 'repartidor1.coyol')) is False


# ------------------------------------------------------------------------------ RN-005 cancelación de acuerdo mutuo

def _cancelacion_cajero(cajero, folio, app, **datos):
    id_pedido = pedido_por_folio(app, folio).id_pedido
    return cajero.post(f'/cajero/pedidos/{id_pedido}/cancelacion', follow_redirects=True,
                       data=datos | {'csrf_token': token_csrf(cajero, '/cajero/pedidos')}).get_data(as_text=True)


def _cancelacion_cliente(cliente, folio, **datos):
    return cliente.post(f'/mi-pedido/{folio}/cancelacion', follow_redirects=True,
                        data=datos | {'csrf_token': token_csrf(cliente, f'/mi-pedido/{folio}')}).get_data(as_text=True)


def test_rn005_el_cliente_pide_y_el_cajero_acepta(app_bd, web):
    folio, cliente = pedido_confirmado_de_la_app(app_bd)
    assert 'Enviamos tu solicitud' in _cancelacion_cliente(cliente, folio, accion='solicitar', motivo='Ya no estaré en casa')
    assert pedido_por_folio(app_bd, folio).estado == 'En Preparación'      # una sola parte no basta
    iniciar_sesion(web, 'cajero1.coyol')
    assert 'El cliente pide cancelar' in web.get('/cajero/pedidos').get_data(as_text=True)
    assert 'de común acuerdo' in _cancelacion_cajero(web, folio, app_bd, accion='aceptar')
    assert pedido_por_folio(app_bd, folio).estado == 'Cancelado'


def test_rn005_el_cajero_pide_y_el_cliente_decide(app_bd, web):
    folio, cliente = pedido_confirmado_de_la_app(app_bd)
    iniciar_sesion(web, 'cajero1.coyol')
    _cancelacion_cajero(web, folio, app_bd, accion='solicitar', motivo='Se descompuso el horno')
    assert 'La sucursal pide cancelar tu pedido' in cliente.get(f'/mi-pedido/{folio}').get_data(as_text=True)
    assert 'Tu pedido continúa' in _cancelacion_cliente(cliente, folio, accion='rechazar')
    assert pedido_por_folio(app_bd, folio).estado == 'En Preparación'
    _cancelacion_cajero(web, folio, app_bd, accion='solicitar', motivo='Se descompuso el horno otra vez')
    assert 'Tu pedido fue cancelado' in _cancelacion_cliente(cliente, folio, accion='aceptar')
    assert pedido_por_folio(app_bd, folio).estado == 'Cancelado'


def test_rn005_pedido_telefonico_con_confirmacion_del_cliente(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    [(_, folio)] = en_preparacion(app_bd, origen='TELEFONO')
    html = _cancelacion_cajero(web, folio, app_bd, accion='telefono', motivo='El cliente llamó para cancelar')
    assert 'confirmó por teléfono' in html
    pedido = pedido_por_folio(app_bd, folio)
    assert pedido.estado == 'Cancelado' and pedido.cancelacion_confirmada_por_telefono


def test_rn005_pedido_de_la_app_no_se_cancela_por_telefono(app_bd, web):
    folio, _ = pedido_confirmado_de_la_app(app_bd)
    iniciar_sesion(web, 'cajero1.coyol')
    html = _cancelacion_cajero(web, folio, app_bd, accion='telefono', motivo='Intento de saltarse al cliente')
    assert 'el cliente debe aceptar la cancelación' in html
    assert pedido_por_folio(app_bd, folio).estado == 'En Preparación'


def test_rn005_en_camino_solo_cancela_el_gerente(app_bd, web):
    with app_bd.app_context():
        p = db.session.scalar(select(Pedido).where(Pedido.estado == 'En Camino', Pedido.id_sucursal == 1))
        id_pedido, folio = p.id_pedido, p.folio
    iniciar_sesion(web, 'cajero1.coyol')
    html = web.get('/cajero/pedidos?estado=En Camino').get_data(as_text=True)
    assert 'se requiere al gerente' in html and 'Cancelar…' not in html
    gerente = app_bd.test_client()
    iniciar_sesion(gerente, 'gerente.coyol')
    html = gerente.post(f'/gerente/pedidos/{id_pedido}/cancelar', follow_redirects=True, data={
        'motivo': 'El cliente no responde', 'csrf_token': token_csrf(gerente, '/gerente/pedidos')}).get_data(as_text=True)
    assert 'cancelado por el gerente' in html
    assert pedido_por_folio(app_bd, folio).estado == 'Cancelado'
    assert asignaciones(app_bd, id_pedido)[-1][0] == 'CANCELADA'


# ------------------------------------------------------------------------------ RN-006 / RN-014 alertas y CU-007

def test_rn006_alerta_de_45_minutos_en_lista_y_en_la_campana(app_bd, web):
    [(id_pedido, folio)] = en_preparacion(app_bd)
    with app_bd.app_context():
        preparacion = db.session.get(Pedido, id_pedido).fecha_preparacion
    poner_hora(app_bd, preparacion + timedelta(minutes=50))
    iniciar_sesion(web, 'cajero1.coyol')
    assert 'min en preparación (límite 45, RN-006)' in web.get('/cajero/pedidos').get_data(as_text=True)
    gerente = app_bd.test_client()
    iniciar_sesion(gerente, 'gerente.coyol')
    with app_bd.app_context():
        ciclo.revisar_tiempos(forzar=True)
    assert 'gp-insignia' in gerente.get('/notificaciones/campana').get_data(as_text=True)
    html = gerente.get('/notificaciones/').get_data(as_text=True)
    assert f'el pedido {folio} lleva más de 45 min en preparación' in html
    assert 'gp-insignia' not in gerente.get('/notificaciones/campana').get_data(as_text=True)  # ya se leyeron


def test_rn014_alerta_de_90_minutos_al_cajero(app_bd, web):
    with app_bd.app_context():
        p = db.session.scalar(select(Pedido).where(Pedido.estado == 'En Camino', Pedido.id_sucursal == 1)
                              .order_by(Pedido.fecha_en_camino))
        folio, en_camino = p.folio, p.fecha_en_camino
    poner_hora(app_bd, en_camino + timedelta(minutes=95))
    with app_bd.app_context():
        ciclo.revisar_tiempos(forzar=True)
    iniciar_sesion(web, 'cajero1.coyol')
    assert 'min en camino (límite 90, RN-014)' in web.get('/cajero/pedidos?estado=En Camino').get_data(as_text=True)
    assert f'el pedido {folio} lleva más de 90 min en camino' in web.get('/notificaciones/').get_data(as_text=True)


def test_cu007_el_cliente_ve_los_avisos_de_su_pedido(app_bd):
    folio, cliente = pedido_confirmado_de_la_app(app_bd)
    html = cliente.get(f'/mi-pedido/{folio}').get_data(as_text=True)
    assert f'Tu pedido {folio} fue confirmado. Tiempo estimado: 60 min.' in html


# ------------------------------------------------------------------------------ CU-003 seguimiento

def test_cu003_busqueda_por_folio_y_telefono(app_bd, web):
    folio, _ = pedido_confirmado_de_la_app(app_bd)
    iniciar_sesion(web, 'cajero1.coyol')
    assert folio in web.get(f'/seguimiento/?q={folio}').get_data(as_text=True)
    assert folio in web.get('/seguimiento/?q=229 586 5835').get_data(as_text=True)
    assert 'No existe un pedido' in web.get('/seguimiento/?q=YP-9999').get_data(as_text=True)   # FA-1
    html = web.get(f'/seguimiento/{folio}').get_data(as_text=True)
    assert 'Luis Pérez Domínguez' in html and 'Cocinero:' in html and 'En Preparación' in html


def test_cu003_el_motivo_de_cancelacion_se_ve(app_bd, web):
    folio, _ = pedido_confirmado_de_la_app(app_bd)
    gerente = app_bd.test_client()
    iniciar_sesion(gerente, 'gerente.coyol')
    gerente.post(f'/gerente/pedidos/{pedido_por_folio(app_bd, folio).id_pedido}/cancelar',
                 data={'motivo': 'Prueba de motivo visible', 'csrf_token': token_csrf(gerente, '/gerente/pedidos')})
    assert 'Motivo: Prueba de motivo visible' in gerente.get(f'/seguimiento/{folio}').get_data(as_text=True)   # FA-2


def test_cu003_cada_quien_ve_solo_lo_suyo(app_bd, web):
    folio, _ = pedido_confirmado_de_la_app(app_bd)       # es de Coyol
    iniciar_sesion(web, 'cajero1.pmoreno')
    assert web.get(f'/seguimiento/{folio}').status_code == 404
    repartidor = app_bd.test_client()
    iniciar_sesion(repartidor, 'repartidor1.coyol')       # no está asignado a este pedido
    assert repartidor.get(f'/seguimiento/{folio}').status_code == 404
