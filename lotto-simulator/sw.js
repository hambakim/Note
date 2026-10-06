// 오프라인 캐시: 한 번 열면 인터넷 없이도 플레이 가능
const CACHE = 'lotto-after-v3';
const FILES = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  // 내 파일은 네트워크 우선(업데이트 반영), 실패하면 캐시. 글꼴 같은 외부 파일은 캐시 우선.
  const same = new URL(e.request.url).origin === location.origin;
  e.respondWith(
    same
      ? fetch(e.request).then(r => { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return r; })
          .catch(() => caches.match(e.request).then(r => r || caches.match('./index.html')))
      : caches.match(e.request).then(r => r || fetch(e.request).then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return res; }))
  );
});
