var CACHE_NAME = "nd-v2";
var STATIC_ASSETS = [
  "/static/css/main.css",
  "/static/js/shared.js",
  "/static/js/tabs.js",
  "/static/js/theme.js",
  "/static/js/summary.js",
  "/static/js/history.js",
  "/static/js/pulse.js",
  "/static/js/budget.js",
  "/static/js/economics.js",
  "/static/js/portfolio.js",
  "/static/js/sentiment.js",
  "/static/js/balances.js",
  "/static/js/holdings.js",
  "/static/js/settings.js",
  "/icon-192.png",
  "/icon-512.png",
  "/manifest.json",
];

self.addEventListener("install", function(e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS);
    })
  );
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

  e.respondWith(
    caches.match(e.request).then(function(cached) {
      var fetched = fetch(e.request).then(function(response) {
        if (response && response.status === 200 && response.type === "basic") {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      }).catch(function() {
        return cached;
      });
      return cached || fetched;
    })
  );
});
