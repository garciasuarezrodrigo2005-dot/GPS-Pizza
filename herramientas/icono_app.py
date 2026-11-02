"""Ícono de GPizza: rebanada de pizza al frente de hojas de selva ("Yungla"), sobre el terracota de la marca.
Genera el SVG (favicon y logotipo) y los PNG que pide la PWA (192, 512, maskable y apple-touch).
Uso: python herramientas/icono_app.py       -> solo logo.svg
     python herramientas/icono_app.py png   -> también los PNG (requiere playwright y Chrome)"""
import sys
from pathlib import Path

IMG = Path(__file__).resolve().parent.parent / 'gpizza' / 'static' / 'img'

DIBUJO = """
  <circle cx="256" cy="236" r="168" fill="#fff" opacity=".07"/>
  <g stroke-linejoin="round">
    {hojas}
  </g>
  <!-- Rebanada: orilla dorada, queso y pepperoni -->
  <path d="M256 448 146 196q110-64 220 0z" fill="#f7cf5f" stroke="#7c2d12" stroke-width="10"/>
  <circle cx="222" cy="248" r="26" fill="#b3261e" stroke="#7f1d1d" stroke-width="6"/>
  <circle cx="294" cy="260" r="22" fill="#b3261e" stroke="#7f1d1d" stroke-width="6"/>
  <circle cx="252" cy="330" r="19" fill="#b3261e" stroke="#7f1d1d" stroke-width="6"/>
  <circle cx="214" cy="244" r="4" fill="#7f1d1d"/><circle cx="300" cy="254" r="3.5" fill="#7f1d1d"/>
  <path d="M232 384q12-18 26-4-12 16-26 4z" fill="#2f7d32" stroke="#14532d" stroke-width="4"/>
  <path d="M128 196q128-84 256 0l-10 30q-118-70-236 0z" fill="#e9a23b" stroke="#7c2d12" stroke-width="10"/>
  <path d="M168 196q88-42 176 0" fill="none" stroke="#f6c86a" stroke-width="6" stroke-linecap="round" opacity=".9"/>
"""

HOJA = ('<g transform="translate(256 222) rotate({a}) scale({s})">'
        '<path d="M0 0C46-56 50-150 0-205-50-150-46-56 0 0z" fill="{c}" stroke="#0f3d1e" stroke-width="7"/>'
        '<path d="M0-8V-190" stroke="#0f3d1e" stroke-width="5" opacity=".55"/>'
        '<path d="M0-60 26-82M0-60-26-82M0-110 24-130M0-110-24-130M0-150 16-166M0-150-16-166" stroke="#0f3d1e" stroke-width="4" opacity=".4"/>'
        '</g>')
hojas = ''.join(HOJA.format(a=a, s=s, c=c) for a, s, c in
                ((-112, .95, '#2f7d32'), (112, .95, '#2f7d32'), (-72, 1.08, '#3f9a3f'), (72, 1.08, '#3f9a3f'), (-34, 1.0, '#4caf50'), (34, 1.0, '#4caf50')))
FONDO = '<defs><linearGradient id="f" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d9531a"/><stop offset="1" stop-color="#7c2d12"/></linearGradient></defs>'


def icono(redondeado=True, escala=1.0):
    marco = '<rect width="512" height="512" rx="{}" fill="url(#f)"/>'.format(112 if redondeado else 0)
    if redondeado:
        marco += '<rect x="14" y="14" width="484" height="484" rx="100" fill="none" stroke="#b8893b" stroke-width="6" opacity=".7"/>'
    cuerpo = DIBUJO.format(hojas=hojas)
    if escala != 1:
        d = 256 * (1 - escala)
        cuerpo = f'<g transform="translate({d} {d}) scale({escala})">{cuerpo}</g>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            f'<title>Yungla Pizza</title>{FONDO}{marco}{cuerpo}</svg>\n')


(IMG / 'logo.svg').write_text(icono(), encoding='utf-8')
if len(sys.argv) > 1 and sys.argv[1] == 'png':
    from playwright.sync_api import sync_playwright
    salidas = [('icono-192.png', 192, icono(), True), ('icono-512.png', 512, icono(), True),
               ('icono-maskable-512.png', 512, icono(False, .78), False),   # zona segura: el dibujo dentro del 80 %
               ('apple-touch-icon.png', 180, icono(False, .9), False)]      # iOS redondea solo las esquinas
    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome')
        for nombre, lado, codigo, transparente in salidas:
            pg = b.new_page(viewport={'width': lado, 'height': lado})
            pg.set_content(f'<html><body style="margin:0;background:transparent">'
                           f'<div style="width:{lado}px;height:{lado}px">{codigo.replace("<svg ", f"<svg width={lado} height={lado} ")}</div></body></html>')
            pg.screenshot(path=str(IMG / nombre), omit_background=transparente)
            pg.close()
        b.close()
print('listo')
