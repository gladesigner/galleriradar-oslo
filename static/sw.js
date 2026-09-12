/* Enkel servicearbeider: gjør appen installerbar og viser siste liste uten nett. */
const CACHE = 'galleriradar-1';
const GRUNNMUR = ['/', '/static/stil.css?v=1', '/static/app.js?v=1', '/static/ikon-192.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(GRUNNMUR)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((n) =>
    Promise.all(n.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  // Nett først, med hurtigbufferet kopi som reserve når mobilen er uten dekning.
  e.respondWith(
    fetch(e.request)
      .then((svar) => {
        const kopi = svar.clone();
        caches.open(CACHE).then((c) => c.put(e.request, kopi));
        return svar;
      })
      .catch(() => caches.match(e.request).then((t) => t || caches.match('/')))
  );
});
