const REQUEST_DELAY_MS = 250;
const FETCH_TIMEOUT_MS = 12000;
const MAX_SITEMAPS = 24;
const MAX_ARCHIVE_PAGES = 12;
const MAX_REST_PAGES = 10;
const MAX_FEED_URLS = 4;

const COMMON_SITEMAP_PATHS = ["/robots.txt", "/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"];
const FEED_PATHS = ["/feed/", "/?feed=rss2", "/feed/rss/", "/comments/feed/"];
const ARCHIVE_SEEDS = ["/", "/blog/", "/posts/", "/archives/", "/archive/"];

const ARCHIVE_HINTS = [
  /^\/$/i,
  /^\/blog\/?$/i,
  /^\/posts\/?$/i,
  /^\/archives?\/?$/i,
  /^\/page\/\d+\/?$/i,
  /^\/category\/.+/i,
  /^\/tag\/.+/i,
  /^\/author\/.+/i,
  /^\/\d{4}\/\d{1,2}(?:\/\d{1,2})?\/?$/i
];

const DISALLOWED_PATH_FRAGMENTS = [
  "/wp-admin", "/wp-login.php", "/wp-json", "/xmlrpc.php", "/feed", "/comments",
  "/cart", "/checkout", "/my-account", "/preview", "/trackback"
];

const DISALLOWED_DIRECTORY_NAMES = [
  "category", "tag", "author", "page", "search", "attachment", "wp-content", "wp-includes"
];

const DISALLOWED_EXTENSIONS = [
  ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf", ".zip", ".rar", ".7z",
  ".css", ".js", ".json", ".xml", ".txt", ".mp4", ".mp3", ".mov", ".webm"
];

const REST_TYPE_EXCLUSIONS = new Set([
  "attachment", "media", "wp_block", "wp_template", "wp_template_part", "wp_navigation", "nav_menu_item", "user"
]);

const POPULARITY_HINTS = [
  "popular", "trending", "featured", "best", "top", "hot", "editor", "recommended",
  "인기", "추천", "베스트", "핫", "주목"
];

const FEATURE_HINTS = [
  "featured", "spotlight", "hero", "editor", "pick", "special", "featured-post", "대표", "추천", "특집"
];

export function normalizeSiteUrl(rawValue) {
  const value = rawValue.trim();
  if (!value) {
    throw new Error("사이트 주소를 입력하세요.");
  }

  const candidate = /^https?:\/\//i.test(value) ? value : `https://${value}`;
  const url = new URL(candidate);
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("http 또는 https 주소만 사용할 수 있습니다.");
  }

  url.hash = "";
  url.search = "";
  url.pathname = "/";
  return url.toString();
}

export function toOriginPattern(siteUrl) {
  const url = new URL(siteUrl);
  return `${url.protocol}//${url.host}/*`;
}

export function normalizeSameSiteUrl(candidate, siteUrl) {
  const baseUrl = siteUrl instanceof URL ? siteUrl : new URL(siteUrl);
  return normalizeDiscoveredUrl(candidate, baseUrl);
}

export function isSameSite(candidate, siteUrl) {
  const url = candidate instanceof URL ? candidate : new URL(candidate);
  const baseUrl = siteUrl instanceof URL ? siteUrl : new URL(siteUrl);
  return canonicalHost(url.hostname) === canonicalHost(baseUrl.hostname);
}

export function isLikelyContentUrl(candidate, siteUrl) {
  const url = candidate instanceof URL ? candidate : new URL(candidate);
  const baseUrl = siteUrl instanceof URL ? siteUrl : new URL(siteUrl);
  const pathname = url.pathname.toLowerCase();
  const segments = pathname.split("/").filter(Boolean);

  if (!isSameSite(url, baseUrl)) {
    return false;
  }
  if (pathname === "/" && !url.search) {
    return false;
  }
  if (url.searchParams.has("preview") || url.searchParams.has("elementor_library") || url.searchParams.has("s")) {
    return false;
  }
  if (DISALLOWED_PATH_FRAGMENTS.some((fragment) => pathname.includes(fragment))) {
    return false;
  }
  if (DISALLOWED_EXTENSIONS.some((extension) => pathname.endsWith(extension))) {
    return false;
  }
  if (segments.some((segment) => DISALLOWED_DIRECTORY_NAMES.includes(segment.toLowerCase()))) {
    return false;
  }

  return true;
}

