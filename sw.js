const CACHE = 'osm-game-v5-music';
const FILES = ['./', './index.html', './styles.css', './bootstrap.js', './music.js', './assets/music-theme.mp3', './game.py', './engine.py', './content.py', './scene.svg', './manifest.webmanifest', './assets/icon.svg', './assets/icon-192.png', './assets/icon-512.png', './vendor/brython.min.js'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('osm-game-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(caches.open(CACHE).then(async cache => {
    const cached = await cache.match(event.request, {ignoreSearch: true});
    if (['127.0.0.1', 'localhost', '[::1]'].includes(self.location.hostname)) {
      try { return await fetch(event.request); } catch (error) { if (cached) return cached; throw error; }
    }
    return cached || fetch(event.request);
  }));
});
