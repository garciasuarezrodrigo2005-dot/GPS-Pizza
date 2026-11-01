// JavaScript común a todas las pantallas de GPizza.

// Registra el service worker para que la app se pueda instalar en el celular (PWA, RNF-007).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error) =>
      console.warn('No se pudo registrar el service worker:', error));
  });
}

// Protección CSRF (RNF-003): HTMX envía el token en una cabecera en cada petición que modifica datos.
document.addEventListener('htmx:configRequest', (evento) => {
  const token = document.querySelector('meta[name="csrf-token"]');
  if (token) evento.detail.headers['X-CSRFToken'] = token.content;
});
