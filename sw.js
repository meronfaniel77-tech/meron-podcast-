
const CACHE_NAME = 'meron-v1';

// Evento di installazione
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        '/',
        '/logo.png'
      ]);
    })
  );
  self.skipWaiting();
});

// Evento di attivazione
self.addEventListener('activate', (e) => {
  e.waitUntil(self.clients.claim());
});

// Evento Fetch
self.addEventListener('fetch', (e) => {
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
