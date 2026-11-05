// Mapa de sucursales del pedido (decisión 22).
// - Muestra todas las sucursales; las cerradas en este momento se ven en gris.
// - Con la ubicación del cliente (guardada o con "Usar mi ubicación") preselecciona la abierta más cercana.
// - Tocar una sucursal en el mapa la elige; elegirla en la lista la resalta en el mapa.
// Es solo una recomendación: el cliente puede pedir a cualquier sucursal (RNF-009 sigue fuera del alcance).
(() => {
  const contenedor = document.getElementById('mapa-sucursales');
  const datos = JSON.parse(document.getElementById('datos-sucursales')?.textContent || 'null');
  const lista = document.getElementById('id_sucursal');
  if (!contenedor || !datos || !lista || typeof L === 'undefined') return;

  const form = document.getElementById('form-pedido');
  const panel = document.getElementById('sucursal-elegida');
  const ayuda = document.getElementById('sucursal-ayuda');
  const conUbicacion = datos.sucursales.filter((s) => s.lat !== null);
  // Si el cliente ya eligió (al modificar, por un error o en el borrador recuperado), ya no se cambia sola.
  let eligioManual = datos.elegida || document.getElementById('aviso-borrador')?.hidden === false;
  let recomendada = null;
  const distancias = {};

  // Fórmula de Haversine: distancia en línea recta, en km.
  function distanciaKm([lat1, lng1], [lat2, lng2]) {
    const rad = (g) => (g * Math.PI) / 180;
    const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lng2 - lng1) / 2) ** 2;
    return 2 * 6371 * Math.asin(Math.sqrt(a));
  }
  const km = (d) => (d < 1 ? `${Math.round(d * 1000)} m` : `${d.toFixed(1)} km`);

  const mapa = L.map(contenedor, { scrollWheelZoom: false, dragging: !L.Browser.mobile, tap: false });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; colaboradores de OpenStreetMap',
    referrerPolicy: 'strict-origin-when-cross-origin',
  }).addTo(mapa);

  const marcadores = {};
  conUbicacion.forEach((s) => {
    marcadores[s.id] = L.marker([s.lat, s.lng], { title: s.nombre, keyboard: true }).addTo(mapa)
      .on('click', () => elegir(s.id, true));
  });
  let marcaCliente = null;

  function icono(s) {
    const clases = ['gp-pin-sucursal', s.abierta ? '' : 'cerrada', s.id === recomendada ? 'recomendada' : '',
                    String(s.id) === lista.value ? 'elegida' : ''].join(' ');
    const etiqueta = s.id === recomendada ? '<span class="gp-pin-etiqueta">Recomendada</span>' : '';
    return L.divIcon({ className: '', html: `<div class="${clases}"><span>🍕</span>${etiqueta}</div>`,
                       iconSize: [40, 40], iconAnchor: [20, 20] });
  }

  function pintar() {
    conUbicacion.forEach((s) => {
      marcadores[s.id].setIcon(icono(s));
      marcadores[s.id].setZIndexOffset(String(s.id) === lista.value ? 1000 : (s.id === recomendada ? 500 : 0));
    });
    // En la lista también se ve la distancia y cuál es la recomendada.
    [...lista.options].forEach((opcion) => {
      const id = Number(opcion.value);
      const extra = [distancias[id] !== undefined ? km(distancias[id]) : '', id === recomendada ? '★ recomendada' : '']
        .filter(Boolean).join(' · ');
      opcion.textContent = opcion.dataset.nombre + (extra ? ` — ${extra}` : '');
    });
    const s = datos.sucursales.find((x) => String(x.id) === lista.value);
    if (!s) { panel.hidden = true; return; }
    panel.hidden = false;
    panel.className = `gp-sucursal-elegida mb-2 ${s.abierta ? '' : 'cerrada'}`;
    panel.innerHTML = `<span class="gp-sucursal-icono" aria-hidden="true">🍕</span>
      <div><div class="fw-semibold">${s.nombre}${s.id === recomendada ? ' <span class="gp-insignia">Recomendada</span>' : ''}</div>
      <div class="small">${s.direccion}</div>
      <div class="small gp-texto-suave">${distancias[s.id] !== undefined ? `A ${km(distancias[s.id])} de ti · ` : ''}${
        s.abierta ? `Abierta · pedidos de ${s.horario}` : `<strong class="gp-texto-alerta">Cerrada ahora</strong> · pedidos de ${s.horario}`}</div></div>`;
  }

  function elegir(id, manual) {
    if (manual) eligioManual = true;
    lista.value = String(id);
    lista.dispatchEvent(new Event('change', { bubbles: true }));   // el borrador y los totales se enteran
    pintar();
  }

  function ubicacionCliente() {
    const lat = form?.querySelector('[name="latitud"]')?.value;
    const lng = form?.querySelector('[name="longitud"]')?.value;
    if (lat && lng) return [Number(lat), Number(lng)];
    return datos.cliente;
  }

  function recomendar() {
    const cliente = ubicacionCliente();
    recomendada = null;
    if (cliente) {
      conUbicacion.forEach((s) => { distancias[s.id] = distanciaKm(cliente, [s.lat, s.lng]); });
      const ordenadas = [...conUbicacion].sort((a, b) => distancias[a.id] - distancias[b.id]);
      const mejor = ordenadas.find((s) => s.abierta) || ordenadas[0];
      recomendada = mejor ? mejor.id : null;
      if (marcaCliente) marcaCliente.setLatLng(cliente);
      else marcaCliente = L.marker(cliente, { icon: L.divIcon({ html: '🏠', className: 'gp-marcador', iconSize: [34, 34], iconAnchor: [17, 17] }),
                                              title: 'Tu ubicación', interactive: false }).addTo(mapa);
      ayuda.textContent = mejor && mejor.abierta
        ? 'Te recomendamos la sucursal abierta más cercana. Toca otra en el mapa si prefieres.'
        : 'Ninguna sucursal cercana está abierta ahora. Puedes elegir otra en el mapa.';
      if (recomendada && !eligioManual) elegir(recomendada, false);
    }
    encuadrar(cliente);
    pintar();
  }

  function encuadrar(cliente) {
    const puntos = conUbicacion.map((s) => [s.lat, s.lng]);
    if (cliente) {
      // Se enfoca al cliente y a sus 3 sucursales más cercanas: la recomendada y sus alternativas a la vista.
      const cercanas = [...conUbicacion].sort((a, b) => distancias[a.id] - distancias[b.id]).slice(0, 3).map((s) => [s.lat, s.lng]);
      mapa.fitBounds(L.latLngBounds([cliente, ...cercanas]), { padding: [45, 45], maxZoom: 14 });
    } else if (puntos.length) {
      mapa.fitBounds(L.latLngBounds(puntos), { padding: [30, 30], maxZoom: 13 });
    } else {
      mapa.setView([19.1738, -96.1342], 12);
    }
  }

  // Si el mapa cambia de tamaño mientras la página termina de acomodarse (en la PC pasa al armarse las dos
  // columnas), Leaflet debe medirse de nuevo; se vuelve a encuadrar mientras el cliente no lo haya movido.
  let movioMapa = false;
  ['pointerdown', 'wheel', 'touchstart'].forEach((tipo) => contenedor.addEventListener(tipo, () => { movioMapa = true; }, { passive: true }));
  if ('ResizeObserver' in window) {
    new ResizeObserver(() => {
      mapa.invalidateSize();
      if (!movioMapa) encuadrar(ubicacionCliente());
    }).observe(contenedor);
  }

  lista.addEventListener('change', (evento) => { if (evento.isTrusted) eligioManual = true; pintar(); });
  form?.addEventListener('gp:ubicacion', recomendar);
  recomendar();
})();
