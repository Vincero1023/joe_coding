importScripts("catalog.js");

const STORAGE_KEY = "agodaFinderConfig";
const STATE_KEY = "agodaFinderState";
const RESULTS_PAGE_PATH = "results.html";
const SCAN_CONCURRENCY = 6;
const SCENARIO_TIMEOUT_MS = 5000;
const SCAN_DOM_READY_TIMEOUT_MS = 1800;
const SCAN_PRICE_WAIT_MS = 3000;
const SCAN_TAB_POLL_INTERVAL_MS = 120;

let scanState = createIdleState();
let currentScan = null;
let resultsPageTabId = null;

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!currentScan || tabId !== currentScan.sourceTabId || currentScan.ignoreSourceUrlChanges) {
    return;
  }

  const nextUrl = changeInfo.url || tab?.url;
  if (!nextUrl) {
    return;
  }

  if (normalizeComparableUrl(nextUrl) !== currentScan.sourceUrl) {
    cancelCurrentScan("Source page changed. Scan stopped.", { clearResults: true });
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === resultsPageTabId) {
    resultsPageTabId = null;
  }

  if (!currentScan || tabId !== currentScan.sourceTabId) {
    return;
  }

  cancelCurrentScan("Source tab closed. Scan stopped.", { clearResults: true });
});

chrome.runtime.onInstalled.addListener(async () => {
  await ensureDefaults();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message)
    .then((response) => sendResponse({ ok: true, ...response }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));

  return true;
});

async function handleMessage(message) {
  if (!message?.type) {
    throw new Error("Invalid message.");
  }

  if (message.type === "getState") {
    await ensureDefaults();
    return {
      config: await getConfig(),
      scanState
    };
  }

  if (message.type === "saveConfig") {
    const config = sanitizeConfig(message.config);
    await chrome.storage.local.set({ [STORAGE_KEY]: config });
    return { config };
  }

  if (message.type === "resetConfig") {
    const config = createDefaultConfig();
    await chrome.storage.local.set({ [STORAGE_KEY]: config });
    return { config };
  }

  if (message.type === "scanCatalog") {
    if (scanState.running) {
      throw new Error("A scan is already running.");
    }

    const config = sanitizeConfig(message.config || (await getConfig()));
    await chrome.storage.local.set({ [STORAGE_KEY]: config });
    const tabId = await resolveTargetTabId(message.tabId);
    let resultsTab = null;

    if (message.showResultsPage !== false) {
      resultsTab = await ensureResultsPageTab({
        active: Boolean(message.focusResultsPage ?? true),
        openerTabId: tabId
      });
    }

    runCatalogScan(tabId, config, { openBest: Boolean(message.openBest) }).catch((error) => {
      failScan(error);
    });

    return { scanState, resultsTabId: resultsTab?.id || null };
  }

  if (message.type === "openResultsPage") {
    const tab = await ensureResultsPageTab({
      active: Boolean(message.active ?? true),
      openerTabId: message.openerTabId || null
    });
    return {
      tabId: tab.id,
      url: tab.url
    };
  }

  if (message.type === "stopScan") {
    const stopped = cancelCurrentScan("Stopped by user.");
    if (!stopped) {
      return { stopped: false, scanState };
    }

    return { stopped: true, scanState };
  }

  throw new Error(`Unsupported message type: ${message.type}`);
}

function createDefaultConfig() {
  return {
    autoRunOnOpen: true,
    selectedTrafficIds: [...AGODA_DEFAULT_SELECTIONS.traffic],
    selectedCardIds: [...AGODA_DEFAULT_SELECTIONS.cards],
    selectedAirlineIds: [...AGODA_DEFAULT_SELECTIONS.airlines],
    selectedPromoIds: [...AGODA_DEFAULT_SELECTIONS.promos]
  };
}

function createIdleState() {
  return {
    running: false,
    mode: "idle",
    message: "",
    currentIndex: 0,
    total: 0,
    startedAt: null,
    finishedAt: null,
    openedRank: null,
    comparable: true,
    results: [],
    currentPageResult: null,
    diagnosticsNote: "",
    sourceTabId: null,
    sourceUrl: "",
    sourceTitle: "",
    updatedAt: null
  };
}

function createScanContext(sourceTabId, sourceUrl) {
  return {
    id: crypto.randomUUID(),
    sourceTabId,
    sourceUrl: normalizeComparableUrl(sourceUrl),
    cancelled: false,
    reason: "",
    scanTabIds: new Set(),
    ignoreSourceUrlChanges: false,
    clearResultsOnCancel: false
  };
}

function normalizeComparableUrl(url) {
  if (!url) {
    return "";
  }

  try {
    const parsed = new URL(url);
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return String(url);
  }
}

function getResultsPageUrl() {
  return chrome.runtime.getURL(RESULTS_PAGE_PATH);
}

async function ensureResultsPageTab(options = {}) {
  const targetUrl = getResultsPageUrl();
  const existingTab = await resolveResultsPageTab(targetUrl);
  const shouldActivate = options.active !== false;

  if (existingTab?.id) {
    resultsPageTabId = existingTab.id;
    if (shouldActivate) {
      await chrome.tabs.update(existingTab.id, { active: true });
      if (Number.isFinite(existingTab.windowId)) {
        await chrome.windows.update(existingTab.windowId, { focused: true }).catch(() => {});
      }
    }
    return existingTab;
  }

  const createOptions = {
    url: targetUrl,
    active: shouldActivate
  };

  if (Number.isFinite(options.openerTabId)) {
    const openerTab = await chrome.tabs.get(options.openerTabId).catch(() => null);
    if (openerTab) {
      createOptions.windowId = openerTab.windowId;
      createOptions.index = openerTab.index + 1;
    }
  }

  const createdTab = await chrome.tabs.create(createOptions);
  resultsPageTabId = createdTab.id;
  return createdTab;
}

async function resolveResultsPageTab(targetUrl) {
  if (resultsPageTabId) {
    const knownTab = await chrome.tabs.get(resultsPageTabId).catch(() => null);
    if (knownTab?.id && knownTab.url === targetUrl) {
      return knownTab;
    }
    resultsPageTabId = null;
  }

  const matchingTabs = await chrome.tabs.query({ url: targetUrl }).catch(() => []);
  const existingTab = matchingTabs[0] || null;
  if (existingTab?.id) {
    resultsPageTabId = existingTab.id;
  }
  return existingTab;
}

function createCancelledError(message) {
  const error = new Error(message || "Scan stopped.");
  error.name = "ScanCancelledError";
  return error;
}

function isCancelledError(error) {
  return error?.name === "ScanCancelledError";
}

function cancelCurrentScan(reason, options = {}) {
  if (!currentScan) {
    return false;
  }

  currentScan.cancelled = true;
  currentScan.reason = reason || currentScan.reason || "Scan stopped.";
  currentScan.clearResultsOnCancel = currentScan.clearResultsOnCancel || Boolean(options.clearResults);
  updateScanState({
    message: currentScan.reason || "Stopping scan..."
  });

  const tabIds = Array.from(currentScan.scanTabIds);
  currentScan.scanTabIds.clear();
  tabIds.forEach((tabId) => {
    chrome.tabs.remove(tabId).catch(() => {});
  });

  return true;
}

function throwIfScanCancelled(scanContext) {
  if (!scanContext?.cancelled) {
    return;
  }

  throw createCancelledError(scanContext.reason || "Scan stopped.");
}