export async function fetchTextWithTimeout(url, acceptHeader) {
  const response = await fetchWithTimeout(url, {
    headers: { "Accept": acceptHeader },
    credentials: "omit",
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`응답 ${response.status}`);
  }

  return response.text();
}

export async function collectPublicUrls(siteUrl, onProgress = () => {}) {
  const baseUrl = new URL(siteUrl);
  const urlSources = new Map();
  const notes = [];
  const errors = [];
  const sourceStats = [];
  let archiveSignals = new Map();

  await runSource("Sitemap", async () => {
    const urls = await collectFromSitemaps(baseUrl, onProgress);
    mergeUrls(urlSources, urls, "Sitemap", baseUrl);
    return urls.size;
  });

  await runSource("REST API", async () => {
    const urls = await collectFromRestApi(baseUrl, onProgress);
    mergeUrls(urlSources, urls, "REST API", baseUrl);
    return urls.size;
  });

  await runSource("RSS", async () => {
    const urls = await collectFromFeeds(baseUrl, onProgress);
    mergeUrls(urlSources, urls, "RSS", baseUrl);
    return urls.size;
  });

  await runSource("Archive", async () => {
    const result = await collectFromArchives(baseUrl, onProgress);
    archiveSignals = result.signals;
    mergeUrls(urlSources, result.urls, "Archive", baseUrl);
    return result.urls.size;
  });

  const urls = [...urlSources.keys()].sort((left, right) => left.localeCompare(right));

  if (urls.length === 0) {
    notes.push("공개된 URL이 발견되지 않았습니다. 사이트맵 비활성화, REST 비공개, 빈 피드, JS 렌더링 전용 구조일 수 있습니다.");
  }
  if (errors.length > 0) {
    notes.push("일부 소스는 차단되거나 비활성화되어 건너뛰었습니다.");
  }

  return {
    siteUrl: baseUrl.toString(),
    urls,
    sourceStats,
    notes,
    errors,
    urlSourceMap: Object.fromEntries([...urlSources.entries()].map(([url, sources]) => [url, [...sources].sort()])),
    archiveSignals: Object.fromEntries([...archiveSignals.entries()].map(([url, value]) => [url, value]))
  };

  async function runSource(label, worker) {
    onProgress(`${label} 조회 중...`);
    try {
      const count = await worker();
      sourceStats.push({ label, count });
      onProgress(`${label} 완료: ${count}개 URL 후보`);
    } catch (error) {
      sourceStats.push({ label, count: 0 });
      errors.push(`${label}: ${error.message}`);
      onProgress(`${label} 건너뜀: ${error.message}`);
    }
  }
}

async function collectFromSitemaps(baseUrl, onProgress) {
  const sitemapQueue = await discoverSitemaps(baseUrl);
  const visited = new Set();
  const collected = new Set();

  while (sitemapQueue.length > 0 && visited.size < MAX_SITEMAPS) {
    const sitemapUrl = sitemapQueue.shift();
    if (!sitemapUrl || visited.has(sitemapUrl)) {
      continue;
    }

    visited.add(sitemapUrl);
    onProgress(`Sitemap 조회: ${sitemapUrl}`);

    const xmlText = await fetchTextWithTimeout(sitemapUrl, "application/xml, text/xml, */*;q=0.1");
    const xml = parseXml(xmlText);
    const locs = getElementsByLocalName(xml, "loc").map((node) => node.textContent?.trim()).filter(Boolean);

    for (const loc of locs) {
      const normalized = normalizeDiscoveredUrl(loc, baseUrl);
      if (!normalized) {
        continue;
      }
      if (looksLikeSitemap(normalized)) {
        if (!visited.has(normalized) && sitemapQueue.length + visited.size < MAX_SITEMAPS) {
          sitemapQueue.push(normalized);
        }
        continue;
      }
      if (isLikelyContentUrl(normalized, baseUrl)) {
        collected.add(normalized);
      }
    }

    await delay(REQUEST_DELAY_MS);
  }

  return collected;
}

async function discoverSitemaps(baseUrl) {
  const queue = new Set();
  for (const path of COMMON_SITEMAP_PATHS) {
    if (path !== "/robots.txt") {
      queue.add(new URL(path, baseUrl).toString());
    }
  }

  try {
    const robotsText = await fetchTextWithTimeout(new URL("/robots.txt", baseUrl).toString(), "text/plain, */*;q=0.1");
    for (const line of robotsText.split(/\r?\n/)) {
      const match = line.match(/^Sitemap:\s*(.+)$/i);
      if (!match) {
        continue;
      }
      const normalized = normalizeDiscoveredUrl(match[1].trim(), baseUrl);
      if (normalized && looksLikeSitemap(normalized)) {
        queue.add(normalized);
      }
    }
  } catch (error) {
    // robots.txt is optional
  }

  return [...queue];
}

