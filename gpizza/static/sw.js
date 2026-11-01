// Service worker de GPizza (PWA, RNF-007).
// - Guarda en caché los archivos fijos (estilos, scripts, iconos) para que la app abra rápido.
// - Las páginas siempre se piden al servidor; si no hay red, muestra /offline.
// - Nunca guarda en caché datos de pedidos ni respuestas de la API.

const CACHE = 'gpizza-v1';
const ARCHIVOS_FIJOS = [
  '/offline',
  '/static/css/gpizza.css',
  '/static/js/gpizza.js',
  '/static/vendor/bootstrap.min.css',
  '/static/vendor/bootstrap.bundle.min.js',
  '/static/vendor/htmx.min.js',
  '/static/img/icono-192.png',
  '/static/img/icono-512.png',
];

self.addEventListener('install', (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ARCHIVOS_FIJOS)));
  self.skipWaiting();
});

self.addEventListener('activate', (evento) => {
  // Borra cachés de versiones anteriores.
  evento.waitUntil(
    caches.keys().then((nombres) =>
      Promise.all(nombres.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (evento) => {
  const peticion = evento.request;
  const url = new URL(peticion.url);
  if (peticion.method !== 'GET' || url.origin !== location.origin) return;

  if (peticion.mode === 'navigate') {
    evento.respondWith(fetch(peticion).catch(() => caches.match('/offline')));
    return;
  }
  if (url.pathname.startsWith('/static/')) {
    evento.respondWith(caches.match(peticion).then((guardado) => guardado || fetch(peticion)));
  }
});
