"""Genera los íconos SVG de cada producto en gpizza/static/img/productos/ (vista de arriba, 64x64).
Cada pizza muestra sus ingredientes reales; los complementos son dibujos propios.
Uso: python herramientas/iconos_productos.py   (el archivo se llama como el producto: "Ensalada César" -> ensalada-cesar.svg)"""
import math
from pathlib import Path

SALIDA = Path(__file__).resolve().parent.parent / 'gpizza' / 'static' / 'img' / 'productos'
SALIDA.mkdir(parents=True, exist_ok=True)
ORO = math.radians(137.508)


def puntos(n, radio, giro=0.0, centro=(32, 32)):
    """n puntos repartidos parejo dentro de un círculo (espiral de Fermat)."""
    cx, cy = centro
    for i in range(n):
        r = radio * math.sqrt((i + 0.5) / n)
        a = i * ORO + giro
        yield round(cx + r * math.cos(a), 1), round(cy + r * math.sin(a), 1), round(math.degrees(a) % 360)


def svg(cuerpo, titulo):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="{titulo}">'
            f'<title>{titulo}</title>{cuerpo}</svg>\n')


def pizza(toppings, titulo, salsa='#c0392b', queso='#f5cf6e', borde='#d48a3a'):
    base = (f'<circle cx="32" cy="32" r="30" fill="{borde}"/>'
            f'<circle cx="32" cy="32" r="30" fill="none" stroke="#a8652a" stroke-width="1.2"/>'
            f'<circle cx="32" cy="32" r="25.5" fill="{salsa}"/>'
            f'<path d="M32 8.5c7 0 13 3 17 8 4 5 6 10 5.5 16-.5 7-4 13-10 17-5 3.3-10 4.5-15 3.8-6-.8-11.5-4-15-9-3.5-5-4.8-11-3.6-17 1.3-6 5-11.5 10.3-14.6C24.5 9.8 28 8.5 32 8.5z" fill="{queso}"/>'
            '<g stroke="#e9b44c" stroke-width=".9" opacity=".7">'
            '<path d="M32 7v50M7 32h50M14.3 14.3l35.4 35.4M49.7 14.3 14.3 49.7"/></g>')
    return svg(base + toppings, titulo)


def pepperoni(x, y, r=4.2):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="#b3261e"/><circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="#7f1d1d" stroke-width=".8"/>'
            f'<circle cx="{x - 1.2}" cy="{y - 1}" r=".7" fill="#7f1d1d"/><circle cx="{x + 1.3}" cy="{y + .8}" r=".6" fill="#7f1d1d"/>')


def jamon(x, y, a):
    return f'<rect x="{x - 3}" y="{y - 2.6}" width="6" height="5.2" rx="1" fill="#f19aa6" stroke="#d76d7e" stroke-width=".6" transform="rotate({a} {x} {y})"/>'


def pina(x, y, a):
    return f'<path d="M{x - 3.2} {y + 2}l3.2-5 3.2 5z" fill="#ffd93b" stroke="#e0a800" stroke-width=".6" stroke-linejoin="round" transform="rotate({a} {x} {y})"/>'


def tocino(x, y, a):
    return (f'<path d="M{x - 5} {y}q1.7-2 3.3 0t3.3 0 3.4 0" fill="none" stroke="#8b2c1a" stroke-width="2.6" stroke-linecap="round" transform="rotate({a} {x} {y})"/>'
            f'<path d="M{x - 5} {y}q1.7-2 3.3 0t3.3 0 3.4 0" fill="none" stroke="#f3b7a0" stroke-width=".8" stroke-linecap="round" transform="rotate({a} {x} {y})"/>')


def salami(x, y):
    return (f'<circle cx="{x}" cy="{y}" r="4.6" fill="#8e2430"/>'
            f'<circle cx="{x - 1.5}" cy="{y - 1}" r=".8" fill="#f4d0d6"/><circle cx="{x + 1.2}" cy="{y - 1.6}" r=".6" fill="#f4d0d6"/>'
            f'<circle cx="{x + .6}" cy="{y + 1.6}" r=".8" fill="#f4d0d6"/><circle cx="{x - 1.6}" cy="{y + 1.5}" r=".5" fill="#f4d0d6"/>')


def migaja(x, y, a, color='#7a2a14'):
    return f'<path d="M{x - 2.2} {y - .6}l1.4-1.6 2.2.4 1 1.8-1.2 1.8-2.4.2z" fill="{color}" transform="rotate({a} {x} {y})"/>'


