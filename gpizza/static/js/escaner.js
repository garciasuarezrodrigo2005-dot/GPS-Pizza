// RF-009: agregar productos al pedido escaneando su código QR o de barras.
// - Lector USB: funciona como un teclado; "escribe" el código en el campo y presiona Enter.
// - Celular: la cámara lee el QR con html5-qrcode (requiere HTTPS, igual que el GPS).
(() => {
  const campo = document.getElementById('escaner-codigo');
  const form = document.getElementById('form-pedido');
  if (!campo || !form) return;
  const mensaje = document.getElementById('escaner-mensaje');

  function agregar(codigo) {
    codigo = codigo.trim().toUpperCase();
    if (!codigo) return;
    const tamano = form.querySelector(`.gp-tamano[data-qr="${CSS.escape(codigo)}"]`);
    if (!tamano) { mensaje.textContent = `No hay un producto con el código ${codigo}.`; return; }
    if (tamano.disabled) { mensaje.textContent = `${tamano.dataset.nombre} está agotado.`; return; }
    const lista = tamano.closest('[data-categoria]');
    form.querySelector(`[data-pestana="${lista.dataset.categoria}"]`).click();   // abre Pizzas o Complementos
    tamano.click();                                                            // elige el tamaño
    const tarjeta = tamano.closest('[data-producto]');
    tarjeta.querySelector('[data-mas]').click();                               // suma uno (respeta RN-003)
    tarjeta.scrollIntoView({ block: 'center', behavior: 'smooth' });
    mensaje.textContent = `Agregado: ${tamano.dataset.nombre}.`;
  }

  campo.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); agregar(campo.value); campo.value = ''; }
  });

  const boton = document.getElementById('escaner-camara');
  let lector = null;
  boton?.addEventListener('click', async () => {
    if (lector) { await lector.stop(); lector = null; boton.textContent = 'Escanear con la cámara'; return; }
    if (!window.isSecureContext) { mensaje.textContent = 'La cámara requiere HTTPS; usa un lector USB o escribe el código.'; return; }
    lector = new Html5Qrcode('escaner-video');
    boton.textContent = 'Detener cámara';
    try {
      await lector.start({ facingMode: 'environment' }, { fps: 10, qrbox: 220 }, (texto) => {
        agregar(texto);
        lector.pause(true);
        setTimeout(() => lector?.resume(), 1200);   // pausa breve para no sumar el mismo producto dos veces
      });
    } catch {
      mensaje.textContent = 'No se pudo abrir la cámara.';
      lector = null; boton.textContent = 'Escanear con la cámara';
    }
  });
})();
