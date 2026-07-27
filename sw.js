var CACHE = "ren-v3-dongbo";
var ASSETS = ["./", "./index.html", "./manifest.json", "./icon.svg", "./icon-maskable.svg"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(ASSETS) }).then(function () { return self.skipWaiting() }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE }).map(function (k) { return caches.delete(k) }));
  }).then(function () { return self.clients.claim() }));
});

// Trang chính: ưu tiên mạng để luôn nhận bản mới, hỏng mạng thì lấy cache (dùng offline được).
self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  if (req.mode === "navigate" || (req.headers.get("accept") || "").indexOf("text/html") >= 0) {
    e.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put("./index.html", copy) });
        return res;
      }).catch(function () {
        return caches.match("./index.html").then(function (r) { return r || caches.match("./") });
      })
    );
    return;
  }
  e.respondWith(
    caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy) });
        return res;
      });
    })
  );
});
