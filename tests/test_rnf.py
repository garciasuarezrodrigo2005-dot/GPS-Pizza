"""Fase 7: evidencias automáticas de los requisitos no funcionales.

RNF-003  cada ruta del personal exige sesión y el rol correcto (se recorren TODAS las rutas de la app).
RNF-002  ninguna ruta responde con error 500, ni siquiera con datos inválidos.
RNF-005  una sucursal nueva funciona solo con datos.
RNF-006  cada módulo del código explica para qué sirve.
"""
import ast
import re
from pathlib import Path

import pytest
from sqlalchemy import select, text

from gpizza.extensiones import db
from gpizza.modelos import Pedido, Sucursal
from tests.conftest import iniciar_sesion, token_csrf
from tests.test_pedidos import entrar_como_cliente, folio_de, formulario, id_producto

RAIZ = Path(__file__).resolve().parent.parent

# Qué roles pueden usar cada grupo de rutas. Todo lo demás debe responder 403.
PERMISOS = [
    (r'^/cajero/', {'Cajero'}),
    (r'^/repartidor/', {'Repartidor'}),
    (r'^/gerente/', {'Gerente'}),
    (r'^/admin/', {'Administrador'}),
    (r'^/notificaciones/', {'Cajero', 'Repartidor', 'Gerente'}),
    (r'^/seguimiento/<folio>/comanda$', {'Cajero', 'Gerente'}),
    (r'^/seguimiento/<folio>', {'Cajero', 'Repartidor', 'Gerente'}),
    (r'^/seguimiento/$', {'Cajero', 'Gerente'}),
]
USUARIOS = {'Cajero': 'cajero1.coyol', 'Repartidor': 'repartidor1.coyol', 'Gerente': 'gerente.coyol',
            'Administrador': 'admin.yungla'}
VALORES = {'int': '1', 'default': 'YP-0001'}


def rutas_protegidas(app):
    """(método, url de ejemplo, roles permitidos) para cada ruta del personal."""
    for regla in app.url_map.iter_rules():
        permitidos = next((roles for patron, roles in PERMISOS if re.search(patron, regla.rule)), None)
        if permitidos is None:
            continue
        url = regla.rule
        for argumento in regla.arguments:
            tipo = 'int' if f'<int:{argumento}>' in url else 'default'
            valor = {'accion': 'editar', 'formato': 'pdf'}.get(argumento, VALORES[tipo])
            url = re.sub(rf'<(?:\w+:)?{argumento}>', valor, url)
        for metodo in sorted(regla.methods - {'HEAD', 'OPTIONS'}):
            yield metodo, url, permitidos


def test_rnf003_hay_suficientes_rutas_protegidas_que_revisar(app):
    assert len(list(rutas_protegidas(app))) >= 40


def test_rnf003_sin_sesion_ninguna_ruta_del_personal_responde(app_bd):
    anonimo = app_bd.test_client()
    token = token_csrf(anonimo, '/login')
    for metodo, url, _ in rutas_protegidas(app_bd):
        respuesta = anonimo.open(url, method=metodo, data={'csrf_token': token})
        assert respuesta.status_code == 302 and '/login' in respuesta.headers['Location'], f'{metodo} {url}'


@pytest.mark.parametrize('rol', ['Cajero', 'Repartidor', 'Gerente', 'Administrador'])
def test_rnf003_cada_rol_solo_entra_a_lo_suyo_y_nada_truena(app_bd, rol):
    web = app_bd.test_client()
    iniciar_sesion(web, USUARIOS[rol])
    token = token_csrf(web, '/')  # cualquier página con formulario sirve para obtener el token
    for metodo, url, permitidos in rutas_protegidas(app_bd):
        respuesta = web.open(url, method=metodo, data={'csrf_token': token})
        assert respuesta.status_code != 500, f'{rol}: {metodo} {url} respondió 500'       # RNF-002
        if rol in permitidos:
            assert respuesta.status_code != 403, f'{rol} debería poder usar {metodo} {url}'
        else:
            assert respuesta.status_code == 403, f'{rol} NO debería poder usar {metodo} {url}'