async function ensureSourceTabUnchanged(scanContext) {
  throwIfScanCancelled(scanContext);

  const sourceTab = await chrome.tabs.get(scanContext.sourceTabId).catch(() => null);
  if (!sourceTab?.id || !sourceTab.url) {
    scanContext.cancelled = true;
    scanContext.reason = scanContext.reason || "Source tab closed. Scan stopped.";
    scanContext.clearResultsOnCancel = true;
    throwIfScanCancelled(scanContext);
  }

  const currentUrl = normalizeComparableUrl(sourceTab.url);
  if (!scanContext.ignoreSourceUrlChanges && currentUrl !== scanContext.sourceUrl) {
    scanContext.cancelled = true;
    scanContext.reason = scanContext.reason || "Source page changed. Scan stopped.";
    scanContext.clearResultsOnCancel = true;
    throwIfScanCancelled(scanContext);
  }
}

async function sleepWithCancellation(ms, scanContext) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    throwIfScanCancelled(scanContext);
    await sleep(Math.min(250, deadline - Date.now()));
  }
}

async function ensureDefaults() {
  const stored = await chrome.storage.local.get([STORAGE_KEY, STATE_KEY]);

  if (!stored[STORAGE_KEY]) {
    await chrome.storage.local.set({ [STORAGE_KEY]: createDefaultConfig() });
  }

  if (stored[STATE_KEY]) {
    scanState = { ...createIdleState(), ...stored[STATE_KEY] };
  }
}

async function getConfig() {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  return sanitizeConfig(stored[STORAGE_KEY] || createDefaultConfig());
}

function sanitizeConfig(config) {
  return {
    autoRunOnOpen: Boolean(config?.autoRunOnOpen ?? true),
    selectedTrafficIds: sanitizeIdList(
      config?.selectedTrafficIds,
      AGODA_CATALOG.traffic,
      AGODA_DEFAULT_SELECTIONS.traffic
    ),
    selectedCardIds: sanitizeIdList(config?.selectedCardIds, AGODA_CATALOG.cards, []),
    selectedAirlineIds: sanitizeIdList(config?.selectedAirlineIds, AGODA_CATALOG.airlines, []),
    selectedPromoIds: sanitizeIdList(config?.selectedPromoIds, AGODA_CATALOG.promos, [])
  };
}

function sanitizeIdList(value, entries, fallbackIds) {
  const knownIds = new Set(entries.map((entry) => entry.id));
  const rawIds = Array.isArray(value) ? value : fallbackIds;
  return Array.from(new Set(rawIds.filter((id) => knownIds.has(id))));
}