def jalapeno(x, y):
    return (f'<circle cx="{x}" cy="{y}" r="2.9" fill="#a7d36b" stroke="#2f7d32" stroke-width="1.3"/>'
            f'<circle cx="{x - .7}" cy="{y}" r=".45" fill="#f4f1d0"/><circle cx="{x + .7}" cy="{y + .4}" r=".45" fill="#f4f1d0"/>')


def cebolla(x, y, a, color='#9b4f96'):
    return f'<path d="M{x - 3} {y + 1}a3.4 3.4 0 0 1 6 0" fill="none" stroke="{color}" stroke-width="1.1" stroke-linecap="round" transform="rotate({a} {x} {y})"/>'


def frijol(x, y, a):
    return f'<ellipse cx="{x}" cy="{y}" rx="1.9" ry="1.2" fill="#5b3420" transform="rotate({a} {x} {y})"/>'


def pimiento(x, y, a):
    return f'<path d="M{x - 3.5} {y + 1.4}q3.5-4 7 0" fill="none" stroke="#2e9e44" stroke-width="1.8" stroke-linecap="round" transform="rotate({a} {x} {y})"/>'


def champinon(x, y, a):
    return (f'<g transform="rotate({a} {x} {y})"><path d="M{x - 3.2} {y}a3.2 3 0 0 1 6.4 0z" fill="#e8d9c2" stroke="#a88b68" stroke-width=".6"/>'
            f'<rect x="{x - 1}" y="{y}" width="2" height="2.4" rx=".6" fill="#e8d9c2" stroke="#a88b68" stroke-width=".6"/></g>')


def aceituna(x, y):
    return f'<circle cx="{x}" cy="{y}" r="2.1" fill="none" stroke="#1f1b18" stroke-width="1.3"/>'


def elote(x, y):
    return f'<rect x="{x - 1.1}" y="{y - 1.1}" width="2.2" height="2.2" rx=".6" fill="#ffc928"/>'


def chile_guero(x, y, a):
    return (f'<g transform="rotate({a} {x} {y})"><path d="M{x - 5} {y}q4-2.6 9 0q-4 2.6-9 0z" fill="#e7e36a" stroke="#a3a12a" stroke-width=".6"/>'
            f'<path d="M{x + 4} {y}l1.6-.8" stroke="#4d7c0f" stroke-width="1" stroke-linecap="round"/></g>')


def cada(n, radio, f, giro=0.0, **kw):
    return ''.join(f(x, y, a, **kw) if f.__code__.co_argcount >= 3 else f(x, y, **kw) for x, y, a in puntos(n, radio, giro))


PIZZAS = {
    'pepperoni': ('Pizza de pepperoni', cada(9, 18, lambda x, y: pepperoni(x, y))),
    'hawaiana': ('Pizza hawaiana', cada(8, 19, jamon, .4) + cada(8, 19, pina, 2.0)),
    'mexicana': ('Pizza mexicana',
                 cada(10, 19, migaja, .2) + cada(5, 17, jalapeno, 1.3) + cada(5, 19, cebolla, 2.6) + cada(7, 19, frijol, .9)),
    'carnes-frias': ('Pizza de carnes frías',
                     cada(4, 17, salami, .1) + cada(4, 18, lambda x, y: pepperoni(x, y, 3.4), 1.7) + cada(5, 19, jamon, 3.0)
                     + cada(3, 14, tocino, 4.4)),
    'vegetariana': ('Pizza vegetariana',
                    cada(6, 19, pimiento, .3) + cada(5, 18, champinon, 1.9) + cada(6, 19, aceituna, 3.1) + cada(10, 20, elote, 4.6)
                    + cada(4, 15, cebolla, 5.5)),
    'yungla-especial': ('Pizza Yungla Especial',
                        cada(12, 20, lambda x, y, a: migaja(x, y, a, '#6b3e26'), .5) + cada(6, 19, migaja, 2.2) + cada(3, 16, tocino, 3.3)
                        + cada(4, 18, chile_guero, 1.1)
                        # sello de la casa: hojita de la selva al centro
                        + '<path d="M32 26c4.5 1.5 6 5 4 9-2.5-.5-5.5-2.5-6.5-5-.5-1.5 0-3 2.5-4z" fill="#2f7d32" stroke="#14532d" stroke-width=".7"/>'
                          '<path d="M32.6 27.5c1 2.4 2 4.6 3.2 7" stroke="#a7d36b" stroke-width=".7" fill="none"/>'),
}

