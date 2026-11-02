// Service worker de GPizza (PWA, RNF-007).
// - Todo se pide primero a la red, así siempre llega la versión más nueva de la app.
// - Los archivos fijos (estilos, scripts, iconos) se guardan en caché para que la app abra sin conexión.
// - Las páginas sin red muestran /offline. Nunca se guardan datos de pedidos ni respuestas de la API.
// Al cambiar esta estrategia o la lista de archivos, sube el número de CACHE para borrar la anterior.

const CACHE = 'gpizza-v3';
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
    // Primero la red (y se actualiza la copia guardada); la caché solo se usa sin conexión.
    evento.respondWith(
      fetch(peticion)
        .then((respuesta) => {
          const copia = respuesta.clone();
          caches.open(CACHE).then((cache) => cache.put(peticion, copia));
          return respuesta;
        })
        .catch(() => caches.match(peticion))
    );
  }
});
