/* A cache belongs only to this installation path, never to the whole website. */
const PREFIX = 'osm-pwa-' + self.registration.scope + '-';
const CACHE = PREFIX + '09e303445994f6ed';
const FILES = ['index.html', 'install.js', 'install.css', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'];
const urls = FILES.map(name => new URL(name, self.registration.scope).href);
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(urls.map(url => new Request(url, {cache: 'reload'})));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith(PREFIX) && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  url.search = '';
  url.hash = '';
  let target = url.href;
  if (target === self.registration.scope) target = urls[0];
  if (!urls.includes(target)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    return (await cache.match(target)) || fetch(event.request);
  })());
});
self.addEventListener('message', event => {
  if (event.data?.type !== 'CHECK_OFFLINE' || !event.ports[0]) return;
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const available = await Promise.all(urls.map(url => cache.match(url)));
    event.ports[0].postMessage({offlineReady: available.every(Boolean)});
  })());
});
