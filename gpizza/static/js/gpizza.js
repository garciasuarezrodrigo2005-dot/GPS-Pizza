// JavaScript común a todas las pantallas de GPizza.

// Registra el service worker para que la app se pueda instalar en el celular (PWA, RNF-007).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) =>
      console.warn('No se pudo registrar el service worker:', error));
  });
}

// Animaciones de la interfaz (se apagan solas si el sistema pide "reducir movimiento").
const SIN_MOVIMIENTO = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Al abrir una pantalla, sus tarjetas entran suavemente. La clase dura solo la carga inicial: así lo que
// HTMX actualiza cada 10 s no vuelve a "entrar" cada vez.
document.addEventListener('DOMContentLoaded', () => {
  if (SIN_MOVIMIENTO) return;
  document.body.classList.add('gp-entrada');
  setTimeout(() => document.body.classList.remove('gp-entrada'), 1400);
});

// Onda al tocar un botón, como en las apps de celular: confirma que el toque se registró.
document.addEventListener('pointerdown', (evento) => {
  if (SIN_MOVIMIENTO) return;
  const boton = evento.target.closest('.btn, .gp-chip, .gp-tamano, .gp-boton-cantidad, .gp-segmentado label');
  if (!boton || boton.disabled) return;
  const caja = boton.getBoundingClientRect();
  const onda = document.createElement('span');
  const lado = Math.max(caja.width, caja.height) * 2;
  onda.className = 'gp-onda';
  onda.style.cssText = `width:${lado}px;height:${lado}px;left:${evento.clientX - caja.left - lado / 2}px;top:${evento.clientY - caja.top - lado / 2}px`;
  boton.appendChild(onda);
  onda.addEventListener('animationend', () => onda.remove());
});

// Menús que se deslizan a lo ancho en el celular: lleva la opción activa a la vista.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.gp-menu-lateral nav a.activa, .gp-pestanas-estado .activa').forEach((activa) => {
    const fila = activa.parentElement;
    if (fila.scrollWidth > fila.clientWidth) fila.scrollLeft = activa.offsetLeft - (fila.clientWidth - activa.offsetWidth) / 2;
  });
});

// Protección CSRF (RNF-003): HTMX envía el token en una cabecera en cada petición que modifica datos.
document.addEventListener('htmx:configRequest', (evento) => {
  const token = document.querySelector('meta[name="csrf-token"]');
  if (token) evento.detail.headers['X-CSRFToken'] = token.content;
});