def test_rnf003_el_cliente_no_entra_a_pantallas_del_personal(app_bd, web):
    entrar_como_cliente(web)
    for url in ('/cajero/', '/gerente/reportes', '/admin/auditoria', '/seguimiento/YP-0001', '/notificaciones/'):
        assert web.get(url).headers['Location'].startswith('/login')


# ------------------------------------------------------------------------------ RNF-005

def test_rnf005_una_sucursal_nueva_funciona_solo_con_datos(app_bd, web):
    salida = app_bd.test_cli_runner().invoke(args=[
        'nueva-sucursal', '--nombre', 'Boca del Río', '--direccion', 'Blvd. Ávila Camacho 2000', '--ciudad', 'Boca del Río',
        '--apertura', '12:00', '--cierre', '23:00', '--gerente', 'gerente.bocadelrio', '--gerente-nombre', 'Laura',
        '--gerente-apellidos', 'Mendoza Ruiz', '--gerente-telefono', '2291234500']).output
    assert 'Sucursal "Boca del Río" creada' in salida
    temporal = re.search(r'contraseña temporal: (\w+)', salida).group(1)
    with app_bd.app_context():
        nueva = db.session.scalar(select(Sucursal).where(Sucursal.nombre == 'Boca del Río'))
        id_nueva = nueva.id_sucursal

    # El cliente ya la ve y puede pedirle (con el horario propio de la sucursal: 12:00–23:00).
    entrar_como_cliente(web)
    assert 'Boca del Río' in web.get('/pedido').get_data(as_text=True)
    folio = folio_de(web.post('/pedido', data=formulario(app_bd, web, id_sucursal=id_nueva)))
    with app_bd.app_context():
        assert db.session.scalar(select(Pedido.id_sucursal).where(Pedido.folio == folio)) == id_nueva

    # Su gerente entra (debe cambiar la contraseña temporal) y ve solo su sucursal.
    gerente = app_bd.test_client()
    assert iniciar_sesion(gerente, 'gerente.bocadelrio', temporal).headers['Location'] == '/cambiar-contrasena'
    gerente.post('/cambiar-contrasena', data={'actual': temporal, 'nueva': 'Boca2026x', 'confirmacion': 'Boca2026x',
                                              'csrf_token': token_csrf(gerente, '/cambiar-contrasena')})
    html = gerente.get('/gerente/pedidos?estado=Cancelado').get_data(as_text=True)
    assert 'Pedidos · Boca del Río' in html


def test_rnf005_el_ejemplo_sql_se_ejecuta(con):
    script = (RAIZ / 'db' / 'ejemplo_nueva_sucursal.sql').read_text(encoding='utf-8')
    sentencias = [s for s in re.sub(r'--[^\n]*', '', script).split(';') if s.strip() and s.strip() not in ('BEGIN', 'COMMIT')]
    for sentencia in sentencias:
        con.exec_driver_sql(sentencia)
    assert con.execute(text("SELECT count(*) FROM empleado e JOIN sucursal s USING (id_sucursal) "
                            "WHERE s.nombre = 'Boca del Río' AND e.puesto = 'Cocinero'")).scalar() == 1


# ------------------------------------------------------------------------------ RNF-006

def test_rnf006_cada_modulo_explica_para_que_sirve():
    sin_documentar = []
    for archivo in sorted((RAIZ / 'gpizza').rglob('*.py')):
        if not ast.get_docstring(ast.parse(archivo.read_text(encoding='utf-8'))):
            sin_documentar.append(str(archivo.relative_to(RAIZ)))
    assert sin_documentar == []


def test_rnf006_las_reglas_de_negocio_estan_en_un_solo_lugar():
    """Los números de las reglas (100, 45, 90…) se leen de gpizza/reglas.py, no se repiten sueltos."""
    from gpizza import reglas
    assert (reglas.PEDIDO_MINIMO, reglas.ALERTA_PREPARACION_MIN, reglas.ALERTA_ENTREGA_MIN,
            reglas.MAX_PEDIDOS_ACTIVOS_REPARTIDOR, reglas.PLAZO_DEVOLUCION_HORAS) == (100, 45, 90, 2, 2)
