"""Decisión 21: dirección de destino en cada pedido, confirmación antes de enviar y comprobante del pedido."""
import pytest
from sqlalchemy import func, select

from gpizza.extensiones import db
from gpizza.modelos import Cliente, Pedido
from tests.test_pedidos import TEL_ANA, entrar_como_cliente, folio_de, formulario, pedido_por_folio

TEL_NUEVO = '2290005555'


def cliente(app, telefono) -> Cliente:
    with app.app_context():
        return db.session.scalar(select(Cliente).where(Cliente.telefono == telefono))


def contar_pedidos(app) -> int:
    with app.app_context():
        return db.session.scalar(select(func.count()).select_from(Pedido))


def test_la_cuenta_se_crea_sin_direccion_y_el_primer_pedido_la_guarda(app_bd, web):
    entrar_como_cliente(web, TEL_NUEVO)
    assert cliente(app_bd, TEL_NUEVO).direccion is None
    html = web.get('/pedido').get_data(as_text=True)
    assert '¿A dónde lo llevamos?' in html and 'Es tu primer pedido' in html
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web, direccion='Av. Independencia 100',
                                                           colonia='Centro', codigo_postal='91700')))
    assert pedido_por_folio(app_bd, folio).direccion_entrega == 'Av. Independencia 100, Col. Centro, C.P. 91700'
    assert cliente(app_bd, TEL_NUEVO).direccion == 'Av. Independencia 100'
    # En el siguiente pedido la dirección ya aparece escrita.
    assert 'value="Av. Independencia 100"' in web.get('/pedido').get_data(as_text=True)


def test_otro_destino_sin_cambiar_la_direccion_guardada(app_bd, web):
    """Mandar el pedido a otro lugar (p. ej. la oficina) sin tocar la dirección de la cuenta."""
    entrar_como_cliente(web)
    antes = cliente(app_bd, TEL_ANA).direccion
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web, direccion='Oficina: Blvd. Ávila Camacho 50',
                                                           colonia='Costa Verde', codigo_postal='94294')))
    pedido = pedido_por_folio(app_bd, folio)
    assert pedido.direccion_entrega.startswith('Oficina: Blvd. Ávila Camacho 50')
    assert cliente(app_bd, TEL_ANA).direccion == antes            # sin "Guardar como mi dirección"


def test_otro_destino_guardado_como_nueva_direccion(app_bd, web):
    entrar_como_cliente(web)
    web.post('/pedido', data=formulario(app_bd, web, direccion='Calle Nueva 7', guardar_direccion='si'))
    assert cliente(app_bd, TEL_ANA).direccion == 'Calle Nueva 7'


def test_revisar_muestra_la_confirmacion_de_envio_sin_guardar(app_bd, web):
    entrar_como_cliente(web)
    antes = contar_pedidos(app_bd)
    r = web.post('/pedido', data=formulario(app_bd, web, paso='revisar', codigo='BIENVENIDA10'))
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'Confirmación de envío' in html
    for texto in ('Enviar a', 'Ana López Martínez', 'Calle Pino Suárez 120', 'Desde', 'Coyol (matriz)',
                  'Pepperoni Mediana', '$ 298.00', 'BIENVENIDA10', '− $ 29.80', '$ 268.20',     # RN-008
                  'Pagas con', '$ 500.00', 'Tu cambio', '$ 231.80',                              # RN-010
                  'Confirmar y enviar pedido', 'Modificar pedido'):
        assert texto in html, texto
    assert contar_pedidos(app_bd) == antes                        # todavía no se envía


def test_revisar_con_errores_regresa_al_formulario(app_bd, web):
    entrar_como_cliente(web)
    r = web.post('/pedido', data=formulario(app_bd, web, paso='revisar', direccion=''))
    assert r.status_code == 422 and 'Escribe la dirección de entrega' in r.get_data(as_text=True)


def test_modificar_vuelve_al_formulario_con_lo_capturado(app_bd, web):
    entrar_como_cliente(web)
    r = web.post('/pedido', data=formulario(app_bd, web, paso='editar', direccion='Calle Editada 9'))
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'value="Calle Editada 9"' in html and 'data-hay-valores="si"' in html


def test_confirmar_y_enviar_registra_el_pedido(app_bd, web):
    entrar_como_cliente(web)
    r = web.post('/pedido', data=formulario(app_bd, web, paso='enviar'))
    assert r.status_code == 302 and '/mi-pedido/' in r.headers['Location']


def test_tu_pedido_muestra_el_comprobante_completo(app_bd, web):
    entrar_como_cliente(web)
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web)))
    html = web.get(f'/mi-pedido/{folio}').get_data(as_text=True)
    for texto in ('Comprobante de pedido', folio, 'Enviar a', 'Calle Pino Suárez 120', 'Desde', 'Coyol (matriz)',
                  'Pepperoni Mediana', 'Total', '$ 298.00', 'Efectivo', 'Tu cambio', '$ 202.00'):
        assert texto in html, texto


def test_la_pantalla_que_se_actualiza_sola_es_un_solo_bloque(app_bd, web):
    """Regresión: un </div> de más dejaba "¿Necesitas cancelar?" fuera del bloque que HTMX reemplaza
    cada 10 s, y se agregaba una copia nueva en cada actualización."""
    from html.parser import HTMLParser

    class Raices(HTMLParser):
        VACIOS = {'input', 'br', 'img', 'hr', 'meta', 'link'}

        def __init__(self):
            super().__init__()
            self.nivel, self.raices = 0, 0

        def handle_starttag(self, etiqueta, _atributos):
            if etiqueta in self.VACIOS:
                return
            if self.nivel == 0:
                self.raices += 1
            self.nivel += 1

        def handle_endtag(self, etiqueta):
            if etiqueta not in self.VACIOS:
                self.nivel -= 1

    entrar_como_cliente(web)
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web)))
    for _ in range(2):
        parcial = web.get(f'/mi-pedido/{folio}/estado').get_data(as_text=True)
        lector = Raices()
        lector.feed(parcial)
        assert lector.raices == 1 and lector.nivel == 0, 'el parcial debe ser un único <div id="estado-pedido">'
    assert web.get(f'/mi-pedido/{folio}').get_data(as_text=True).count('Cancelar pedido') == 1


# ------------------------------------------------------------------------------ decisión 22: mapa de sucursales

def test_el_pedido_trae_el_mapa_de_sucursales_con_su_ubicacion(app_bd, web):
    import json
    import re
    entrar_como_cliente(web)
    html = web.get('/pedido').get_data(as_text=True)
    datos = json.loads(re.search(r'<script type="application/json" id="datos-sucursales">(.*?)</script>', html, re.S).group(1))
    coyol = next(s for s in datos['sucursales'] if s['nombre'] == 'Coyol (matriz)')
    assert coyol['lat'] == 19.1563 and coyol['lng'] == -96.159 and coyol['abierta'] is True   # 15:00 de la demo
    assert datos['cliente'] == [19.1571, -96.1605]          # Ana: la recomendación se calcula en el navegador
    assert datos['elegida'] is False and 'js/sucursales.js' in html


@pytest.mark.hora_demo('09:00')
def test_fuera_de_horario_las_sucursales_salen_cerradas_en_el_mapa(app_bd, web):
    import json
    import re
    entrar_como_cliente(web)
    html = web.get('/pedido').get_data(as_text=True)
    datos = json.loads(re.search(r'id="datos-sucursales">(.*?)</script>', html, re.S).group(1))
    assert not any(s['abierta'] for s in datos['sucursales'])
