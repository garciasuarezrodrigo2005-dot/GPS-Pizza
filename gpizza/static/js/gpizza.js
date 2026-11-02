// JavaScript común a todas las pantallas de GPizza.

// Registra el service worker para que la app se pueda instalar en el celular (PWA, RNF-007).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) =>
      console.warn('No se pudo registrar el service worker:', error));
  });
}

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
