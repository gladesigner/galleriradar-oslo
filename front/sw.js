/* Servicearbeider: gjør appen installerbar og lar den vise siste liste uten nett. */
const CACHE = 'galleriradar-2';
const GRUNNMUR = ['./', 'index.html', 'stil.css?v=2', 'app.js?v=2', 'ikon-192.png',
                  'manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE)
    .then((c) => Promise.allSettled(GRUNNMUR.map((u) => c.add(u))))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((n) => Promise.all(n.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  // Nett først, med bufret kopi i bakhånd når mobilen er uten dekning.
  e.respondWith(
    fetch(e.request)
      .then((svar) => {
        const kopi = svar.clone();
        caches.open(CACHE).then((c) => c.put(e.request, kopi));
        return svar;
      })
      .catch(() => caches.match(e.request).then((t) => t || caches.match('index.html')))
  );
});
