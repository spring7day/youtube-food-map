/* 백년해방 맛집 지도 — 서비스 워커
 *
 * 홈 화면에 추가된 웹앱이 네트워크 없이도 뜨도록 앱 셸을 캐시한다.
 * 식당 데이터 396건은 index.html에 인라인이라, 지도 타일만 없을 뿐
 * 목록/검색/상세는 완전 오프라인으로 동작한다.
 *
 * 캐시를 갱신하려면 VERSION을 올린다.
 */
const VERSION = "v1";

const SHELL = `shell-${VERSION}`;   // 자체 호스팅 자산 (index.html, 아이콘 등)
const VENDOR = `vendor-${VERSION}`; // Leaflet / MarkerCluster (CDN)
const FONTS = "fonts-v1";           // Pretendard (CDN) — 버전과 무관하게 유지
const TILES = "tiles-v1";           // OSM 지도 타일 — 방문한 영역만 런타임 캐시

const CURRENT_CACHES = [SHELL, VENDOR, FONTS, TILES];

const INDEX_URL = new URL("./", self.location).href;

const SHELL_URLS = [
  "./",
  "./manifest.webmanifest",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

const VENDOR_URLS = [
  "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
  "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
  "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css",
  "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css",
  "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js",
  "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
];

const NAV_TIMEOUT_MS = 3500; // 이 시간을 넘기면 캐시본으로 먼저 띄운다
const MAX_TILES = 900;       // 타일 캐시 상한 (대략 40~60MB)
const TRIM_EVERY = 40;       // 타일 N개 저장할 때마다 정리

// ===== 설치 =====
self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL);
    await shell.addAll(SHELL_URLS);

    // CDN은 일시적으로 실패할 수 있으므로 설치를 막지 않는다
    const vendor = await caches.open(VENDOR);
    await Promise.allSettled(VENDOR_URLS.map((url) => vendor.add(url)));

    await self.skipWaiting();
  })());
});

// ===== 활성화 =====
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(
      names
        .filter((name) => !CURRENT_CACHES.includes(name))
        .map((name) => caches.delete(name))
    );
    await self.clients.claim();
  })());
});

// ===== 요청 라우팅 =====
self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.protocol !== "http:" && url.protocol !== "https:") return;

  if (request.mode === "navigate") {
    event.respondWith(handleNavigation(request));
    return;
  }

  if (isTileHost(url.hostname)) {
    event.respondWith(handleTile(request));
    return;
  }

  if (url.hostname === "unpkg.com") {
    event.respondWith(staleWhileRevalidate(request, VENDOR));
    return;
  }

  if (url.hostname === "cdn.jsdelivr.net") {
    event.respondWith(staleWhileRevalidate(request, FONTS));
    return;
  }

  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(request, SHELL));
  }
  // 그 외(유튜브 등)는 브라우저 기본 동작에 맡긴다
});

function isTileHost(hostname) {
  return hostname === "tile.openstreetmap.org"
    || hostname.endsWith(".tile.openstreetmap.org");
}

// 문서 요청: 네트워크 우선 + 타임아웃 → 캐시 폴백.
// 온라인이면 항상 최신 데이터를 받고, 오프라인/느린 회선에서는 즉시 뜬다.
async function handleNavigation(request) {
  const cache = await caches.open(SHELL);
  const fetching = fetch(request).then((response) => {
    if (response && response.ok) {
      cache.put(INDEX_URL, response.clone()).catch(() => {});
    }
    return response;
  });

  try {
    return await withTimeout(fetching, NAV_TIMEOUT_MS);
  } catch (err) {
    const cached = await cache.match(INDEX_URL);
    if (cached) return cached;
    return fetching; // 캐시가 없으면 네트워크를 끝까지 기다린다
  }
}

// 지도 타일: 캐시 우선. 한 번 본 지역은 오프라인에서도 그대로 보인다.
async function handleTile(request) {
  const cache = await caches.open(TILES);
  const cached = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response && response.ok) {
      await cache.put(request, response.clone()).catch(() => {});
      trimTiles(cache);
    }
    return response;
  } catch (err) {
    // 오프라인 + 미캐시 타일. Leaflet이 빈 타일로 처리한다.
    return new Response("", { status: 504, statusText: "offline" });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const network = fetch(request)
    .then((response) => {
      if (response && (response.ok || response.type === "opaque")) {
        cache.put(request, response.clone()).catch(() => {});
      }
      return response;
    })
    .catch(() => null);

  if (cached) return cached;
  return (await network) || new Response("", { status: 504, statusText: "offline" });
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone()).catch(() => {});
    }
    return response;
  } catch (err) {
    return new Response("", { status: 504, statusText: "offline" });
  }
}

let tilePutCount = 0;

// Cache API는 삽입 순서를 유지하므로 앞쪽부터 지우면 FIFO 축출이 된다.
// (엄밀한 LRU는 아니지만 타일 캐시에는 충분하다)
function trimTiles(cache) {
  if (++tilePutCount < TRIM_EVERY) return;
  tilePutCount = 0;
  cache.keys().then((keys) => {
    const excess = keys.length - MAX_TILES;
    if (excess > 0) {
      return Promise.all(keys.slice(0, excess).map((key) => cache.delete(key)));
    }
  }).catch(() => {});
}

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("timeout")), ms);
    promise.then(
      (value) => { clearTimeout(timer); resolve(value); },
      (error) => { clearTimeout(timer); reject(error); }
    );
  });
}
