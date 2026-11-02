"""Íconos de la app y de los productos: cada producto del menú tiene su propio dibujo y ninguno se repite."""
import hashlib
from pathlib import Path

from gpizza.web.filtros import _clave_producto, icono_producto
from seed.datos_demo import COMPLEMENTOS, PIZZAS

CARPETA = Path(__file__).resolve().parent.parent / 'gpizza' / 'static' / 'img' / 'productos'


def test_cada_producto_del_menu_tiene_su_propio_icono():
    nombres = [n for n, _, _ in PIZZAS] + [n for n, _, _ in COMPLEMENTOS]
    archivos = [CARPETA / f'{_clave_producto(n)}.svg' for n in nombres]
    faltan = [a.name for a in archivos if not a.is_file()]
    assert not faltan, f'Productos sin ícono: {faltan}'
    huellas = {hashlib.sha256(a.read_bytes()).hexdigest() for a in archivos}
    assert len(huellas) == len(nombres), 'Hay productos que comparten el mismo dibujo'


def test_clave_del_producto_ignora_acentos_y_parentesis():
    assert _clave_producto('Ensalada César') == 'ensalada-cesar'
    assert _clave_producto('Alitas BBQ (8 pzas)') == 'alitas-bbq'
    assert _clave_producto('Carnes frías') == 'carnes-frias'


def test_producto_nuevo_usa_el_icono_general_de_su_categoria(app):
    with app.test_request_context():
        assert icono_producto('Pepperoni', 'Pizza').endswith('/img/productos/pepperoni.svg')
        assert icono_producto('Pizza de temporada', 'Pizza').endswith('/img/productos/pizza.svg')
        assert icono_producto('Agua de jamaica', 'Complemento').endswith('/img/productos/complemento.svg')


def test_logo_y_favicon_disponibles(cliente):
    respuesta = cliente.get('/static/img/logo.svg')
    assert respuesta.status_code == 200 and b'<svg' in respuesta.data
