"""Fase 6b: CU-004 Reporte de desempeño (RF-008), CU-008 Exportar PDF/Excel, auditoría (RN-019)
y registro con QR (RF-009)."""
import io
from datetime import timedelta

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select

from gpizza import reloj
from gpizza.extensiones import db
from gpizza.modelos import Empleado, Pedido
from gpizza.servicios import auditoria, exportar
from tests.conftest import iniciar_sesion, token_csrf


@pytest.fixture
def gerente(app_bd):
    cliente_web = app_bd.test_client()
    iniciar_sesion(cliente_web, 'gerente.coyol')
    return cliente_web


def periodo(app, dias=14):
    with app.app_context():
        hoy = reloj.ahora().date()
    return (hoy - timedelta(days=dias)).isoformat(), hoy.isoformat()


# ------------------------------------------------------------------------------ CU-004

def test_cu004_reporte_con_indicadores_grafica_y_repartidores(app_bd, gerente):
    desde, hasta = periodo(app_bd)
    html = gerente.get(f'/gerente/reportes?desde={desde}&hasta={hasta}').get_data(as_text=True)
    for texto in ('Pedidos totales', 'Tiempo promedio de entrega', 'Cancelaciones', 'Devoluciones', 'Pizza más vendida',
                  'id="grafica-dias"', 'Detalle por repartidor', 'Carlos Gómez Arano', 'Generado en'):
        assert texto in html


def test_cu004_los_totales_cuadran_con_la_base_de_datos(app_bd, gerente):
    desde, hasta = periodo(app_bd, dias=3)
    with app_bd.app_context():
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        zona = ZoneInfo('America/Mexico_City')
        inicio = datetime.combine(date.fromisoformat(desde), datetime.min.time(), zona)
        fin = datetime.combine(date.fromisoformat(hasta) + timedelta(days=1), datetime.min.time(), zona)
        esperado = db.session.scalar(select(func.count()).select_from(Pedido).where(
            Pedido.id_sucursal == 1, Pedido.fecha_registro >= inicio, Pedido.fecha_registro < fin))
    respuesta = gerente.get(f'/gerente/reportes/exportar/xlsx?desde={desde}&hasta={hasta}')
    libro = load_workbook(io.BytesIO(respuesta.data))
    valores = {fila[0]: fila[1] for fila in libro['Resumen'].iter_rows(min_row=5, values_only=True)}
    assert valores['Pedidos totales'] == str(esperado)


def test_cu004_filtro_por_repartidor_y_sucursal_fija(app_bd, gerente):
    desde, hasta = periodo(app_bd)
    with app_bd.app_context():
        r1 = db.session.scalar(select(Empleado.id_empleado).where(Empleado.username == 'repartidor1.coyol'))
        ajeno = db.session.scalar(select(Empleado.id_empleado).where(Empleado.username == 'repartidor1.pmoreno'))
    html = gerente.get(f'/gerente/reportes?desde={desde}&hasta={hasta}&id_repartidor={r1}').get_data(as_text=True)
    assert 'Carlos Gómez Arano' in html and 'Daniel Sánchez Mora</td>' not in html
    html = gerente.get(f'/gerente/reportes?desde={desde}&hasta={hasta}&id_repartidor={ajeno}').get_data(as_text=True)
    assert 'Ricardo Flores' not in html                   # un repartidor de otra sucursal se ignora
    assert 'value="Coyol (matriz)" disabled' in html      # decisión 11: solo su sucursal


def test_cu004_fa1_periodo_sin_datos_y_fechas_invalidas(app_bd, gerente):
    html = gerente.get('/gerente/reportes?desde=2030-01-01&hasta=2030-01-07').get_data(as_text=True)
    assert 'Prueba ampliando el rango de fechas (CU-004 FA-1)' in html
    html = gerente.get('/gerente/reportes?desde=ayer&hasta=hoy', follow_redirects=True).get_data(as_text=True)
    assert 'Escribe las fechas con el calendario' in html