for nombre, (titulo, toppings) in PIZZAS.items():
    salsa = '#7a2d1a' if nombre == 'yungla-especial' else '#c0392b'
    queso = '#f8dc8a' if nombre == 'vegetariana' else '#f5cf6e'
    (SALIDA / f'{nombre}.svg').write_text(pizza(toppings, titulo, salsa=salsa, queso=queso), encoding='utf-8')

COMPLEMENTOS = {
    'papas-gajo': ('Papas gajo',
        '<path d="M14 26h36l-5 32H19z" fill="#c2410c"/><path d="M14 26h36l-1 6H15z" fill="#9a3412"/>'
        '<path d="M22 40 22 30 29 34z" fill="none"/>'
        + ''.join(f'<path d="M{x} 30q{d} -14 {w} -18q3 2 3 6q-1 8 -4 12z" fill="#f2b84b" stroke="#b7791f" stroke-width=".8" transform="rotate({r} {x + 2} 28)"/>'
                  for x, d, w, r in ((17, 2, 4, -18), (23, 1, 3, -6), (29, 0, 3, 4), (35, 1, 4, 14), (41, 2, 3, 24)))
        + '<g fill="#b45309" opacity=".8"><circle cx="24" cy="20" r=".6"/><circle cx="33" cy="17" r=".6"/><circle cx="39" cy="22" r=".6"/></g>'
        '<path d="M22 44h20" stroke="#fde68a" stroke-width="1.5" stroke-linecap="round"/><path d="M24 49h16" stroke="#fde68a" stroke-width="1.5" stroke-linecap="round"/>'),
    'alitas-bbq': ('Alitas BBQ',
        '<ellipse cx="32" cy="36" rx="28" ry="22" fill="#f5f0e8" stroke="#cfc6b8" stroke-width="1.2"/>'
        '<ellipse cx="32" cy="36" rx="22" ry="16.5" fill="none" stroke="#e7dfd2" stroke-width="1"/>'
        + ''.join(f'<g transform="rotate({r} {x} {y})"><ellipse cx="{x}" cy="{y}" rx="9" ry="5.5" fill="#8b3a12"/>'
                  f'<ellipse cx="{x - 1.5}" cy="{y - 1.6}" rx="5" ry="1.6" fill="#c2621f" opacity=".8"/>'
                  f'<rect x="{x + 7}" y="{y - 1.4}" width="5" height="2.8" rx="1.4" fill="#f3ead8"/>'
                  f'<circle cx="{x + 12}" cy="{y - 1.4}" r="1.6" fill="#f3ead8"/><circle cx="{x + 12}" cy="{y + 1.4}" r="1.6" fill="#f3ead8"/></g>'
                  for x, y, r in ((22, 30, -25), (30, 40, 10), (38, 28, 35)))
        + '<g fill="#fef3c7"><circle cx="20" cy="29" r=".5"/><circle cx="29" cy="39" r=".5"/><circle cx="37" cy="27" r=".5"/></g>'),
    'pan-de-ajo': ('Pan de ajo',
        '<rect x="6" y="40" width="52" height="14" rx="3" fill="#8a5a3b"/>'
        + ''.join(f'<g transform="rotate(-12 {x} 34)"><path d="M{x - 7} 44q0-16 7-17q7 1 7 17z" fill="#e3a857" stroke="#a8652a" stroke-width="1"/>'
                  f'<path d="M{x - 5} 43q0-12 5-13q5 1 5 13z" fill="#fbe3a1"/>'
                  f'<path d="M{x - 4.5} 36q2-2 4 0t4 0" fill="none" stroke="#f5c542" stroke-width="1.6" stroke-linecap="round"/>'
                  f'<circle cx="{x - 2}" cy="39" r=".7" fill="#3f8f3a"/><circle cx="{x + 1.5}" cy="37" r=".7" fill="#3f8f3a"/><circle cx="{x + 1}" cy="41" r=".6" fill="#3f8f3a"/></g>'
                  for x in (16, 30, 44))
        + '<g transform="translate(46 12)"><path d="M6 2c4 0 6 3 6 6s-3 6-6 6-6-3-6-6 2-6 6-6z" fill="#fbf7ef" stroke="#b8a98f" stroke-width=".8"/>'
          '<path d="M6 2v12M2.5 4q3.5 4 0 9M9.5 4q-3.5 4 0 9" fill="none" stroke="#d6cbb7" stroke-width=".7"/><path d="M6 2q1-2 2-2.5" stroke="#6b8e23" stroke-width="1" fill="none"/></g>'),
    'refresco-2-l': ('Refresco de 2 litros',
        '<path d="M27 4h10v5l3 6v39q0 6-6 6h-4q-6 0-6-6V15l3-6z" fill="#3b1d12" stroke="#1f1b18" stroke-width="1"/>'
        '<rect x="26.5" y="2" width="11" height="5" rx="1.2" fill="#c2410c"/>'
        '<rect x="24" y="26" width="16" height="14" fill="#c2410c"/><path d="M24 30h16" stroke="#fde68a" stroke-width="1"/>'
        '<path d="M28 35q4-4 8 0" stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round"/>'
        '<path d="M27 16v8M27 44v10" stroke="#fff" stroke-opacity=".35" stroke-width="1.6" stroke-linecap="round"/>'
        '<g fill="#fff" opacity=".55"><circle cx="34" cy="48" r="1"/><circle cx="36" cy="44" r=".7"/><circle cx="33" cy="20" r=".8"/></g>'),
    'brownie': ('Brownie',
        '<ellipse cx="32" cy="50" rx="27" ry="8" fill="#f5f0e8" stroke="#cfc6b8" stroke-width="1"/>'
        '<path d="M12 28l20-10 20 10v16l-20 10-20-10z" fill="#4a2617"/>'
        '<path d="M12 28l20-10 20 10-20 10z" fill="#6b3a24"/>'
        '<path d="M32 38v16" stroke="#2e170d" stroke-width="1"/>'
        '<path d="M14 29q4 3 6 0t6 1 6 0 6 1 6-1 6 0" fill="none" stroke="#2e170d" stroke-width="1.2" opacity=".6"/>'
        + ''.join(f'<path d="M{x - 2} {y}q2-2.4 4 0q-2 2.4-4 0z" fill="#d6b07a" stroke="#8b6a3e" stroke-width=".5"/>' for x, y in ((24, 25), (33, 22), (40, 27), (30, 30)))
        + '<path d="M20 22q-2-6 2-10M44 22q2-6-2-10" stroke="#cfc6b8" stroke-width="1.2" fill="none" stroke-linecap="round"/>'),
    'ensalada-cesar': ('Ensalada César',
        '<path d="M6 30h52q-2 24-26 24T6 30z" fill="#f5f0e8" stroke="#cfc6b8" stroke-width="1.2"/>'
        '<path d="M10 38h44" stroke="#c2410c" stroke-width="1.5" opacity=".7"/>'
        + ''.join(f'<path d="M{x} 31q{d} -16 {w} -18q4 6 0 18z" fill="{c}" stroke="#2f6b2f" stroke-width=".8"/>'
                  for x, d, w, c in ((10, 2, 10, '#8cc56b'), (18, 1, 9, '#6fae4f'), (26, 2, 10, '#9fd47a'), (34, 1, 9, '#6fae4f'), (42, 2, 9, '#8cc56b')))
        + ''.join(f'<rect x="{x}" y="{y}" width="4.4" height="4.4" rx=".8" fill="#e0a95b" stroke="#a8652a" stroke-width=".6" transform="rotate({r} {x + 2} {y + 2})"/>'
                  for x, y, r in ((17, 23, 15), (30, 21, -10), (40, 24, 25)))
        + '<g fill="#fffbeb"><path d="M23 26l3-1 1 2-3 1z"/><path d="M35 25l3 0 0 2-3 0z"/></g>'),
}
for nombre, (titulo, cuerpo) in COMPLEMENTOS.items():
    (SALIDA / f'{nombre}.svg').write_text(svg(cuerpo, titulo), encoding='utf-8')

# Genéricos para productos que el gerente agregue después (RNF-005): se usan hasta que tengan su propio dibujo.
(SALIDA / 'pizza.svg').write_text(pizza(cada(6, 18, lambda x, y: f'<circle cx="{x}" cy="{y}" r="3" fill="#fff7e0" opacity=".9"/>')
                                        + '<circle cx="32" cy="32" r="3" fill="#2f7d32"/>', 'Pizza'), encoding='utf-8')
(SALIDA / 'complemento.svg').write_text(svg(
    '<path d="M10 30h44l-4 24H14z" fill="#c2410c"/><path d="M8 26h48v5H8z" fill="#9a3412"/>'
    '<path d="M22 18q4-8 10-8t10 8" fill="none" stroke="#cfc6b8" stroke-width="2" stroke-linecap="round"/>'
    '<circle cx="32" cy="42" r="5" fill="#fde68a"/>', 'Complemento'), encoding='utf-8')
print(sorted(p.name for p in SALIDA.iterdir()))
