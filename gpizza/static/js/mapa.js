// Mapa con Leaflet + OpenStreetMap (gratuitos, sin clave de API), compartido por el cliente y el repartidor.
// Marcadores: 🛵 repartidor y 🏠 domicilio del cliente (boceto 5).
window.GPizzaMapa = (() => {
  const VERACRUZ = [19.1738, -96.1342]; // centro por si todavía no hay coordenadas

  const icono = (emoji) => L.divIcon({ html: emoji, className: 'gp-marcador', iconSize: [34, 34], iconAnchor: [17, 17] });
  const punto = (lat, lng) => (lat !== '' && lat !== null && lat !== undefined && lng !== '' && lng !== null)
    ? [Number(lat), Number(lng)] : null;

  function crear(elemento, { repartidor, destino }) {
    const mapa = L.map(elemento, { zoomControl: true, attributionControl: true });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; colaboradores de OpenStreetMap',
      // Política de uso de OpenStreetMap: cada mosaico debe indicar el sitio que lo pide (solo el origen).
      referrerPolicy: 'strict-origin-when-cross-origin',
    }).addTo(mapa);

    let marcaRepartidor = repartidor ? L.marker(repartidor, { icon: icono('🛵'), title: 'Repartidor' }).addTo(mapa) : null;
    const marcaDestino = destino ? L.marker(destino, { icon: icono('🏠'), title: 'Domicilio' }).addTo(mapa) : null;

    function encuadrar() {
      const puntos = [marcaRepartidor?.getLatLng(), marcaDestino?.getLatLng()].filter(Boolean);
      if (puntos.length === 2) mapa.fitBounds(L.latLngBounds(puntos), { padding: [40, 40], maxZoom: 16 });
      else mapa.setView(puntos[0] || VERACRUZ, 15);
    }
    encuadrar();

    return {
      mapa,
      moverRepartidor(lat, lng) {
        if (marcaRepartidor) marcaRepartidor.setLatLng([lat, lng]);
        else marcaRepartidor = L.marker([lat, lng], { icon: icono('🛵'), title: 'Repartidor' }).addTo(mapa);
        encuadrar();
      },
      repartidor: () => marcaRepartidor?.getLatLng(),
      destino: () => marcaDestino?.getLatLng(),
    };
  }

  return { crear, punto };
})();