async function resolveTargetTabId(tabId) {
  if (tabId) {
    const tab = await chrome.tabs.get(tabId);
    validateAgodaTab(tab);
    return tab.id;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  validateAgodaTab(tab);
  return tab.id;
}

function validateAgodaTab(tab) {
  if (!tab?.id || !tab.url) {
    throw new Error("Active tab not found.");
  }

  const url = new URL(tab.url);
  if (!url.hostname.endsWith("agoda.com")) {
    throw new Error("Open an Agoda property page first.");
  }

  if (!/\/hotel\//i.test(url.pathname)) {
    throw new Error("Open an Agoda property detail page first.");
  }
}

async function runCatalogScan(sourceTabId, config, options = {}) {
  const sourceTab = await chrome.tabs.get(sourceTabId);
  validateAgodaTab(sourceTab);
  const scanContext = createScanContext(sourceTabId, sourceTab.url);
  currentScan = scanContext;
  let workerTabs = [];

  try {
    const scenarios = buildCatalogScenarios(sourceTab.url, config);
    if (!scenarios.length) {
      throw new Error("Select at least one traffic source, card, airline, or promo option.");
    }

    const scannableCount = scenarios.filter((scenario) => scenario.mode !== "promo-page").length;
    const workerCount = Math.min(
      SCAN_CONCURRENCY,
      Math.max(scannableCount, scenarios.length ? 1 : 0)
    );
    const sourcePageResult = await tryScrapeCurrentPage(sourceTabId);

    updateScanState({
      ...createIdleState(),
      running: true,
      mode: options.openBest ? "scan-and-open" : "scan-only",
      currentIndex: 0,
      total: scenarios.length,
      startedAt: new Date().toISOString(),
      currentPageResult: serializeVisibleResult(sourcePageResult),
      diagnosticsNote: "",
      sourceTabId,
      sourceUrl: normalizeComparableUrl(sourceTab.url),
      sourceTitle: sourceTab.title || "",
      message: options.openBest
        ? `Scanning ${scenarios.length} scenarios with ${workerCount} workers before opening the best result...`
        : `Scanning ${scenarios.length} scenarios with ${workerCount} workers...`
    });

    const rawResults = [];
    let completedCount = 0;
    let appendQueue = Promise.resolve();

    const appendResult = (nextResult) => {
      appendQueue = appendQueue.then(() => {
        throwIfScanCancelled(scanContext);
        rawResults.push(nextResult);
        completedCount += 1;
        const rankedResults = rankResults(rawResults);
        updateScanState({
          currentIndex: completedCount,
          message: buildScanProgressMessage(
            completedCount,
            scenarios.length,
            workerCount,
            nextResult.option?.label || ""
          ),
          results: rankedResults.results.map(serializeResult),
          comparable: rankedResults.comparable,
          diagnosticsNote: buildDiagnosticsNote(rankedResults.results, sourcePageResult)
        });
      });

      return appendQueue;
    };

    workerTabs = scannableCount
      ? await createScanTabPool(sourceTab, Math.min(SCAN_CONCURRENCY, scannableCount), scanContext)
      : [];

    await runScenarioPool(scenarios, workerCount, async (scenario, workerIndex) => {
      throwIfScanCancelled(scanContext);
      await ensureSourceTabUnchanged(scanContext);

      if (scenario.mode === "promo-page") {
        await appendResult(createOpenOnlyResult(scenario));
        return;
      }

      const tabId = workerTabs[workerIndex]?.id;
      if (!tabId) {
        throw new Error(`Worker ${workerIndex + 1} has no scan tab assigned.`);
      }

      try {
        const { scanResult, finalUrl } = await scanScenarioInTab(
          tabId,
          scenario,
          scanContext,
          SCENARIO_TIMEOUT_MS
        );
        await appendResult({
          ...scanResult,
          option: scenario,
          scannedUrl: scenario.scannedUrl,
          finalUrl
        });
      } catch (error) {
        if (isCancelledError(error)) {
          throw error;
        }

        await appendResult(await buildFailedScenarioResult(scenario, tabId, error));
      }
    });

    await appendQueue;

    throwIfScanCancelled(scanContext);
    const rankedResults = rankResults(rawResults);
    const bestResult = findBestResult(rankedResults.results);
    let openedRank = null;
    let message = bestResult
      ? `Top result: ${bestResult.option.label}`
      : "No valid price was extracted from the selected links.";

    if (options.openBest && bestResult) {
      scanContext.ignoreSourceUrlChanges = true;
      await chrome.tabs.update(sourceTabId, {
        url: bestResult.scannedUrl,
        active: true
      });
      openedRank = 1;
      message = `Opening #1: ${bestResult.option.label}`;
    }

    updateScanState({
      running: false,
      finishedAt: new Date().toISOString(),
      openedRank,
      message,
      results: rankedResults.results.map(serializeResult),
      comparable: rankedResults.comparable,
      currentPageResult: serializeVisibleResult(sourcePageResult),
      diagnosticsNote: buildDiagnosticsNote(rankedResults.results, sourcePageResult)
    });
  } catch (error) {
    if (isCancelledError(error)) {
      const cancelledState = {
        running: false,
        finishedAt: new Date().toISOString(),
        openedRank: null,
        message: error.message || "Scan stopped."
      };

      if (scanContext.clearResultsOnCancel) {
        Object.assign(cancelledState, {
          currentIndex: 0,
          total: 0,
          results: [],
          currentPageResult: null,
          comparable: true,
          diagnosticsNote: "",
          sourceTabId: null,
          sourceUrl: "",
          sourceTitle: ""
        });
      }

      updateScanState(cancelledState);
      return;
    }

    throw error;
  } finally {
    await closeScanTabs(scanContext);
    if (currentScan?.id === scanContext.id) {
      currentScan = null;
    }
  }
}

async function runScenarioPool(scenarios, concurrency, runWorkerScenario) {
  let nextIndex = 0;

  async function worker(workerIndex) {
    while (nextIndex < scenarios.length) {
      const scenario = scenarios[nextIndex];
      nextIndex += 1;
      if (!scenario) {
        return;
      }

      await runWorkerScenario(scenario, workerIndex);
    }
  }

  const workers = [];
  for (let index = 0; index < concurrency; index += 1) {
    workers.push(worker(index));
  }

  await Promise.all(workers);
}

function buildScanProgressMessage(completedCount, total, workerCount, label) {
  const suffix = label ? ` Last finished: ${label}` : "";
  return `Scanning ${total} scenarios with ${workerCount} workers... ${completedCount}/${total}.${suffix}`;
}

async function createScanTabPool(sourceTab, count, scanContext) {
  const tabs = [];

  for (let index = 0; index < count; index += 1) {
    const tab = await chrome.tabs.create({
      url: "about:blank",
      active: false,
      windowId: sourceTab.windowId,
      index: sourceTab.index + 1 + index
    });

    scanContext.scanTabIds.add(tab.id);
    tabs.push(tab);
    await chrome.tabs.update(tab.id, { autoDiscardable: false }).catch(() => {});
  }

  return tabs;
}

async function closeScanTabs(scanContext) {
  const tabIds = Array.from(scanContext.scanTabIds);
  scanContext.scanTabIds.clear();
  await Promise.all(tabIds.map((tabId) => chrome.tabs.remove(tabId).catch(() => {})));
}

function getRemainingTimeout(deadline, fallbackMessage) {
  const remaining = deadline - Date.now();
  if (remaining <= 0) {
    throw new Error(fallbackMessage);
  }
  return remaining;
}

async function scanScenarioInTab(tabId, scenario, scanContext, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  const timeoutMessage = `Scenario timed out after ${timeoutMs}ms: ${scenario.label}`;

  await chrome.tabs.update(tabId, {
    url: scenario.scannedUrl,
    active: false
  });

  await waitForTabInteractive(
    tabId,
    Math.min(SCAN_DOM_READY_TIMEOUT_MS, getRemainingTimeout(deadline, timeoutMessage)),
    scanContext
  );
  throwIfScanCancelled(scanContext);

  const scanResult = await scrapePriceInTab(
    tabId,
    Math.min(SCAN_PRICE_WAIT_MS, getRemainingTimeout(deadline, timeoutMessage))
  );
  throwIfScanCancelled(scanContext);

  const finalTab = await chrome.tabs.get(tabId).catch(() => null);
  return {
    scanResult,
    finalUrl: finalTab?.url || scenario.scannedUrl
  };
}

async function buildFailedScenarioResult(scenario, tabId, error) {
  const finalTab = tabId ? await chrome.tabs.get(tabId).catch(() => null) : null;
  const debugDetails = error?.debugDetails || {};
  const failureMessageParts = [error.message];

  if (debugDetails.failureReason) {
    failureMessageParts.push(`[${debugDetails.failureReason}]`);
  }
  if (debugDetails.debugSummary) {
    failureMessageParts.push(debugDetails.debugSummary);
  }

  return {
    ok: false,
    error: failureMessageParts.filter(Boolean).join(" "),
    option: scenario,
    scannedUrl: scenario.scannedUrl,
    finalUrl: finalTab?.url || scenario.scannedUrl,
    priceText: debugDetails.priceText || "",
    selectorHint: debugDetails.selectorHint || "",
    pageOrigin: debugDetails.pageOrigin || "",
    pageCid: debugDetails.pageCid || "",
    pageCulture: debugDetails.pageCulture || "",
    pageCurrencyCode: debugDetails.pageCurrencyCode || "",
    pageTitle: debugDetails.pageTitle || "",
    debugSummary: debugDetails.debugSummary || "",
    failureReason: debugDetails.failureReason || ""
  };
}

function buildCatalogScenarios(baseUrl, config) {
  const selectedEntries = [
    ...pickCatalogEntries(AGODA_CATALOG.traffic, config.selectedTrafficIds),
    ...pickCatalogEntries(AGODA_CATALOG.cards, config.selectedCardIds),
    ...pickCatalogEntries(AGODA_CATALOG.airlines, config.selectedAirlineIds),
    ...pickCatalogEntries(AGODA_CATALOG.promos, config.selectedPromoIds)
  ];

  const scenarios = [];
  const seenKeys = new Set();

  for (const entry of selectedEntries) {
    const tag = entry.mode === "promo-page" ? "" : (entry.tag || AGODA_MARKET.defaultTag);
    const key = entry.mode === "promo-page" ? `promo:${entry.id}` : `${entry.cid}|${tag}`;
    if (seenKeys.has(key)) {
      continue;
    }
    seenKeys.add(key);

    scenarios.push({
      ...entry,
      tag,
      scannedUrl: buildScenarioUrl(baseUrl, entry)
    });
  }

  return sortScenariosByPriority(scenarios);
}

function sortScenariosByPriority(scenarios) {
  return [...scenarios].sort((left, right) => {
    const priorityDelta = getScenarioPriority(left) - getScenarioPriority(right);
    if (priorityDelta) {
      return priorityDelta;
    }
    return 0;
  });
}

function getScenarioPriority(scenario) {
  if (scenario.mode === "promo-page" || scenario.group === "promos") {
    return 3;
  }
  if (scenario.group === "traffic") {
    return 0;
  }
  if (scenario.group === "cards") {
    return 1;
  }
  if (scenario.group === "airlines") {
    return 2;
  }
  return 9;
}

function pickCatalogEntries(entries, selectedIds) {
  const selectedSet = new Set(selectedIds);
  return entries.filter((entry) => selectedSet.has(entry.id));
}

function buildScenarioUrl(baseUrl, entry) {
  if (entry.mode === "promo-page") {
    return isPlaceholderPromoUrl(entry.promoUrl) ? "" : entry.promoUrl;
  }

  return buildCampaignUrl(baseUrl, entry);
}

function isPlaceholderPromoUrl(value) {
  return !value || value.includes("/.../");
}

function createOpenOnlyResult(scenario) {
  const hasRealUrl = Boolean(scenario.scannedUrl);
  return {
    ok: false,
    openOnly: true,
    error: hasRealUrl
      ? "Promo landing page. Open manually from the results tab."
      : "Promo page URL placeholder. Replace it with the real Agoda promo URL first.",
    option: scenario,
    scannedUrl: scenario.scannedUrl,
    finalUrl: scenario.scannedUrl,
    priceText: scenario.description || "",
    selectorHint: "",
    pageOrigin: "",
    pageCid: "",
    pageCulture: "",
    pageCurrencyCode: "",
    pageTitle: "",
    debugSummary: scenario.promoUrl || "",
    failureReason: hasRealUrl ? "promo-page-open-only" : "promo-page-url-needed"
  };
}

function buildCampaignUrl(baseUrl, entry) {
  const url = new URL(baseUrl);
  const params = new URLSearchParams(url.search);

  url.pathname = replaceLocalePath(url.pathname, AGODA_MARKET.language);
  params.set("finalPriceView", AGODA_MARKET.finalPriceView);
  params.set("isShowMobileAppPrice", AGODA_MARKET.isShowMobileAppPrice);
  params.set("currencyCode", AGODA_MARKET.currency);
  params.set("userCountry", AGODA_MARKET.userCountry);
  params.set("cid", entry.cid);

  const tagValue = entry.tag || AGODA_MARKET.defaultTag;
  if (tagValue) {
    params.set("tag", tagValue);
  }

  url.search = params.toString();
  return url.toString();
}

function replaceLocalePath(pathname, language) {
  const segments = pathname.split("/");
  if (/^[a-z]{2}-[a-z]{2}$/i.test(segments[1] || "")) {
    segments[1] = language;
    return segments.join("/");
  }

  return `/${language}${pathname.startsWith("/") ? pathname : `/${pathname}`}`;
}

function updateScanState(patch) {
  scanState = {
    ...scanState,
    ...patch,
    updatedAt: new Date().toISOString()
  };
  chrome.storage.local.set({ [STATE_KEY]: scanState }).catch(() => {});
  chrome.runtime.sendMessage({ type: "scanState", scanState }).catch(() => {});
}

async function failScan(error) {
  updateScanState({
    running: false,
    finishedAt: new Date().toISOString(),
    openedRank: null,
    message: `Scan failed: ${error.message || "Unknown error."}`
  });
}

function rankResults(results) {
  const cloned = results.map((result) => ({
    ...result,
    option: { ...result.option }
  }));
  const successful = cloned.filter((result) => result.ok && Number.isFinite(result.amount));
  const comparableCurrencies = new Set(
    successful.map((result) => (result.currency || AGODA_MARKET.currency).toUpperCase())
  );
  const comparable = comparableCurrencies.size <= 1;

  cloned.sort((left, right) => {
    const leftOk = left.ok && Number.isFinite(left.amount);
    const rightOk = right.ok && Number.isFinite(right.amount);

    if (leftOk !== rightOk) {
      return leftOk ? -1 : 1;
    }

    if (!leftOk && !rightOk) {
      return left.option.label.localeCompare(right.option.label, "ko");
    }

    if (comparable && left.amount !== right.amount) {
      return left.amount - right.amount;
    }

    const scoreDelta = (right.confidenceScore || 0) - (left.confidenceScore || 0);
    if (scoreDelta) {
      return scoreDelta;
    }

    return left.amount - right.amount;
  });

  let rank = 1;
  cloned.forEach((result) => {
    result.rank = comparable && result.ok && Number.isFinite(result.amount) ? rank++ : null;
  });

  return {
    comparable,
    results: cloned
  };
}

function findBestResult(results) {
  return results.find((result) => result.ok && Number.isFinite(result.amount)) || null;
}

function buildDiagnosticsNote(results, currentPageResult) {
  const successful = results.filter((result) => result.ok);
  if (!successful.length) {
    return "";
  }

  const origins = new Set(successful.map((result) => result.pageOrigin).filter(Boolean));
  const cids = new Set(
    successful
      .map((result) => result.pageCid)
      .filter((value) => value !== undefined && value !== null && value !== "")
  );

  const parts = [];
  if (currentPageResult?.pageOrigin) {
    parts.push(`current origin=${currentPageResult.pageOrigin}`);
  }
  if (origins.size === 1) {
    parts.push(`tested origin=${Array.from(origins)[0]}`);
  }
  if (cids.size === 1) {
    parts.push(`tested cid=${Array.from(cids)[0]}`);
  }

  return parts.join(" | ");
}

function serializeResult(result) {
  return {
    id: result.option.id,
    label: result.option.label,
    group: result.option.group,
    groupLabel: result.option.groupLabel,
    description: result.option.description || "",
    mode: result.option.mode || "campaign",
    cid: result.option.cid || "",
    tag: result.option.mode === "promo-page" ? "" : (result.option.tag || AGODA_MARKET.defaultTag),
    rank: result.rank,
    ok: Boolean(result.ok),
    openOnly: Boolean(result.openOnly),
    error: result.error || "",
    amount: Number.isFinite(result.amount) ? result.amount : null,
    currency: result.currency || AGODA_MARKET.currency,
    priceText: result.priceText || "",
    selectorHint: result.selectorHint || "",
    confidenceScore: result.confidenceScore || 0,
    scannedUrl: result.scannedUrl,
    finalUrl: result.finalUrl || result.scannedUrl,
    pageOrigin: result.pageOrigin || "",
    pageCid: result.pageCid ?? "",
    pageCulture: result.pageCulture || "",
    pageCurrencyCode: result.pageCurrencyCode || "",
    pageTitle: result.pageTitle || "",
    debugSummary: result.debugSummary || "",
    failureReason: result.failureReason || ""
  };
}

function serializeVisibleResult(result) {
  if (!result?.ok || !Number.isFinite(result.amount)) {
    return null;
  }

  return {
    amount: result.amount,
    currency: result.currency || AGODA_MARKET.currency,
    priceText: result.priceText || "",
    pageOrigin: result.pageOrigin || "",
    pageCid: result.pageCid ?? "",
    pageCulture: result.pageCulture || "",
    pageCurrencyCode: result.pageCurrencyCode || ""
  };
}

async function tryScrapeCurrentPage(tabId) {
  try {
    return await scrapePriceInTab(tabId, SCAN_PRICE_WAIT_MS);
  } catch {
    return null;
  }
}

async function waitForTabInteractive(tabId, timeoutMs, scanContext) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;

  while (Date.now() < deadline) {
    throwIfScanCancelled(scanContext);

    const readiness = await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: () => ({
        readyState: document.readyState,
        hasBody: Boolean(document.body),
        href: location.href
      })
    }).catch((error) => {
      lastError = error;
      return null;
    });

    const state = readiness?.[0]?.result;
    if (state?.hasBody && state.readyState !== "loading") {
      return state;
    }

    await sleep(Math.min(SCAN_TAB_POLL_INTERVAL_MS, Math.max(1, deadline - Date.now())));
  }

  const suffix = lastError?.message ? ` (${lastError.message})` : "";
  throw new Error(`Timed out waiting for Agoda DOMContentLoaded.${suffix}`);
}

