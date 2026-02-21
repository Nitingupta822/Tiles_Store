const CACHE_NAME = 'tiles-stock-v1';
const ASSETS_TO_CACHE = [
  '/static/manifest.json',
  '/static/logo.png',
  '/static/css/style.css' // Assuming this exists, if not it will fail gracefully in most implementations or we can remove it.
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch(err => console.log('Cache addAll error', err));
    })
  );
});

self.addEventListener('fetch', (event) => {
  // Network first, fall back to cache for HTML/dynamic content usually better for stock apps
  // But for static assets, cache first is better.

  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          return caches.match(event.request);
        })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
