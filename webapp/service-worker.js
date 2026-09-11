const CACHE_NAME = 'gorev-maliyet-v3.7.0';
const APP_SHELL = ['./', './index.html', './style.css', './calc.js', './db.js', './sync.js', './app.js'];
const TELEGRAM_SDK_HOST = 'telegram.org';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

// Sorgu parametreleri (bot önizleme verisi, ?v=) önbellek anahtarına dahil edilmez.
function cacheKey(url) {
  return new Request(url.origin + url.pathname);
}

function putInCache(request, response) {
  if (!response || (!response.ok && response.type !== 'opaque')) return;
  const copy = response.clone();
  caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // Sayfa: önce ağ (güncellemeler hemen gelsin), çevrimdışıysa önbellek.
  if (request.mode === 'navigate' && url.origin === self.location.origin) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          putInCache(cacheKey(url), response);
          return response;
        })
        .catch(() =>
          caches
            .match(request, { ignoreSearch: true })
            .then((cached) => cached || caches.match('./index.html'))
        )
    );
    return;
  }

  // Statik dosyalar ve Telegram SDK: önbellekten hızlı yanıt, arka planda yenile.
  if (url.origin === self.location.origin || url.hostname === TELEGRAM_SDK_HOST) {
    const key = url.origin === self.location.origin ? cacheKey(url) : request;
    event.respondWith(
      caches.match(key, { ignoreSearch: url.origin === self.location.origin }).then((cached) => {
        const network = fetch(request)
          .then((response) => {
            putInCache(key, response);
            return response;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
  }
});