async function scrapePriceInTab(tabId, waitMs = SCAN_PRICE_WAIT_MS) {
  const injection = await chrome.scripting.executeScript({
    target: { tabId },
    world: "MAIN",
    func: injectedScrape,
    args: [AGODA_MARKET.currency, waitMs]
  });

  const result = injection[0]?.result;
  if (!result?.ok) {
    const error = new Error(result?.error || "Could not extract a visible price.");
    error.debugDetails = result || {};
    throw error;
  }

  return result;
}

function injectedScrape(defaultCurrency, waitMs) {
  const selectorSource = [
    '[data-element-name*="price" i]',
    '[data-element-name*="rate" i]',
    '[data-element-name*="amount" i]',
    '[data-selenium*="price" i]',
    '[data-selenium*="rate" i]',
    '[itemprop="price"]',
    '[class*="price" i]',
    '[class*="Price"]',
    '[class*="amount" i]',
    '[id*="price" i]',
    '[id*="amount" i]',
    '[aria-label*="price" i]'
  ];
  const fallbackSelectors = ["span", "div", "strong", "p"];
  const currencySymbolPattern = /[$\u20ac\u00a5\u20a9\u00a3\u0e3f]/;
  const numericPattern = /\d[\d., ]{0,15}\d|\d{2,}/g;
  const fromLabelPattern = /(\bfrom\b|starting\s*from|starts\s*from|as\s*low\s*as|\uC2DC\uC791\uAC00)/i;
  const oneNightLabelPattern = /(1\s*\uBC15|1\s*night|per\s*night|nightly|\/night)/i;
  const installmentPattern =
    /(installment|monthly|per\s*month|\/mo\b|pay\s*later|split\s*payment|payment\s*plan|financing|finance|affirm|klarna|afterpay|zip\s*pay|atome|pay\s*in\s*\d+|할부|무이자|개월|최저\s*월|월\s*결제)/i;
  const positiveCuePattern =
    /(price|rate|total|room|stay|book|pay|charge|amount|display|current|객실|숙박|요금|결제|총액|합계|지불|예약)/i;
  const totalCuePattern = /(total|included|include|tax included|총액|합계|포함|세금포함)/i;
  const perNightPattern = /(per\s*night|nightly|\/night|1박당)/i;
  const taxFeePattern = /(tax|fee|service charge|세금|수수료|봉사료)/i;
  const discountPattern = /(discount|save|coupon|off|deal|할인|쿠폰|적립)/i;
  const roomDealPattern =
    /(view\s*room|room\s*deals|see\s*available\s*rooms|\uAC1D\uC2E4\s*\uC0C1\uD488\s*\uBCF4\uAE30)/i;
  const rewardPattern =
    /(points?|cashback|reward|\uD3EC\uC778\uD2B8|\uC801\uB9BD)/i;
  const ignoredContextPattern =
    /(review|rating|score|star|photo|image|adult|child|km|mile|min|minute|hour|reviews|후기|평점|별점|사진|성인|어린이|거리|분)/i;
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const isVisible = (element) => {
    if (!(element instanceof HTMLElement)) {
      return false;
    }

    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();

    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      rect.width > 0 &&
      rect.height > 0
    );
  };

  const normalizeText = (value) => String(value || "").replace(/\s+/g, " ").trim();

  const normalizeNumericToken = (token) => {
    let normalized = token.replace(/\s+/g, "");
    const commaCount = (normalized.match(/,/g) || []).length;
    const dotCount = (normalized.match(/\./g) || []).length;

    if (commaCount && dotCount) {
      if (normalized.lastIndexOf(",") > normalized.lastIndexOf(".")) {
        normalized = normalized.replace(/\./g, "").replace(",", ".");
      } else {
        normalized = normalized.replace(/,/g, "");
      }
    } else if (commaCount > 1) {
      normalized = normalized.replace(/,/g, "");
    } else if (dotCount > 1) {
      normalized = normalized.replace(/\./g, "");
    } else if (commaCount === 1) {
      const [, decimal = ""] = normalized.split(",");
      normalized = decimal.length === 2 ? normalized.replace(",", ".") : normalized.replace(",", "");
    } else if (dotCount === 1) {
      const [, decimal = ""] = normalized.split(".");
      normalized = decimal.length === 2 ? normalized : normalized.replace(".", "");
    }

    const value = Number.parseFloat(normalized);
    return Number.isFinite(value) ? value : null;
  };

  const minimumReasonableAmount = () => {
    const currency = (defaultCurrency || "").toUpperCase();
    if (currency === "KRW") {
      return 5000;
    }
    if (currency === "JPY") {
      return 1000;
    }
    if (currency === "THB" || currency === "TWD") {
      return 100;
    }
    if (currency === "VND" || currency === "IDR") {
      return 10000;
    }
    return 10;
  };

  const parseAmountFromValue = (rawValue) => {
    const text = normalizeText(rawValue);
    if (!text) {
      return null;
    }

    const stripped = normalizeText(text.replace(/[^\d,.\s]/g, ""));
    const directValue = normalizeNumericToken(stripped);
    if (Number.isFinite(directValue)) {
      return directValue;
    }

    const numericMatch = text.match(numericPattern);
    return numericMatch?.[0] ? normalizeNumericToken(numericMatch[0]) : null;
  };

  const formatAmount = (amount) => {
    if (!Number.isFinite(amount)) {
      return "";
    }

    if (Math.round(amount) === amount) {
      return amount.toLocaleString("en-US");
    }

    return amount.toLocaleString("en-US", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2
    });
  };

  const firstMatchSnippet = (text, pattern, beforeChars = 24, afterChars = 72) => {
    const normalized = normalizeText(text);
    if (!normalized) {
      return "";
    }

    const match = normalized.match(pattern);
    if (!match) {
      return "";
    }

    const index = match.index || 0;
    return normalizeText(
      normalized.slice(
        Math.max(0, index - beforeChars),
        Math.min(normalized.length, index + match[0].length + afterChars)
      )
    );
  };

  const findReadableScope = (node) => {
    if (!(node instanceof HTMLElement)) {
      return null;
    }

    const scopes = [
      node,
      node.closest('[data-element-name="price-display"]'),
      node.closest(".PriceContainer"),
      node.closest(".ChildRoom__PriceContainer"),
      node.parentElement,
      node.parentElement?.parentElement
    ].filter(Boolean);

    for (const scope of scopes) {
      if (scope instanceof HTMLElement && isVisible(scope)) {
        return scope;
      }
    }

    let current = node.parentElement;
    while (current && current !== document.body) {
      if (isVisible(current)) {
        return current;
      }
      current = current.parentElement;
    }

    return node;
  };

  const buildGuidedText = (node, labelPattern, fallbackText, beforeChars = 24, afterChars = 72) => {
    const scope = findReadableScope(node);
    const scopeTexts = [
      scope?.innerText || scope?.textContent || "",
      node?.innerText || node?.textContent || "",
      scope?.parentElement?.innerText || scope?.parentElement?.textContent || ""
    ];

    for (const scopeText of scopeTexts) {
      const snippet = firstMatchSnippet(scopeText, labelPattern, beforeChars, afterChars);
      if (snippet) {
        return snippet;
      }
    }

    return fallbackText;
  };

  const collectAttributeCandidates = () => {
    const minimum = minimumReasonableAmount();
    const startNodes = Array.from(
      document.querySelectorAll(
        '[data-element-name="cheapest-room-price-property-nav-bar"][data-element-cheapest-room-price]'
      )
    );

    const startCandidates = startNodes
      .map((node, index) => {
        const amount = parseAmountFromValue(node.getAttribute("data-element-cheapest-room-price"));
        if (!Number.isFinite(amount) || amount < minimum) {
          return null;
        }

        const text = buildGuidedText(
          node,
          fromLabelPattern,
          `\uC2DC\uC791\uAC00 ${formatAmount(amount)}`,
          12,
          56
        );

        return {
          text,
          selectorHint: "start-price-attribute",
          amount,
          score: 200 - index,
          currency: parseCurrency(text) || defaultCurrency,
          domIndex: index,
          sourceIndex: 0
        };
      })
      .filter(Boolean);

    if (startCandidates.length) {
      return startCandidates;
    }

    const roomPriceNodes = Array.from(
      document.querySelectorAll('[data-element-name="fpc-room-price"][data-fpc-value]')
    );

    return roomPriceNodes
      .map((node, index) => {
        const amount = parseAmountFromValue(node.getAttribute("data-fpc-value"));
        if (!Number.isFinite(amount) || amount < minimum) {
          return null;
        }

        const scope = findReadableScope(node);
        const captionText = normalizeText(
          scope?.querySelector?.('[data-element-name="price-caption-message"]')?.textContent || ""
        );
        const scopeText = normalizeText(scope?.innerText || scope?.textContent || "");

        if (captionText && !oneNightLabelPattern.test(captionText)) {
          return null;
        }

        if (!captionText && !oneNightLabelPattern.test(scopeText)) {
          return null;
        }

        const text =
          buildGuidedText(
            node,
            oneNightLabelPattern,
            `${formatAmount(amount)} 1\uBC15`,
            48,
            36
          ) || `${formatAmount(amount)} 1\uBC15`;

        return {
          text,
          selectorHint: "one-night-price-attribute",
          amount,
          score: 140 - index,
          currency: parseCurrency(`${captionText} ${text}`) || defaultCurrency,
          domIndex: index,
          sourceIndex: 0
        };
      })
      .filter(Boolean);
  };

  const pickBestAmount = (text, selectorHint) => {
    const matches = Array.from(text.matchAll(numericPattern));
    if (!matches.length) {
      return null;
    }

    const minimum = minimumReasonableAmount();
    let bestToken = null;

    for (const match of matches) {
      const token = match[0].trim();
      const value = normalizeNumericToken(token);
      if (!Number.isFinite(value)) {
        continue;
      }

      const index = match.index || 0;
      const before = text.slice(Math.max(0, index - 20), index);
      const after = text.slice(index + token.length, index + token.length + 20);
      const context = `${before} ${after}`;
      const combined = `${selectorHint} ${context} ${text}`;

      if (installmentPattern.test(combined)) {
        continue;
      }
      if (/%/.test(after.slice(0, 2)) || /%$/.test(before.slice(-2))) {
        continue;
      }
      if (ignoredContextPattern.test(context)) {
        continue;
      }

      let score = 0;
      if (/[,.]/.test(token)) {
        score += 1;
      }
      if (value >= minimum) {
        score += 4;
      } else {
        score -= 8;
      }
      if (currencySymbolPattern.test(text) || /\b[A-Z]{3}\b/.test(text)) {
        score += 4;
      }
      if (positiveCuePattern.test(combined)) {
        score += 6;
      }
      if (totalCuePattern.test(combined)) {
        score += 4;
      }
      if (perNightPattern.test(combined)) {
        score -= 3;
      }
      if (taxFeePattern.test(combined) && !totalCuePattern.test(combined)) {
        score -= 4;
      }
      if (discountPattern.test(combined) && !positiveCuePattern.test(selectorHint)) {
        score -= 4;
      }

      if (!bestToken || score > bestToken.score || (score === bestToken.score && value < bestToken.value)) {
        bestToken = { value, score };
      }
    }

    if (!bestToken || bestToken.score < 3) {
      return null;
    }

    return bestToken;
  };

  const pickFromLabelAmount = (text) => {
    const minimum = minimumReasonableAmount();
    const matches = Array.from(text.matchAll(fromLabelPattern));
    let best = null;

    for (const match of matches) {
      const afterIndex = (match.index || 0) + match[0].length;
      const windows = [
        text.slice(afterIndex, afterIndex + 48),
        text.slice(Math.max(0, (match.index || 0) - 24), match.index || 0)
      ];

      for (const windowText of windows) {
        const numericMatch = windowText.match(numericPattern);
        if (!numericMatch?.length) {
          continue;
        }

        const token = numericMatch[0].trim();
        const value = normalizeNumericToken(token);
        if (!Number.isFinite(value) || value < minimum) {
          continue;
        }

        let score = 20;
        if (currencySymbolPattern.test(windowText) || /\b[A-Z]{3}\b/.test(windowText)) {
          score += 3;
        }
        if (roomDealPattern.test(text)) {
          score += 6;
        }
        if (rewardPattern.test(text) && !roomDealPattern.test(text)) {
          score -= 6;
        }

        if (!best || score > best.score || (score === best.score && value > best.value)) {
          best = { value, score };
        }
      }
    }

    return best;
  };

  const extractFirstAmountAfterLabel = (text, labelPattern) => {
    const minimum = minimumReasonableAmount();
    const matches = Array.from(text.matchAll(labelPattern));

    for (const match of matches) {
      const anchorIndex = (match.index || 0) + match[0].length;
      const afterText = text.slice(anchorIndex, anchorIndex + 72);
      const numericMatches = Array.from(afterText.matchAll(numericPattern));

      for (const numericMatch of numericMatches) {
        const token = numericMatch[0].trim();
        const value = normalizeNumericToken(token);
        if (!Number.isFinite(value) || value < minimum) {
          continue;
        }

        const index = numericMatch.index || 0;
        const before = afterText.slice(Math.max(0, index - 16), index);
        const after = afterText.slice(index + token.length, index + token.length + 16);
        const context = `${before} ${after}`;
        const combined = `${text} ${context}`;

        if (installmentPattern.test(combined)) {
          continue;
        }
        if (/%/.test(after.slice(0, 2)) || /%$/.test(before.slice(-2))) {
          continue;
        }
        if (ignoredContextPattern.test(context)) {
          continue;
        }

        return { value };
      }
    }

    return null;
  };

  const extractLastAmountBeforeLabel = (text, labelPattern) => {
    const minimum = minimumReasonableAmount();
    const matches = Array.from(text.matchAll(labelPattern));

    for (const match of matches) {
      const anchorIndex = match.index || 0;
      const beforeText = text.slice(Math.max(0, anchorIndex - 72), anchorIndex);
      const numericMatches = Array.from(beforeText.matchAll(numericPattern));

      for (let index = numericMatches.length - 1; index >= 0; index -= 1) {
        const numericMatch = numericMatches[index];
        const token = numericMatch[0].trim();
        const value = normalizeNumericToken(token);
        if (!Number.isFinite(value) || value < minimum) {
          continue;
        }

        const tokenIndex = numericMatch.index || 0;
        const before = beforeText.slice(Math.max(0, tokenIndex - 16), tokenIndex);
        const after = beforeText.slice(tokenIndex + token.length, tokenIndex + token.length + 16);
        const context = `${before} ${after}`;
        const combined = `${text} ${context}`;

        if (installmentPattern.test(combined)) {
          continue;
        }
        if (/%/.test(after.slice(0, 2)) || /%$/.test(before.slice(-2))) {
          continue;
        }
        if (ignoredContextPattern.test(context)) {
          continue;
        }

        return { value };
      }
    }

    return null;
  };

  const parseCurrency = (text) => {
    const codeMatch = text.match(/\b([A-Z]{3})\b/);
    if (codeMatch) {
      return codeMatch[1];
    }

    if (text.includes("\u20a9")) return "KRW";
    if (text.includes("\u00a5")) return "JPY";
    if (text.includes("\u0e3f")) return "THB";
    if (text.includes("$")) return defaultCurrency || "USD";
    if (text.includes("\u20ac")) return "EUR";
    if (text.includes("\u00a3")) return "GBP";

    return defaultCurrency || null;
  };

  const scoreCandidate = (text, selectorHint, amountScore) => {
    const combined = `${selectorHint} ${text}`;
    if (installmentPattern.test(combined)) {
      return -100;
    }

    let score = amountScore;
    if (positiveCuePattern.test(selectorHint)) {
      score += 5;
    }
    if (positiveCuePattern.test(text)) {
      score += 4;
    }
    if (currencySymbolPattern.test(text) || /\b[A-Z]{3}\b/.test(text)) {
      score += 4;
    }
    if (fromLabelPattern.test(combined)) {
      score += 18;
    }
    if (roomDealPattern.test(combined)) {
      score += 10;
    }
    if (rewardPattern.test(combined) && !roomDealPattern.test(combined)) {
      score -= 8;
    }
    if (totalCuePattern.test(combined)) {
      score += 4;
    }
    if (perNightPattern.test(combined)) {
      score -= 3;
    }
    if (taxFeePattern.test(combined) && !totalCuePattern.test(combined)) {
      score -= 4;
    }
    if (discountPattern.test(combined) && !positiveCuePattern.test(selectorHint)) {
      score -= 5;
    }
    if (text.length > 100) {
      score -= 2;
    }
    return score;
  };

  const collectFromLabelCandidates = () => {
    const labelNodes = Array.from(document.querySelectorAll("span, div, strong, p"))
      .filter((node) => isVisible(node))
      .filter((node) => {
        const text = normalizeText(node.innerText || node.textContent || "");
        return text && text.length <= 80 && fromLabelPattern.test(text);
      })
      .slice(0, 120);

    if (!labelNodes.length) {
      return [];
    }

    const candidateMap = new Map();

    labelNodes.forEach((node) => {
      const scopes = [
        node,
        node.nextElementSibling,
        node.parentElement,
        node.parentElement?.nextElementSibling,
        node.parentElement?.parentElement
      ].filter(Boolean);

      scopes.forEach((scope) => {
        const text = normalizeText(scope.innerText || scope.textContent || "");
        if (!text || text.length < 4 || text.length > 220) {
          return;
        }

        const selectorHint = normalizeText([
          "from-label",
          scope.getAttribute?.("data-element-name"),
          scope.getAttribute?.("data-selenium"),
          scope.className,
          scope.id,
          scope.getAttribute?.("aria-label")
        ].filter(Boolean).join(" "));

        const amountInfo = pickFromLabelAmount(text) || pickBestAmount(text, selectorHint);
        if (!amountInfo) {
          return;
        }

        let score = scoreCandidate(text, selectorHint, amountInfo.score) + 10;
        if (roomDealPattern.test(text)) {
          score += 10;
        }
        if (rewardPattern.test(text) && !roomDealPattern.test(text)) {
          score -= 8;
        }
        const key = `${text}|${selectorHint}|${amountInfo.value}`;

        candidateMap.set(key, {
          text,
          selectorHint,
          amount: amountInfo.value,
          score,
          currency: parseCurrency(text)
        });
      });
    });

    const candidates = Array.from(candidateMap.values())
      .sort((left, right) => {
        if (right.score !== left.score) {
          return right.score - left.score;
        }
        return right.amount - left.amount;
      });

    if (!candidates.length) {
      return [];
    }

    const bestScore = candidates[0].score;
    return candidates
      .filter((candidate) => candidate.score >= bestScore - 2)
      .sort((left, right) => {
        if (right.score !== left.score) {
          return right.score - left.score;
        }
        return right.amount - left.amount;
      })
      .slice(0, 8);
  };

  const collectCandidates = () => {
    const fromLabelCandidates = collectFromLabelCandidates();
    if (fromLabelCandidates.length) {
      return fromLabelCandidates;
    }

    const candidateMap = new Map();
    const primaryNodes = Array.from(document.querySelectorAll(selectorSource.join(",")));
    const nodes = primaryNodes.length
      ? primaryNodes
      : Array.from(document.querySelectorAll(fallbackSelectors.join(","))).slice(0, 1400);

    for (const node of nodes) {
      if (!isVisible(node)) {
        continue;
      }

      const text = normalizeText(node.innerText || node.textContent || "");
      if (!text || text.length < 4 || text.length > 180) {
        continue;
      }
      if (installmentPattern.test(text)) {
        continue;
      }

      const selectorHint = normalizeText([
        node.getAttribute("data-element-name"),
        node.getAttribute("data-selenium"),
        node.className,
        node.id,
        node.getAttribute("aria-label")
      ].filter(Boolean).join(" "));

      const combined = `${selectorHint} ${text}`;
      const hasPriceCue =
        positiveCuePattern.test(combined) ||
        currencySymbolPattern.test(text) ||
        /\b[A-Z]{3}\b/.test(text);

      if (!hasPriceCue) {
        continue;
      }

      const amountInfo = pickBestAmount(text, selectorHint);
      if (!amountInfo) {
        continue;
      }

      const score = scoreCandidate(text, selectorHint, amountInfo.score);
      if (score < 4) {
        continue;
      }

      const key = `${text}|${selectorHint}|${amountInfo.value}`;
      candidateMap.set(key, {
        text,
        selectorHint,
        amount: amountInfo.value,
        score,
        currency: parseCurrency(text)
      });
    }

    const candidates = Array.from(candidateMap.values());
    const strongCandidates = candidates
      .filter((candidate) => candidate.score >= 12)
      .sort((left, right) => {
        if (right.score !== left.score) {
          return right.score - left.score;
        }
        return left.amount - right.amount;
      });

    if (strongCandidates.length) {
      const bestScore = strongCandidates[0].score;
      return strongCandidates
        .filter((candidate) => candidate.score >= bestScore - 2)
        .sort((left, right) => {
          if (left.amount !== right.amount) {
            return left.amount - right.amount;
          }
          return right.score - left.score;
        })
        .slice(0, 8);
    }

    return candidates
      .sort((left, right) => {
        if (right.score !== left.score) {
          return right.score - left.score;
        }
        return left.amount - right.amount;
      })
      .slice(0, 8);
  };

  const buildAnchorTexts = (node) => {
    const entries = [];
    const seen = new Set();

    const pushEntry = (text, source) => {
      const normalized = normalizeText(text);
      if (!normalized || normalized.length < 4 || normalized.length > 220 || seen.has(normalized)) {
        return;
      }

      seen.add(normalized);
      entries.push({ text: normalized, source });
    };

    const selfText = node.innerText || node.textContent || "";
    const prevText = node.previousElementSibling?.innerText || node.previousElementSibling?.textContent || "";
    const nextText = node.nextElementSibling?.innerText || node.nextElementSibling?.textContent || "";
    const parentText = node.parentElement?.innerText || node.parentElement?.textContent || "";
    const parentNextText =
      node.parentElement?.nextElementSibling?.innerText ||
      node.parentElement?.nextElementSibling?.textContent ||
      "";

    pushEntry(selfText, "self");
    pushEntry(`${selfText} ${nextText}`, "self-next");
    pushEntry(`${prevText} ${selfText}`, "prev-self");
    pushEntry(`${prevText} ${selfText} ${nextText}`, "prev-self-next");
    pushEntry(parentText, "parent");
    pushEntry(`${parentText} ${parentNextText}`, "parent-next");

    return entries;
  };

  const collectAnchorCandidates = (labelPattern, extractor, selectorLabel) => {
    const candidateMap = new Map();
    const labelNodes = Array.from(document.querySelectorAll("span, div, strong, p, button, a, h1, h2, h3"))
      .filter((node) => isVisible(node))
      .filter((node) => {
        const text = normalizeText(node.innerText || node.textContent || "");
        return text && text.length <= 96 && labelPattern.test(text);
      })
      .slice(0, 160);

    labelNodes.forEach((node, nodeIndex) => {
      buildAnchorTexts(node).forEach(({ text, source }, sourceIndex) => {
        const amountInfo = extractor(text, labelPattern);
        if (!amountInfo) {
          return;
        }

        let score = 40;
        if (currencySymbolPattern.test(text) || /\b[A-Z]{3}\b/.test(text)) {
          score += 4;
        }
        if (roomDealPattern.test(text)) {
          score += 5;
        }
        if (totalCuePattern.test(text)) {
          score += 4;
        }
        if (text.length > 120) {
          score -= 3;
        }

        const key = `${text}|${amountInfo.value}`;
        const nextCandidate = {
          text,
          selectorHint: `${selectorLabel}:${source}`,
          amount: amountInfo.value,
          score,
          currency: parseCurrency(text),
          domIndex: nodeIndex,
          sourceIndex
        };
        const existing = candidateMap.get(key);

        if (
          !existing ||
          nextCandidate.domIndex < existing.domIndex ||
          (nextCandidate.domIndex === existing.domIndex && nextCandidate.sourceIndex < existing.sourceIndex)
        ) {
          candidateMap.set(key, nextCandidate);
        }
      });
    });

    return Array.from(candidateMap.values())
      .sort((left, right) => {
        if (left.domIndex !== right.domIndex) {
          return left.domIndex - right.domIndex;
        }
        if (left.sourceIndex !== right.sourceIndex) {
          return left.sourceIndex - right.sourceIndex;
        }
        return right.score - left.score;
      })
      .slice(0, 8);
  };

  const collectGuidedCandidates = () => {
    const attributeCandidates = collectAttributeCandidates();
    if (attributeCandidates.length) {
      return attributeCandidates;
    }

    const startCandidates = collectAnchorCandidates(
      fromLabelPattern,
      extractFirstAmountAfterLabel,
      "start-anchor"
    );
    if (startCandidates.length) {
      return startCandidates;
    }

    return collectAnchorCandidates(
      oneNightLabelPattern,
      extractLastAmountBeforeLabel,
      "one-night-anchor"
    );
  };

  const readHotelName = () => {
    const heading = document.querySelector("h1");
    return normalizeText(heading?.textContent) || null;
  };

  const readBootstrapDiagnostics = () => {
    const scriptText = Array.from(document.scripts)
      .map((script) => script.textContent || "")
      .find((text) => text.includes('currencyCode:"') && text.includes('origin:"'));

    if (!scriptText) {
      return {};
    }

    const extract = (pattern) => {
      const match = scriptText.match(pattern);
      return match ? match[1] : "";
    };

    return {
      pageOrigin: extract(/origin:"([^"]+)"/),
      pageCid: extract(/cid:([\-0-9]+)/),
      pageCulture: extract(/culture:"([^"]+)"/),
      pageCurrencyCode: extract(/currencyCode:"([^"]+)"/)
    };
  };

  const readFailureDiagnostics = () => {
    const diagnostics = readBootstrapDiagnostics();
    const roomTimeoutText = normalizeText(
      document.querySelector(".RoomGrid-searchTimeOutText")?.textContent || ""
    );
    const roomGridTitle = normalizeText(
      document.querySelector("#roomgrid-title")?.textContent || ""
    );
    const visibleText = normalizeText(document.body?.innerText || "");
    const startPriceNode = document.querySelector(
      '[data-element-name="cheapest-room-price-property-nav-bar"][data-element-cheapest-room-price]'
    );
    const oneNightNode = document.querySelector('[data-element-name="fpc-room-price"][data-fpc-value]');
    const startPriceValue = parseAmountFromValue(
      startPriceNode?.getAttribute?.("data-element-cheapest-room-price") || ""
    );
    const oneNightValue = parseAmountFromValue(oneNightNode?.getAttribute?.("data-fpc-value") || "");
    const startAnchorText =
      buildGuidedText(
        startPriceNode,
        fromLabelPattern,
        firstMatchSnippet(visibleText, fromLabelPattern, 12, 56),
        12,
        56
      ) || "";
    const oneNightAnchorText =
      buildGuidedText(
        oneNightNode,
        oneNightLabelPattern,
        firstMatchSnippet(visibleText, oneNightLabelPattern, 48, 36),
        48,
        36
      ) || "";
    const failureReason = roomTimeoutText
      ? "room-sold-out-or-unavailable"
      : Number.isFinite(startPriceValue) || Number.isFinite(oneNightValue)
        ? "price-attribute-found-but-rejected"
        : startAnchorText || oneNightAnchorText
          ? "anchor-found-but-no-price"
          : "no-price-anchor-found";
    const debugParts = [];

    if (roomGridTitle) {
      debugParts.push(`room-grid: ${roomGridTitle}`);
    }
    if (roomTimeoutText) {
      debugParts.push(`room-state: ${roomTimeoutText}`);
    }
    if (Number.isFinite(startPriceValue)) {
      debugParts.push(`start-attr: ${formatAmount(startPriceValue)}`);
    }
    if (Number.isFinite(oneNightValue)) {
      debugParts.push(`one-night-attr: ${formatAmount(oneNightValue)}`);
    }
    if (startAnchorText) {
      debugParts.push(`start-anchor: ${startAnchorText}`);
    }
    if (oneNightAnchorText) {
      debugParts.push(`one-night-anchor: ${oneNightAnchorText}`);
    }

    return {
      ...diagnostics,
      pageTitle: document.title,
      failureReason,
      debugSummary: debugParts.join(" | "),
      priceText: roomTimeoutText || startAnchorText || oneNightAnchorText || ""
    };
  };

  const waitForGuidedCandidates = () =>
    new Promise((resolve) => {
      let settled = false;
      let observer = null;
      let intervalHandle = null;
      let timeoutHandle = null;

      const cleanup = () => {
        if (observer) {
          observer.disconnect();
        }
        if (intervalHandle) {
          clearInterval(intervalHandle);
        }
        if (timeoutHandle) {
          clearTimeout(timeoutHandle);
        }
        document.removeEventListener("DOMContentLoaded", tryResolve);
      };

      const finish = (candidates) => {
        if (settled) {
          return;
        }
        settled = true;
        cleanup();
        resolve(candidates);
      };

      const tryResolve = () => {
        const candidates = collectGuidedCandidates();
        if (candidates.length) {
          finish(candidates);
        }
      };

      const root = document.documentElement || document.body;
      if (root) {
        observer = new MutationObserver(() => {
          tryResolve();
        });
        observer.observe(root, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ["data-element-cheapest-room-price", "data-fpc-value"]
        });
      }

      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", tryResolve, { once: true });
      }

      intervalHandle = setInterval(tryResolve, 100);
      timeoutHandle = setTimeout(() => finish([]), waitMs);
      tryResolve();
    });

  return (async () => {
    const candidates = await waitForGuidedCandidates();

    if (!candidates.length) {
      const failureDiagnostics = readFailureDiagnostics();
      return {
        ok: false,
        error: "Could not extract Agoda start price or one-night price.",
        ...failureDiagnostics
      };
    }

    const best = candidates[0];
    const diagnostics = readBootstrapDiagnostics();
    return {
      ok: true,
      amount: best.amount,
      currency: best.currency || defaultCurrency,
      priceText: best.text,
      selectorHint: best.selectorHint,
      confidenceScore: best.score,
      hotelName: readHotelName(),
      pageTitle: document.title,
      pageOrigin: diagnostics.pageOrigin || "",
      pageCid: diagnostics.pageCid || "",
      pageCulture: diagnostics.pageCulture || "",
      pageCurrencyCode: diagnostics.pageCurrencyCode || "",
      candidates
    };
  })();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
