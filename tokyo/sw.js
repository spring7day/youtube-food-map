/* 도쿄 산보 — 서비스 워커
 *
 * 여행 중 데이터가 끊겨도 일정·설명·주문 문장은 그대로 떠야 한다.
 * 앱 셸과 일정 데이터는 프리캐시하고, 지도 타일과 영상 썸네일은
 * 한 번 본 것만 런타임 캐시한다.
 *
 * 캐시를 갈아엎으려면 VERSION을 올린다.
 */
const VERSION = "v1";

const SHELL = `sanpo-shell-${VERSION}`;
const VENDOR = `sanpo-vendor-${VERSION}`;
const TILES = "sanpo-tiles-v1";
const IMGS = "sanpo-imgs-v1";

const CURRENT = [SHELL, VENDOR, TILES, IMGS];
const INDEX_URL = new URL("./", self.location).href;

const SHELL_URLS = [
  "./",
  "./data.js",
  "./manifest.webmanifest",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

const VENDOR_URLS = [
  "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
  "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
  "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
];

const NAV_TIMEOUT_MS = 3500;
const MAX_TILES = 1200;   // 도쿄 시내 여러 권역을 담기 위해 넉넉히
const MAX_IMGS = 120;
const TRIM_EVERY = 40;

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const shell = await caches.open(SHELL);
    await shell.addAll(SHELL_URLS);
    const vendor = await caches.open(VENDOR);
    await Promise.allSettled(VENDOR_URLS.map((u) => vendor.add(u)));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n.startsWith("sanpo-") && !CURRENT.includes(n))
      .map((n) => caches.delete(n)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.protocol !== "http:" && url.protocol !== "https:") return;

  if (request.mode === "navigate") { e.respondWith(handleNavigation(request)); return; }

  if (isTile(url.hostname)) { e.respondWith(cacheFirstCapped(request, TILES, MAX_TILES)); return; }

  // 유튜브 썸네일 — 영상 근거 이미지
  if (url.hostname === "i.ytimg.com" || url.hostname.endsWith(".ytimg.com")) {
    e.respondWith(cacheFirstCapped(request, IMGS, MAX_IMGS)); return;
  }

  if (url.hostname === "unpkg.com") { e.respondWith(staleWhileRevalidate(request, VENDOR)); return; }

  if (url.origin === self.location.origin) { e.respondWith(cacheFirst(request, SHELL)); }
});

const isTile = (h) => h === "tile.openstreetmap.org" || h.endsWith(".tile.openstreetmap.org");

// 문서는 네트워크 우선 → 캐시 폴백. 온라인이면 항상 최신 일정을 받는다.
async function handleNavigation(request) {
  const cache = await caches.open(SHELL);
  const fetching = fetch(request).then((res) => {
    if (res && res.ok) cache.put(INDEX_URL, res.clone()).catch(() => {});
    return res;
  });
  try {
    return await withTimeout(fetching, NAV_TIMEOUT_MS);
  } catch (err) {
    const cached = await cache.match(INDEX_URL);
    if (cached) return cached;
    return fetching;
  }
}

async function cacheFirstCapped(request, name, max) {
  const cache = await caches.open(name);
  const hit = await cache.match(request);
  if (hit) return hit;
  try {
    const res = await fetch(request);
    if (res && res.ok) {
      await cache.put(request, res.clone()).catch(() => {});
      trim(cache, name, max);
    }
    return res;
  } catch (err) {
    return new Response("", { status: 504, statusText: "offline" });
  }
}

async function staleWhileRevalidate(request, name) {
  const cache = await caches.open(name);
  const hit = await cache.match(request);
  const net = fetch(request).then((res) => {
    if (res && (res.ok || res.type === "opaque")) cache.put(request, res.clone()).catch(() => {});
    return res;
  }).catch(() => null);
  if (hit) return hit;
  return (await net) || new Response("", { status: 504, statusText: "offline" });
}

async function cacheFirst(request, name) {
  const cache = await caches.open(name);
  const hit = await cache.match(request);
  if (hit) return hit;
  try {
    const res = await fetch(request);
    if (res && res.ok) cache.put(request, res.clone()).catch(() => {});
    return res;
  } catch (err) {
    return new Response("", { status: 504, statusText: "offline" });
  }
}

// Cache API는 삽입 순서를 유지하므로 앞에서부터 지우면 FIFO 축출이 된다.
const counters = {};
function trim(cache, name, max) {
  counters[name] = (counters[name] || 0) + 1;
  if (counters[name] < TRIM_EVERY) return;
  counters[name] = 0;
  cache.keys().then((keys) => {
    const excess = keys.length - max;
    if (excess > 0) return Promise.all(keys.slice(0, excess).map((k) => cache.delete(k)));
  }).catch(() => {});
}

function withTimeout(p, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error("timeout")), ms);
    p.then((v) => { clearTimeout(t); resolve(v); },
           (e) => { clearTimeout(t); reject(e); });
  });
}
