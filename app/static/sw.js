var CACHE_NAME = "nd-v5";

self.addEventListener("install", function(e) {
  self.skipWaiting();
});

self.addEventListener("activate", function(e) {
  e.waitUntil(
    caches.keys().then(function(names) {
      return Promise.all(
        names.filter(function(n) { return n !== CACHE_NAME; })
             .map(function(n) { return caches.delete(n); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function(e) {
  var url = new URL(e.request.url);

  if (url.pathname.startsWith("/api/")) return;
  if (e.request.method !== "GET") return;
  if (e.request.mode === "navigate") return;

  var isStatic = /\.(js|css|png|jpg|ico|woff2?|json)(\?|$)/.test(url.pathname);
  if (!isStatic) return;

  e.respondWith(
    fetch(e.request).then(function(response) {
      if (response && response.status === 200 && response.type === "basic") {
        var clone = response.clone();
        caches.open(CACHE_NAME).then(function(cache) {
          cache.put(e.request, clone);
        });
      }
      return response;
    }).catch(function() {
      return caches.match(e.request);
    })
  );
});