async function collectFromRestApi(baseUrl, onProgress) {
  const json = await fetchJson(new URL("/wp-json/wp/v2/types", baseUrl).toString());
  const types = [];

  for (const [slug, definition] of Object.entries(json)) {
    if (!definition?.viewable || !definition?.rest_base || REST_TYPE_EXCLUSIONS.has(slug)) {
      continue;
    }
    types.push({ slug, restBase: definition.rest_base });
  }

  const collected = new Set();

  for (const type of types) {
    let currentPage = 1;
    let totalPages = 1;

    while (currentPage <= totalPages && currentPage <= MAX_REST_PAGES) {
      const endpoint = new URL(`/wp-json/wp/v2/${type.restBase}`, baseUrl);
      endpoint.searchParams.set("per_page", "100");
      endpoint.searchParams.set("page", String(currentPage));
      endpoint.searchParams.set("_fields", "link");

      onProgress(`REST API 조회: ${type.slug} page ${currentPage}`);

      const response = await fetch(endpoint.toString(), {
        headers: { "Accept": "application/json" },
        credentials: "omit",
        cache: "no-store"
      });
      if (!response.ok) {
        throw new Error(`REST 응답 ${response.status}`);
      }

      const items = await response.json();
      totalPages = Number(response.headers.get("x-wp-totalpages") || "1");

      for (const item of items) {
        const normalized = normalizeDiscoveredUrl(item?.link, baseUrl);
        if (normalized && isLikelyContentUrl(normalized, baseUrl)) {
          collected.add(normalized);
        }
      }

      currentPage += 1;
      await delay(REQUEST_DELAY_MS);
    }
  }

  return collected;
}

async function collectFromFeeds(baseUrl, onProgress) {
  const collected = new Set();
  let attempts = 0;

  for (const path of FEED_PATHS) {
    if (attempts >= MAX_FEED_URLS) {
      break;
    }

    attempts += 1;
    const feedUrl = new URL(path, baseUrl).toString();
    onProgress(`RSS 조회: ${feedUrl}`);

    try {
      const xmlText = await fetchTextWithTimeout(feedUrl, "application/rss+xml, application/xml, text/xml, */*;q=0.1");
      const xml = parseXml(xmlText);
      const links = [
        ...getElementsByLocalName(xml, "item").flatMap((item) => getElementsByLocalName(item, "link")),
        ...getElementsByLocalName(xml, "entry").flatMap((entry) => getElementsByLocalName(entry, "link"))
      ];

      for (const node of links) {
        const href = node.getAttribute?.("href") || node.textContent;
        const normalized = normalizeDiscoveredUrl(href, baseUrl);
        if (normalized && isLikelyContentUrl(normalized, baseUrl)) {
          collected.add(normalized);
        }
      }
    } catch (error) {
      // feeds are optional
    }

    await delay(REQUEST_DELAY_MS);
  }

  return collected;
}

async function collectFromArchives(baseUrl, onProgress) {
  const queue = ARCHIVE_SEEDS.map((path) => new URL(path, baseUrl).toString());
  const visited = new Set();
  const collected = new Set();
  const signals = new Map();

  while (queue.length > 0 && visited.size < MAX_ARCHIVE_PAGES) {
    const pageUrl = queue.shift();
    if (!pageUrl || visited.has(pageUrl)) {
      continue;
    }

    visited.add(pageUrl);
    onProgress(`아카이브 조회: ${pageUrl}`);

    let htmlText;
    try {
      htmlText = await fetchTextWithTimeout(pageUrl, "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");
    } catch (error) {
      await delay(REQUEST_DELAY_MS);
      continue;
    }

    const html = new DOMParser().parseFromString(htmlText, "text/html");
    const anchors = [...html.querySelectorAll("a[href]")];

    for (const anchor of anchors) {
      const normalized = normalizeDiscoveredUrl(anchor.getAttribute("href"), baseUrl);
      if (!normalized) {
        continue;
      }
      if (isLikelyContentUrl(normalized, baseUrl)) {
        collected.add(normalized);
        recordArchiveSignal(signals, normalized, pageUrl, anchor);
      }
      if (isLikelyArchiveUrl(normalized, baseUrl, anchor) && !visited.has(normalized) && !queue.includes(normalized)) {
        queue.push(normalized);
      }
    }

    await delay(REQUEST_DELAY_MS);
  }

  return { urls: collected, signals };
}

