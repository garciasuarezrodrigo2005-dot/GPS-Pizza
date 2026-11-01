// Pantalla "Mis entregas" (boceto 9): mapa, GPS, simulación de recorrido, firma y recarga segura.
(() => {
  const contenedor = document.getElementById('entregas');
  if (!contenedor) return;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const mapas = [];

  // ---------------------------------------------------------------- mapas de las entregas en camino
  contenedor.querySelectorAll('[data-mapa]').forEach((el) => {
    mapas.push(GPizzaMapa.crear(el, {
      repartidor: GPizzaMapa.punto(el.dataset.tuLat, el.dataset.tuLng),
      destino: GPizzaMapa.punto(el.dataset.destinoLat, el.dataset.destinoLng),
    }));
  });

  function enviarUbicacion(lat, lng) {
    mapas.forEach((m) => m.moverRepartidor(lat, lng));
    const datos = new FormData();
    datos.append('latitud', lat.toFixed(6));
    datos.append('longitud', lng.toFixed(6));
    return fetch(contenedor.dataset.urlUbicacion, { method: 'POST', body: datos, headers: { 'X-CSRFToken': csrf } });
  }

  const avisoGps = (texto) => contenedor.querySelectorAll('[data-estado-gps]').forEach((s) => { s.textContent = texto; });

  // ---------------------------------------------------------------- GPS: solo mientras hay entregas en camino
  if (mapas.length) {
    if (window.isSecureContext && 'geolocation' in navigator) {
      let ultimoEnvio = 0;
      navigator.geolocation.watchPosition((pos) => {
        avisoGps('GPS activo.');
        if (Date.now() - ultimoEnvio > 15000) {
          ultimoEnvio = Date.now();
          enviarUbicacion(pos.coords.latitude, pos.coords.longitude);
        }
      }, () => avisoGps('No se pudo leer el GPS; usa "Simular recorrido".'), { enableHighAccuracy: true, maximumAge: 10000 });
    } else {
      avisoGps('El GPS del navegador requiere HTTPS.');
    }
  }

  // ---------------------------------------------------------------- "Simular recorrido" para la demo
  contenedor.querySelectorAll('[data-simular]').forEach((boton, i) => boton.addEventListener('click', () => {
    const m = mapas[i];
    const destino = m?.destino();
    if (!destino) { avisoGps('Este pedido no tiene la ubicación del domicilio.'); return; }
    const inicio = m.repartidor() || L.latLng(destino.lat + 0.02, destino.lng - 0.02);
    const pasos = 12;
    let paso = 0;
    boton.disabled = true;
    const temporizador = setInterval(() => {
      paso += 1;
      const t = paso / pasos;
      enviarUbicacion(inicio.lat + (destino.lat - inicio.lat) * t, inicio.lng + (destino.lng - inicio.lng) * t);
      avisoGps(`Simulando recorrido… ${Math.round(t * 100)} %`);
      if (paso >= pasos) { clearInterval(temporizador); avisoGps('Llegaste al domicilio (simulado).'); boton.disabled = false; }
    }, 2500);
  }));

  // ---------------------------------------------------------------- firma en canvas (RF-010, RN-013 paso 1)
  contenedor.querySelectorAll('[data-form-firma]').forEach((form) => {
    const canvas = form.querySelector('[data-firma]');
    const ctx = canvas.getContext('2d');
    let trazos = 0;
    let dibujando = false;
    ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.strokeStyle = '#1f1b18';

    const posicion = (e) => {
      const r = canvas.getBoundingClientRect();
      return [(e.clientX - r.left) * (canvas.width / r.width), (e.clientY - r.top) * (canvas.height / r.height)];
    };
    canvas.addEventListener('pointerdown', (e) => {
      dibujando = true; trazos += 1;
      contenedor.classList.add('gp-firmando'); // evita recargar la pantalla a mitad de la firma
      canvas.setPointerCapture(e.pointerId);
      ctx.beginPath(); ctx.moveTo(...posicion(e));
    });
    canvas.addEventListener('pointermove', (e) => { if (dibujando) { ctx.lineTo(...posicion(e)); ctx.stroke(); } });
    canvas.addEventListener('pointerup', () => { dibujando = false; });
    form.querySelector('[data-borrar-firma]').addEventListener('click', () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height); trazos = 0;
      contenedor.classList.remove('gp-firmando');
    });
    form.addEventListener('submit', (e) => {
      const codigo = form.querySelector('[name="codigo"]').value.trim();
      if (trazos > 0 && !codigo) form.querySelector('[name="firma"]').value = canvas.toDataURL('image/png');
      if (trazos === 0 && !codigo) {
        e.preventDefault();
        alert('Pide al cliente que firme en el recuadro o que te dé su código de entrega (RN-013).');
      }
    });
  });

  // ---------------------------------------------------------------- recarga cuando cambian las entregas
  setInterval(async () => {
    if (contenedor.classList.contains('gp-firmando') || contenedor.contains(document.activeElement)) return;
    try {
      const r = await (await fetch(contenedor.dataset.urlVersion)).json();
      if (r.version !== contenedor.dataset.version) location.reload();
    } catch { /* sin red: se vuelve a intentar en 10 s */ }
  }, 10000);
})();
