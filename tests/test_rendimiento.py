"""RNF-001: registrar un pedido toma menos de 3 segundos.

Se registran 20 pedidos seguidos de punta a punta (petición HTTP, validaciones, cifrado, INSERT,
triggers y COMMIT) y se mide cada uno. Con `pytest -s` se imprimen los tiempos.
"""
import statistics
import time

from tests.test_pedidos import entrar_como_cliente, formulario

LIMITE_SEGUNDOS = 3.0
PEDIDOS = 20


def test_rnf001_registrar_pedido_en_menos_de_3_segundos(app_bd, web):
    entrar_como_cliente(web)
    tiempos = []
    for _ in range(PEDIDOS):
        datos = formulario(app_bd, web)
        inicio = time.perf_counter()
        respuesta = web.post('/pedido', data=datos)
        tiempos.append(time.perf_counter() - inicio)
        assert respuesta.status_code == 302, respuesta.get_data(as_text=True)[:300]
    print(f'\nRNF-001: {PEDIDOS} pedidos · promedio {statistics.mean(tiempos):.3f} s · '
          f'máximo {max(tiempos):.3f} s · límite {LIMITE_SEGUNDOS} s')
    assert max(tiempos) < LIMITE_SEGUNDOS