function recordArchiveSignal(signals, url, pageUrl, anchor) {
  const entry = signals.get(url) || { references: 0, rootReferences: 0, popularityHints: 0, featureHints: 0 };
  entry.references += 1;

  const fromPath = new URL(pageUrl).pathname.toLowerCase();
  if (fromPath === "/" || /^\/(?:blog|posts|archives?|archive)\/?$/i.test(fromPath)) {
    entry.rootReferences += 1;
  }

  const contextText = getAnchorContextText(anchor);
  if (POPULARITY_HINTS.some((hint) => contextText.includes(hint))) {
    entry.popularityHints += 1;
  }
  if (FEATURE_HINTS.some((hint) => contextText.includes(hint))) {
    entry.featureHints += 1;
  }

  signals.set(url, entry);
}

function getAnchorContextText(anchor) {
  const parts = [];
  const containers = [
    anchor,
    anchor.closest("li"),
    anchor.closest("article"),
    anchor.closest("section"),
    anchor.closest("aside"),
    anchor.closest("nav"),
    anchor.closest("div")
  ].filter(Boolean);

  for (const node of containers) {
    if (typeof node.className === "string") {
      parts.push(node.className);
    }
    if (typeof node.id === "string") {
      parts.push(node.id);
    }
    const heading = node.querySelector?.("h1, h2, h3, h4, strong");
    if (heading?.textContent) {
      parts.push(heading.textContent);
    }
  }

  return parts.join(" ").toLowerCase();
}

function normalizeDiscoveredUrl(candidate, baseUrl) {
  if (!candidate) {
    return null;
  }
  try {
    const url = new URL(candidate, baseUrl);
    if (!["http:", "https:"].includes(url.protocol) || !isSameSite(url, baseUrl)) {
      return null;
    }
    url.hash = "";
    return url.toString();
  } catch (error) {
    return null;
  }
}

function isLikelyArchiveUrl(candidate, baseUrl, anchor) {
  const url = new URL(candidate);
  const pathname = url.pathname.toLowerCase();
  const linkText = anchor?.textContent?.trim().toLowerCase() || "";
  const rel = anchor?.rel?.toLowerCase() || "";

  if (!isSameSite(url, baseUrl)) {
    return false;
  }
  if (DISALLOWED_PATH_FRAGMENTS.some((fragment) => pathname.includes(fragment))) {
    return false;
  }
  if (ARCHIVE_HINTS.some((pattern) => pattern.test(pathname))) {
    return true;
  }
  if (rel.includes("next") || rel.includes("prev")) {
    return true;
  }

  return ["older", "newer", "next", "previous", "다음", "이전", "더보기"].some((word) => linkText.includes(word));
}

function mergeUrls(target, urls, sourceLabel, baseUrl) {
  for (const value of urls) {
    const normalized = normalizeDiscoveredUrl(value, baseUrl);
    if (!normalized || !isLikelyContentUrl(normalized, baseUrl)) {
      continue;
    }
    const sources = target.get(normalized) || new Set();
    sources.add(sourceLabel);
    target.set(normalized, sources);
  }
}

function looksLikeSitemap(url) {
  try {
    const pathname = new URL(url).pathname.toLowerCase();
    return pathname.endsWith(".xml") || pathname.includes("sitemap");
  } catch (error) {
    return false;
  }
}

function parseXml(xmlText) {
  const xml = new DOMParser().parseFromString(xmlText, "application/xml");
  if (xml.querySelector("parsererror")) {
    throw new Error("XML 파싱 실패");
  }
  return xml;
}

function getElementsByLocalName(root, localName) {
  const exactMatches = [...root.getElementsByTagName(localName)];
  return exactMatches.length > 0 ? exactMatches : [...root.getElementsByTagNameNS("*", localName)];
}

async function fetchJson(url) {
  const text = await fetchTextWithTimeout(url, "application/json, */*;q=0.1");
  return JSON.parse(text);
}

async function fetchWithTimeout(url, init) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("요청 시간 초과");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

function canonicalHost(hostname) {
  return hostname.replace(/^www\./i, "").toLowerCase();
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
