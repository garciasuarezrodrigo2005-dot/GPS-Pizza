"""Revisa todas las pantallas en varios anchos y reporta: elementos fuera de la pantalla, textos o botones
encimados, textos cortados y contenido tapado por la barra inferior. Toma captura de las que tienen problemas.
Uso (con la app corriendo sobre la base de pruebas gpizza_test):
    python herramientas/revisar_responsivo.py http://127.0.0.1:5000 revision [320,360,390,412,768,1024,1366]
Requiere playwright (pip install playwright) y Chrome instalado. Debe terminar en "0 pantallas con problemas"."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE, SALIDA = sys.argv[1], Path(sys.argv[2])
ANCHOS = [int(a) for a in (sys.argv[3] if len(sys.argv) > 3 else '320,360,390,412,768,1024,1366').split(',')]
SALIDA.mkdir(parents=True, exist_ok=True)

GRUPOS = {
    None: ['/', '/login', '/crear-cuenta', '/no-existe'],
    'cliente': ['/pedido', '/mi-pedido/YP-0224', '/mi-cuenta'],
    'cajero1.coyol': ['/cajero/', '/cajero/pedidos', '/cajero/pedidos?estado=En%20Camino', '/cajero/nuevo',
                      '/cajero/nuevo?telefono=2297654321', '/cajero/clientes', '/cajero/clientes/nuevo',
                      '/seguimiento/?q=YP-0224', '/seguimiento/YP-0224', '/notificaciones/', '/cambiar-contrasena'],
    'repartidor1.coyol': ['/repartidor/', '/repartidor/historial'],
    'gerente.coyol': ['/gerente/', '/gerente/pedidos', '/gerente/catalogo', '/gerente/clientes', '/gerente/clientes/1',
                      '/gerente/personal', '/gerente/descuentos', '/gerente/reportes', '/gerente/auditoria',
                      '/gerente/catalogo/etiquetas', '/seguimiento/YP-0224'],
    'admin.yungla': ['/admin/', '/admin/sucursales', '/admin/gerentes', '/admin/auditoria'],
}

REVISAR = r"""() => {
  const vw = document.documentElement.clientWidth, vh = innerHeight, res = [];
  const desc = (el) => {
    const c = (el.className && typeof el.className === 'string') ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : '';
    const t = (el.innerText || el.value || el.alt || '').trim().replace(/\s+/g, ' ').slice(0, 40);
    return `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${c} "${t}"`;
  };
  const visible = (el) => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  // Zonas que se desplazan a lo ancho a propósito, o dibujos internos de librerías.
  const ignorar = (el) => el.closest('.visually-hidden, .leaflet-container, .gp-pestanas-estado, .gp-menu-lateral nav, .table-responsive, canvas, svg, option, datalist, script, style, head, [hidden], details:not([open]) > :not(summary)');
  const todos = [...document.body.querySelectorAll('*')].filter((el) => !ignorar(el) && visible(el));

  // 1. Fuera de la pantalla a lo ancho
  for (const el of todos) {
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 || r.left < -1) res.push({tipo: 'fuera', el: desc(el), detalle: `${Math.round(r.left)}..${Math.round(r.right)} de ${vw}`});
  }
  // 2. Texto cortado: el contenido es más ancho que la caja y no se puede desplazar
  for (const el of todos) {
    const s = getComputedStyle(el);
    if (['auto', 'scroll'].includes(s.overflowX) || el.tagName === 'SELECT' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') continue;
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
      res.push({tipo: 'cortado', el: desc(el), detalle: `${el.scrollWidth} > ${el.clientWidth}`});
  }
  // 3. Encimados: hojas (texto propio, botones, campos, imágenes) cuyas cajas se cruzan
  const hojas = todos.filter((el) => ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'IMG', 'A', 'LABEL'].includes(el.tagName) ||
      [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
    .filter((el) => !el.closest('.gp-insignia, .gp-navegacion') && !el.matches('.btn-check, .visually-hidden') && getComputedStyle(el).position !== 'fixed');
  const cajas = hojas.map((el) => {
    // Para texto se mide el texto real (no la caja del bloque, que puede ser más ancha que las letras).
    let r = el.getBoundingClientRect();
    if (!['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'IMG'].includes(el.tagName)) {
      const rango = document.createRange(); rango.selectNodeContents(el); const rr = rango.getBoundingClientRect();
      if (rr.width && rr.height) r = rr;
    }
    return [el, r];
  });
  for (let i = 0; i < cajas.length; i++) for (let j = i + 1; j < cajas.length; j++) {
    const [a, ra] = cajas[i], [b, rb] = cajas[j];
    if (a.contains(b) || b.contains(a)) continue;
    const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    if (w > 3 && h > 3) res.push({tipo: 'encimado', el: desc(a), detalle: 'con ' + desc(b) + ` (${Math.round(w)}x${Math.round(h)})`});
  }
  // 4. Barra inferior fija: al final de la página, ¿tapa el último contenido?
  const barra = document.querySelector('.gp-navegacion');
  if (barra && getComputedStyle(barra).position === 'fixed') {
    window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'});
    const tope = barra.getBoundingClientRect().top;
    const ultimo = [...document.querySelectorAll('.gp-contenido *')].filter(visible).pop();
    if (ultimo && ultimo.getBoundingClientRect().bottom > tope + 1) res.push({tipo: 'tapado', el: desc(ultimo), detalle: 'por la barra inferior'});
    window.scrollTo({top: 0, behavior: 'instant'});
  }
  if (document.documentElement.scrollWidth > vw + 1) res.push({tipo: 'scroll-horizontal', el: 'página', detalle: `${document.documentElement.scrollWidth} > ${vw}`});
  return res;
}"""


def entrar(pagina, rol):
    if rol == 'cliente':
        pagina.goto(BASE + '/')
        pagina.fill('#telefono', '2298901234')
        pagina.fill('#contrasena', 'Pizza2026')
        pagina.click('button:has-text("Entrar")')
    elif rol:
        pagina.goto(BASE + '/login')
        pagina.fill('#usuario', rol)
        pagina.fill('#contrasena', 'Pizza2026')
        pagina.click('button:has-text("Iniciar sesión")')
    pagina.wait_for_load_state('load')


reporte = {}
with sync_playwright() as p:
    nav = p.chromium.launch(channel='chrome')
    for ancho in ANCHOS:
        movil = ancho < 768
        for rol, rutas in GRUPOS.items():
            ctx = nav.new_context(viewport={'width': ancho, 'height': 800 if movil else 900}, is_mobile=movil, has_touch=movil,
                                  device_scale_factor=1)
            # Sin mosaicos del mapa: no cambian el acomodo y así la revisión no depende de internet.
            ctx.route('**/tile.openstreetmap.org/**', lambda r: r.abort())
            pg = ctx.new_page()
            entrar(pg, rol)
            for ruta in rutas:
                pg.goto(BASE + ruta, wait_until='load')
                pg.wait_for_timeout(1500)   # deja terminar las animaciones de entrada
                problemas = pg.evaluate(REVISAR)
                clave = f'{ancho} {rol or "publico"} {ruta}'
                if problemas:
                    reporte[clave] = problemas
                    nombre = f'{ancho}_{(rol or "publico").split(".")[0]}_{ruta.strip("/").replace("/", "_").replace("?", "_") or "inicio"}'[:90]
                    pg.screenshot(path=str(SALIDA / f'{nombre}.png'), full_page=True)
            ctx.close()
    nav.close()

(SALIDA / 'reporte.json').write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding='utf-8')
total = sum(len(v) for v in reporte.values())
print(f'{len(reporte)} pantallas con problemas, {total} problemas')
for clave, problemas in reporte.items():
    print('\n#', clave)
    vistos = set()
    for pr in problemas:
        linea = f"  {pr['tipo']:9} {pr['el']} {pr['detalle']}"
        if linea not in vistos:
            vistos.add(linea)
            print(linea[:230])