def test_cu004_se_genera_en_menos_de_5_segundos(app_bd):
    from gpizza.servicios import reportes
    with app_bd.app_context():
        hoy = reloj.ahora().date()
        r = reportes.generar(1, reportes.Filtros(hoy - timedelta(days=365), hoy))
    assert r.total > 0 and r.segundos < 5


def test_solo_el_gerente_ve_reportes(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    assert web.get('/gerente/reportes').status_code == 403
    assert web.get('/gerente/reportes/exportar/pdf').status_code == 403


# ------------------------------------------------------------------------------ CU-008

def test_cu008_exportar_pdf(app_bd, gerente):
    desde, hasta = periodo(app_bd)
    r = gerente.get(f'/gerente/reportes/exportar/pdf?desde={desde}&hasta={hasta}')
    assert r.status_code == 200 and r.mimetype == 'application/pdf' and r.data.startswith(b'%PDF')
    assert f'reporte_coyol_matriz_{desde}_{hasta}.pdf' in r.headers['Content-Disposition']


def test_cu008_exportar_excel(app_bd, gerente):
    desde, hasta = periodo(app_bd)
    r = gerente.get(f'/gerente/reportes/exportar/xlsx?desde={desde}&hasta={hasta}')
    assert r.status_code == 200 and r.data.startswith(b'PK')
    libro = load_workbook(io.BytesIO(r.data))
    assert libro.sheetnames == ['Resumen', 'Pedidos por día', 'Por repartidor']
    assert libro['Pedidos por día']._charts                      # la gráfica va dentro del Excel
    assert libro['Por repartidor']['A2'].value                    # al menos un repartidor


def test_cu008_fa2_si_falla_la_exportacion_se_conservan_los_filtros(app_bd, gerente, monkeypatch):
    def falla(*_args, **_kwargs):
        raise RuntimeError('disco lleno')
    monkeypatch.setattr(exportar, 'pdf', falla)
    r = gerente.get('/gerente/reportes/exportar/pdf?desde=2026-10-20&hasta=2026-10-25')
    assert r.status_code == 302 and 'desde=2026-10-20' in r.headers['Location']
    assert 'No se pudo generar el archivo' in gerente.get(r.headers['Location']).get_data(as_text=True)


# ------------------------------------------------------------------------------ RN-019 auditoría

def test_resumen_de_detalle():
    assert auditoria.resumen({'estado': {'antes': 'En Camino', 'despues': 'Entregado'}}) == 'estado: En Camino → Entregado'
    assert auditoria.resumen({'nuevo': {'folio': 'YP-0001', 'estado': 'Por Confirmar', 'otro': 1}}) == \
        'folio: YP-0001, estado: Por Confirmar'
    assert auditoria.resumen(None) == ''
    assert auditoria.resumen({'fecha_fin': {'antes': None, 'despues': '2026-11-01T17:31:24.2099-06:00'}}) == \
        'fecha_fin: — → 17:31'


# ------------------------------------------------------------------------------ RF-009 QR

def test_rf009_comanda_con_qr_del_folio_y_busqueda_por_escaneo(app_bd, web):
    with app_bd.app_context():
        folio = db.session.scalar(select(Pedido.folio).where(Pedido.estado == 'En Preparación', Pedido.id_sucursal == 1))
    iniciar_sesion(web, 'cajero1.coyol')
    html = web.get(f'/seguimiento/{folio}/comanda').get_data(as_text=True)
    assert folio in html and f'/seguimiento/{folio}/qr.png' in html
    imagen = web.get(f'/seguimiento/{folio}/qr.png')
    assert imagen.mimetype == 'image/png' and imagen.data.startswith(b'\x89PNG')
    assert f'/seguimiento/{folio}' in web.get(f'/seguimiento/?q={folio}').get_data(as_text=True)   # el lector "teclea" el folio


def test_rf009_nuevo_pedido_permite_escanear_productos(app_bd, web):
    iniciar_sesion(web, 'cajero1.coyol')
    html = web.get('/cajero/nuevo?telefono=2295865835').get_data(as_text=True)
    assert 'id="escaner-codigo"' in html and 'data-qr="YP0000' in html and 'html5-qrcode.min.js' in html
