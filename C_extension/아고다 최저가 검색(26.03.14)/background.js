importScripts("catalog.js");

const STORAGE_KEY = "agodaFinderConfig";
const STATE_KEY = "agodaFinderState";
const RESULTS_PAGE_PATH = "results.html";
const RESERVATIONS_KEY = "savedReservations";
const RESERVATIONS_PAGE_PATH = "reservations.html";
const RESERVATION_ALARM_NAME = "reservation-price-check";
const RESERVATION_NOTIFICATION_PREFIX = "reservation-drop:";
const MAX_SAVED_RESERVATIONS = 5;
const NOTIFICATION_ICON_PATH = "icon128.png";
const SCAN_CONCURRENCY = 3;
const SCENARIO_TIMEOUT_MS = 18000;
const SCAN_PAGE_READY_TIMEOUT_MS = 10000;
const SCAN_POST_READY_DELAY_MS = 1800;
const SCAN_PRICE_WAIT_MS = 12000;
const SCAN_TAB_POLL_INTERVAL_MS = 120;

let scanState = createIdleState();
let currentScan = null;
let resultsPageTabId = null;
let reservationsPageTabId = null;
let reservationMonitorPromise = null;

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!currentScan || tabId !== currentScan.sourceTabId || currentScan.ignoreSourceUrlChanges) {
    return;
  }

  const nextUrl = changeInfo.url || tab?.url;
  if (!nextUrl) {
    return;
  }

  if (normalizeComparableUrl(nextUrl) !== currentScan.sourceUrl) {
    cancelCurrentScan("기준 페이지가 바뀌어 스캔을 중지했습니다.", { clearResults: true });
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === resultsPageTabId) {
    resultsPageTabId = null;
  }

  if (tabId === reservationsPageTabId) {
    reservationsPageTabId = null;
  }

  if (!currentScan || tabId !== currentScan.sourceTabId) {
    return;
  }

  cancelCurrentScan("기준 탭이 닫혀 스캔을 중지했습니다.", { clearResults: true });
});

chrome.runtime.onInstalled.addListener(async () => {
  await ensureDefaults();
  await syncReservationAlarm();
});

chrome.runtime.onStartup.addListener(() => {
  ensureDefaults().catch(() => {});
  syncReservationAlarm().catch(() => {});
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm?.name !== RESERVATION_ALARM_NAME) {
    return;
  }

  runReservationMonitoring().catch(() => {});
});

chrome.notifications.onClicked.addListener((notificationId) => {
  openReservationNotificationTarget(notificationId).catch(() => {});
});

chrome.notifications.onButtonClicked.addListener((notificationId, buttonIndex) => {
  if (buttonIndex !== 0) {
    return;
  }

  openReservationNotificationTarget(notificationId).catch(() => {});
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message)
    .then((response) => sendResponse({ ok: true, ...response }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));

  return true;
});

async function handleMessage(message) {
  if (!message?.type) {
    throw new Error("잘못된 메시지입니다.");
  }

  if (message.type === "getState") {
    await ensureDefaults();
    return {
      config: await getConfig(),
      scanState,
      reservations: await getSavedReservations()
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
      throw new Error("이미 다른 스캔이 진행 중입니다.");
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

  if (message.type === "openReservationsPage") {
    const tab = await ensureReservationsPageTab({
      active: Boolean(message.active ?? true),
      openerTabId: message.openerTabId || null
    });
    return {
      tabId: tab.id,
      url: tab.url
    };
  }

  if (message.type === "getReservations") {
    await ensureDefaults();
    return {
      reservations: await getSavedReservations()
    };
  }

  if (message.type === "saveCurrentReservation") {
    const saved = await saveReservationFromCurrentState();
    return saved;
  }

  if (message.type === "saveReservationManual") {
    return await saveManualReservation(message.payload || {});
  }

  if (message.type === "removeReservation") {
    if (!message.reservationId) {
      throw new Error("예약 ID가 필요합니다.");
    }

    return {
      reservations: await removeSavedReservation(message.reservationId)
    };
  }

  if (message.type === "checkReservation") {
    if (!message.reservationId) {
      throw new Error("예약 ID가 필요합니다.");
    }

    return await checkSavedReservation(message.reservationId, {
      notifyOnDrop: Boolean(message.notifyOnDrop)
    });
  }

  if (message.type === "stopScan") {
    const stopped = cancelCurrentScan("사용자가 스캔을 중지했습니다.");
    if (!stopped) {
      return { stopped: false, scanState };
    }

    return { stopped: true, scanState };
  }

  throw new Error(`지원하지 않는 메시지 타입입니다: ${message.type}`);
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

function getReservationsPageUrl() {
  return chrome.runtime.getURL(RESERVATIONS_PAGE_PATH);
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

async function ensureReservationsPageTab(options = {}) {
  const targetUrl = getReservationsPageUrl();
  const existingTab = await resolveReservationsPageTab(targetUrl);
  const shouldActivate = options.active !== false;

  if (existingTab?.id) {
    reservationsPageTabId = existingTab.id;
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
  reservationsPageTabId = createdTab.id;
  return createdTab;
}

async function resolveReservationsPageTab(targetUrl) {
  if (reservationsPageTabId) {
    const knownTab = await chrome.tabs.get(reservationsPageTabId).catch(() => null);
    if (knownTab?.id && knownTab.url === targetUrl) {
      return knownTab;
    }
    reservationsPageTabId = null;
  }

  const matchingTabs = await chrome.tabs.query({ url: targetUrl }).catch(() => []);
  const existingTab = matchingTabs[0] || null;
  if (existingTab?.id) {
    reservationsPageTabId = existingTab.id;
  }
  return existingTab;
}

function createCancelledError(message) {
  const error = new Error(message || "스캔이 중지되었습니다.");
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
  currentScan.reason = reason || currentScan.reason || "스캔이 중지되었습니다.";
  currentScan.clearResultsOnCancel = currentScan.clearResultsOnCancel || Boolean(options.clearResults);
  updateScanState({
    message: currentScan.reason || "스캔을 중지하는 중입니다..."
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

  throw createCancelledError(scanContext.reason || "스캔이 중지되었습니다.");
}

async function ensureSourceTabUnchanged(scanContext) {
  throwIfScanCancelled(scanContext);

  const sourceTab = await chrome.tabs.get(scanContext.sourceTabId).catch(() => null);
  if (!sourceTab?.id || !sourceTab.url) {
    scanContext.cancelled = true;
    scanContext.reason = scanContext.reason || "기준 탭이 닫혀 스캔을 중지했습니다.";
    scanContext.clearResultsOnCancel = true;
    throwIfScanCancelled(scanContext);
  }

  const currentUrl = normalizeComparableUrl(sourceTab.url);
  if (!scanContext.ignoreSourceUrlChanges && currentUrl !== scanContext.sourceUrl) {
    scanContext.cancelled = true;
    scanContext.reason = scanContext.reason || "기준 페이지가 바뀌어 스캔을 중지했습니다.";
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
  const stored = await chrome.storage.local.get([STORAGE_KEY, STATE_KEY, RESERVATIONS_KEY]);

  if (!stored[STORAGE_KEY]) {
    await chrome.storage.local.set({ [STORAGE_KEY]: createDefaultConfig() });
  }

  if (stored[STATE_KEY]) {
    scanState = { ...createIdleState(), ...stored[STATE_KEY] };
  }

  const reservations = sanitizeReservations(stored[RESERVATIONS_KEY] || []);
  if (!Array.isArray(stored[RESERVATIONS_KEY])) {
    await chrome.storage.local.set({ [RESERVATIONS_KEY]: reservations });
  }
}

async function getConfig() {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  return sanitizeConfig(stored[STORAGE_KEY] || createDefaultConfig());
}

async function getSavedReservations() {
  const stored = await chrome.storage.local.get(RESERVATIONS_KEY);
  return sanitizeReservations(stored[RESERVATIONS_KEY] || []);
}

async function setSavedReservations(reservations) {
  const sanitized = sanitizeReservations(reservations);
  await chrome.storage.local.set({ [RESERVATIONS_KEY]: sanitized });
  await syncReservationAlarmFromList(sanitized);
  return sanitized;
}

function sanitizeReservations(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map(sanitizeReservation)
    .filter(Boolean)
    .slice(0, MAX_SAVED_RESERVATIONS);
}

function sanitizeReservation(entry) {
  if (!entry?.id || !entry?.url) {
    return null;
  }

  return {
    id: String(entry.id),
    url: normalizeComparableUrl(entry.url),
    hotelName: String(entry.hotelName || "").trim(),
    priceBooked: Number.isFinite(Number(entry.priceBooked)) ? Number(entry.priceBooked) : null,
    currency: String(entry.currency || AGODA_MARKET.currency || "").toUpperCase(),
    checkin: String(entry.checkin || ""),
    checkout: String(entry.checkout || ""),
    createdAt: String(entry.createdAt || new Date().toISOString()),
    currentBestPrice: Number.isFinite(Number(entry.currentBestPrice)) ? Number(entry.currentBestPrice) : null,
    currentBestUrl: String(entry.currentBestUrl || ""),
    currentBestLabel: String(entry.currentBestLabel || ""),
    currentBestPriceType: String(entry.currentBestPriceType || ""),
    lastCheckedAt: String(entry.lastCheckedAt || ""),
    status: sanitizeReservationStatus(entry.status),
    lastMessage: String(entry.lastMessage || "")
  };
}

function sanitizeReservationStatus(value) {
  const allowed = new Set(["same", "higher", "lower", "unknown", "checking"]);
  return allowed.has(value) ? value : "unknown";
}

async function syncReservationAlarm() {
  const reservations = await getSavedReservations();
  await syncReservationAlarmFromList(reservations);
}

async function syncReservationAlarmFromList(reservations) {
  if ((reservations || []).length) {
    await chrome.alarms.create(RESERVATION_ALARM_NAME, {
      periodInMinutes: 24 * 60
    });
    return;
  }

  await chrome.alarms.clear(RESERVATION_ALARM_NAME);
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

function getTabAgodaUrl(tab) {
  if (tab?.url && tab.url !== "about:blank") {
    return tab.url;
  }

  return tab?.pendingUrl || tab?.url || "";
}

function validateAgodaTab(tab) {
  const candidateUrl = getTabAgodaUrl(tab);
  if (!tab?.id || !candidateUrl) {
    throw new Error("활성 탭을 찾지 못했습니다.");
  }

  const url = new URL(candidateUrl);
  if (!url.hostname.endsWith("agoda.com")) {
    throw new Error("먼저 Agoda 페이지를 열어 주세요.");
  }

  if (!/\/hotel\//i.test(url.pathname)) {
    throw new Error("Agoda 호텔 상세 페이지를 열어 주세요.");
  }
}

async function runCatalogScan(sourceTabId, config, options = {}) {
  await executeCatalogScan({
    sourceTabId,
    config,
    interactive: true,
    openBest: Boolean(options.openBest),
    onStart: async ({ sourceTab, scenarios, sourcePageResult, workerCount }) => {
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
        sourceUrl: normalizeComparableUrl(getTabAgodaUrl(sourceTab)),
        sourceTitle: sourceTab.title || "",
        message: options.openBest
          ? `${scenarios.length}개 시나리오를 ${workerCount}개 워커로 스캔 중입니다. 완료 후 최저가 링크를 엽니다...`
          : `${scenarios.length}개 시나리오를 ${workerCount}개 워커로 스캔 중입니다...`
      });
    },
    onProgress: async ({
      completedCount,
      total,
      workerCount,
      nextResult,
      rankedResults,
      sourcePageResult
    }) => {
      updateScanState({
        currentIndex: completedCount,
        message: buildScanProgressMessage(
          completedCount,
          total,
          workerCount,
          getScenarioDisplayLabel(nextResult.option)
        ),
        results: rankedResults.results.map(serializeResult),
        comparable: rankedResults.comparable,
        diagnosticsNote: buildDiagnosticsNote(rankedResults.results, sourcePageResult)
      });
    },
    onComplete: async ({ rankedResults, bestResult, sourcePageResult, scanContext }) => {
      let openedRank = null;
      let message = bestResult
        ? `최저가 결과: ${bestResult.option.label}`
        : "선택한 링크들에서 비교 가능한 가격을 찾지 못했습니다.";

      if (options.openBest && bestResult) {
        scanContext.ignoreSourceUrlChanges = true;
        await chrome.tabs.update(sourceTabId, {
          url: bestResult.scannedUrl,
          active: true
        });
        openedRank = 1;
        message = `1위 링크를 여는 중: ${bestResult.option.label}`;
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
    },
    onCancelled: async ({ error, scanContext }) => {
      const cancelledState = {
        running: false,
        finishedAt: new Date().toISOString(),
        openedRank: null,
        message: error.message || "스캔이 중지되었습니다."
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
    }
  });
}

async function executeCatalogScan(options) {
  const sourceTab = await chrome.tabs.get(options.sourceTabId);
  validateAgodaTab(sourceTab);
  const sourceUrl = getTabAgodaUrl(sourceTab);
  const scanContext = createScanContext(options.sourceTabId, sourceUrl);
  if (!options.interactive) {
    scanContext.ignoreSourceUrlChanges = true;
  }
  let workerTabs = [];

  if (options.interactive) {
    currentScan = scanContext;
  }

  try {
    const scenarios = buildCatalogScenarios(sourceUrl, options.config);
    if (!scenarios.length) {
      throw new Error("검색 경로, 카드, 항공, 프로모션 중 최소 1개는 선택해야 합니다.");
    }

    const workerCount = SCAN_CONCURRENCY;
    const sourcePageResult = await tryScrapeCurrentPage(options.sourceTabId);

    if (options.onStart) {
      await options.onStart({ sourceTab, scenarios, sourcePageResult, workerCount, scanContext });
    }

    const rawResults = [];
    let completedCount = 0;
    let appendQueue = Promise.resolve();

    const appendResult = (nextResult) => {
      appendQueue = appendQueue.then(async () => {
        throwIfScanCancelled(scanContext);
        rawResults.push(nextResult);
        completedCount += 1;
        const rankedResults = rankResults(rawResults);
        if (options.onProgress) {
          await options.onProgress({
            completedCount,
            total: scenarios.length,
            workerCount,
            nextResult,
            rankedResults,
            sourcePageResult,
            scanContext
          });
        }
      });

      return appendQueue;
    };

    workerTabs = await createScanTabPool(sourceTab, SCAN_CONCURRENCY, scanContext);

    await runScenarioPool(scenarios, workerCount, async (scenario, workerIndex) => {
      throwIfScanCancelled(scanContext);
      await ensureSourceTabUnchanged(scanContext);

      if (scenario.mode === "promo-page") {
        await appendResult(createOpenOnlyResult(scenario));
        return;
      }

      const tabId = workerTabs[workerIndex]?.id;
      if (!tabId) {
        throw new Error(`워커 ${workerIndex + 1}에 할당된 스캔 탭이 없습니다.`);
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
          finalUrl,
          priceType: scenario.priceType || "",
          variantKey: scenario.variantKey || ""
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

    if (options.onComplete) {
      await options.onComplete({
        rankedResults,
        bestResult,
        sourcePageResult,
        sourceTab,
        scanContext,
        scenarios
      });
    }

    return {
      rankedResults,
      bestResult,
      sourcePageResult,
      sourceTab,
      scanContext,
      scenarios
    };
  } catch (error) {
    if (isCancelledError(error)) {
      if (options.onCancelled) {
        await options.onCancelled({ error, scanContext });
      }
      return {
        cancelled: true,
        error,
        scanContext
      };
    }

    throw error;
  } finally {
    await closeScanTabs(scanContext);
    if (options.interactive && currentScan?.id === scanContext.id) {
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

async function saveReservationFromCurrentState() {
  await ensureDefaults();

  if (!scanState.sourceUrl) {
    throw new Error("저장할 Agoda 기준 페이지가 없습니다.");
  }

  if (!scanState.currentPageResult || !Number.isFinite(scanState.currentPageResult.amount)) {
    throw new Error("현재 페이지 기준가를 읽지 못했습니다.");
  }

  return saveReservationRecord({
    url: scanState.sourceUrl,
    hotelName: scanState.sourceTitle || deriveHotelNameFromUrl(scanState.sourceUrl),
    priceBooked: scanState.currentPageResult.amount,
    currency: scanState.currentPageResult.currency || AGODA_MARKET.currency
  });
}

async function saveManualReservation(payload) {
  await ensureDefaults();

  const normalizedUrl = normalizeComparableUrl(payload.url || "");
  validateAgodaPropertyUrl(normalizedUrl);

  const bookedPrice = Number(payload.priceBooked);
  if (!Number.isFinite(bookedPrice) || bookedPrice <= 0) {
    throw new Error("예약 가격을 숫자로 입력해 주세요.");
  }

  const currency = String(payload.currency || AGODA_MARKET.currency || "").toUpperCase();
  return saveReservationRecord({
    url: normalizedUrl,
    hotelName: String(payload.hotelName || "").trim() || deriveHotelNameFromUrl(normalizedUrl),
    priceBooked: bookedPrice,
    currency
  });
}

async function saveReservationRecord(payload) {
  const reservations = await getSavedReservations();
  const normalizedUrl = normalizeComparableUrl(payload.url || "");
  const existing = reservations.find((reservation) => reservation.url === normalizedUrl);

  if (!existing && reservations.length >= MAX_SAVED_RESERVATIONS) {
    throw new Error("예약 추적은 최대 5개까지 가능합니다.");
  }

  const dates = parseReservationDates(normalizedUrl);
  const nextReservation = sanitizeReservation({
    id: existing?.id || crypto.randomUUID(),
    url: normalizedUrl,
    hotelName: payload.hotelName || existing?.hotelName || deriveHotelNameFromUrl(normalizedUrl),
    priceBooked: payload.priceBooked,
    currency: payload.currency || existing?.currency || AGODA_MARKET.currency,
    checkin: dates.checkin || existing?.checkin || "",
    checkout: dates.checkout || existing?.checkout || "",
    createdAt: existing?.createdAt || new Date().toISOString(),
    currentBestPrice: existing?.currentBestPrice ?? null,
    currentBestUrl: existing?.currentBestUrl || "",
    currentBestLabel: existing?.currentBestLabel || "",
    currentBestPriceType: existing?.currentBestPriceType || "",
    lastCheckedAt: existing?.lastCheckedAt || "",
    status: existing?.status || "unknown",
    lastMessage: existing?.lastMessage || ""
  });

  const nextReservations = existing
    ? reservations.map((reservation) => (
      reservation.id === existing.id ? nextReservation : reservation
    ))
    : [...reservations, nextReservation];

  const savedReservations = await setSavedReservations(nextReservations);
  return {
    reservation: savedReservations.find((reservation) => reservation.id === nextReservation.id) || nextReservation,
    reservations: savedReservations,
    updated: Boolean(existing)
  };
}

async function removeSavedReservation(reservationId) {
  const reservations = await getSavedReservations();
  const nextReservations = reservations.filter((reservation) => reservation.id !== reservationId);
  return setSavedReservations(nextReservations);
}

async function checkSavedReservation(reservationId, options = {}) {
  return runReservationTask(
    () => checkSavedReservationInternal(reservationId, options),
    { skipIfBusy: false }
  );
}

async function runReservationMonitoring() {
  return runReservationTask(async () => {
    const reservations = await getSavedReservations();
    for (const reservation of reservations) {
      await checkSavedReservationInternal(reservation.id, {
        notifyOnDrop: true,
        silent: true
      }).catch(() => {});
    }
  }, { skipIfBusy: true });
}

async function runReservationTask(task, options = {}) {
  if (currentScan?.id) {
    if (options.skipIfBusy) {
      return null;
    }
    throw new Error("현재 진행 중인 실시간 스캔이 끝난 뒤 다시 시도해 주세요.");
  }

  if (reservationMonitorPromise) {
    if (options.skipIfBusy) {
      return null;
    }
    throw new Error("예약 가격 확인이 이미 진행 중입니다.");
  }

  const promise = Promise.resolve().then(task);
  reservationMonitorPromise = promise;

  try {
    return await promise;
  } finally {
    if (reservationMonitorPromise === promise) {
      reservationMonitorPromise = null;
    }
  }
}

async function checkSavedReservationInternal(reservationId, options = {}) {
  const reservations = await getSavedReservations();
  const targetReservation = reservations.find((reservation) => reservation.id === reservationId);
  if (!targetReservation) {
    throw new Error("Saved reservation not found.");
  }

  await updateSavedReservation(reservationId, {
    status: "checking",
    lastMessage: "최신 Agoda 가격을 확인하는 중입니다..."
  });

  const config = await getConfig();
  let scanRun = null;
  let updatedReservation = null;

  try {
    scanRun = await runHeadlessCatalogScan(targetReservation.url, config);
    updatedReservation = buildReservationScanUpdate(targetReservation, scanRun.bestResult);
  } catch (error) {
    updatedReservation = {
      currentBestPrice: null,
      currentBestUrl: "",
      currentBestLabel: "",
      currentBestPriceType: "",
      lastCheckedAt: new Date().toISOString(),
      status: "unknown",
      lastMessage: error.message || "예약 가격 재확인에 실패했습니다."
    };
  }

  const finalReservations = await updateSavedReservation(reservationId, updatedReservation);
  const savedReservation = finalReservations.find((reservation) => reservation.id === reservationId) || {
    ...targetReservation,
    ...updatedReservation
  };

  if (options.notifyOnDrop && savedReservation.status === "lower") {
    await notifyReservationPriceDrop(savedReservation);
  }

  return {
    reservation: savedReservation,
    reservations: finalReservations,
    bestResult: scanRun?.bestResult ? serializeResult(scanRun.bestResult) : null
  };
}

async function runHeadlessCatalogScan(sourceUrl, config) {
  const sourceTab = await chrome.tabs.create({
    url: sourceUrl,
    active: false
  });

  await chrome.tabs.update(sourceTab.id, { autoDiscardable: false }).catch(() => {});

  try {
    return await executeCatalogScan({
      sourceTabId: sourceTab.id,
      config,
      interactive: false
    });
  } finally {
    await chrome.tabs.remove(sourceTab.id).catch(() => {});
  }
}

function buildReservationScanUpdate(reservation, bestResult) {
  const now = new Date().toISOString();
  const bookedPrice = Number(reservation.priceBooked);
  const bookedCurrency = (reservation.currency || AGODA_MARKET.currency || "").toUpperCase();

  if (!bestResult || !Number.isFinite(bestResult.amount)) {
    return {
      currentBestPrice: null,
      currentBestUrl: "",
      currentBestLabel: "",
      currentBestPriceType: "",
      lastCheckedAt: now,
      status: "unknown",
      lastMessage: "비교 가능한 Agoda 가격을 찾지 못했습니다."
    };
  }

  const bestCurrency = (bestResult.currency || bookedCurrency || AGODA_MARKET.currency || "").toUpperCase();
  let status = "unknown";
  let lastMessage = `현재 최저가: ${formatCurrencyAmount(bestResult.amount, bestCurrency)}`;

  if (Number.isFinite(bookedPrice) && (!bookedCurrency || bookedCurrency === bestCurrency)) {
    if (bestResult.amount < bookedPrice) {
      status = "lower";
      lastMessage = "더 저렴한 가격이 발견되었습니다. 재예약 후 기존 예약 취소를 검토하세요.";
    } else if (bestResult.amount > bookedPrice) {
      status = "higher";
      lastMessage = "현재 최저가가 예약 가격보다 높습니다.";
    } else {
      status = "same";
      lastMessage = "현재 최저가가 예약 가격과 같습니다.";
    }
  }

  return {
    currentBestPrice: bestResult.amount,
    currentBestUrl: bestResult.finalUrl || bestResult.scannedUrl || "",
    currentBestLabel: bestResult.option?.label || "",
    currentBestPriceType: bestResult.priceType || "",
    lastCheckedAt: now,
    status,
    lastMessage
  };
}

async function updateSavedReservation(reservationId, patch) {
  const reservations = await getSavedReservations();
  const nextReservations = reservations.map((reservation) => {
    if (reservation.id !== reservationId) {
      return reservation;
    }

    return sanitizeReservation({
      ...reservation,
      ...patch
    });
  });

  return setSavedReservations(nextReservations);
}

async function notifyReservationPriceDrop(reservation) {
  const notificationId = `${RESERVATION_NOTIFICATION_PREFIX}${reservation.id}`;
  const hotelName = reservation.hotelName || "Saved Agoda reservation";
  const message = reservation.currentBestPrice
    ? `${hotelName} is now ${formatCurrencyAmount(reservation.currentBestPrice, reservation.currency)}.`
    : "예약한 호텔의 더 낮은 가격이 발견되었습니다.";

  await chrome.notifications.create(notificationId, {
    type: "basic",
    iconUrl: chrome.runtime.getURL(NOTIFICATION_ICON_PATH),
    title: "가격 하락 감지",
    message,
    priority: 2,
    buttons: [
      { title: "최저가 열기" }
    ]
  });
}

async function openReservationNotificationTarget(notificationId) {
  if (!notificationId || !notificationId.startsWith(RESERVATION_NOTIFICATION_PREFIX)) {
    return;
  }

  const reservationId = notificationId.slice(RESERVATION_NOTIFICATION_PREFIX.length);
  const reservations = await getSavedReservations();
  const reservation = reservations.find((entry) => entry.id === reservationId);
  if (!reservation?.currentBestUrl) {
    return;
  }

  await chrome.tabs.create({ url: reservation.currentBestUrl, active: true });
  await chrome.notifications.clear(notificationId).catch(() => {});
}

function parseReservationDates(url) {
  try {
    const parsed = new URL(url);
    const checkin = parsed.searchParams.get("checkIn") || "";
    let checkout = parsed.searchParams.get("checkOut") || "";
    const losValue = Number.parseInt(parsed.searchParams.get("los") || "", 10);

    if (!checkout && checkin && Number.isFinite(losValue) && losValue > 0) {
      checkout = addDaysToDate(checkin, losValue);
    }

    return { checkin, checkout };
  } catch {
    return { checkin: "", checkout: "" };
  }
}

function addDaysToDate(dateText, days) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateText || "");
  if (!match) {
    return "";
  }

  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month, day));
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  date.setUTCDate(date.getUTCDate() + days);
  const nextYear = date.getUTCFullYear();
  const nextMonth = `${date.getUTCMonth() + 1}`.padStart(2, "0");
  const nextDay = `${date.getUTCDate()}`.padStart(2, "0");
  return `${nextYear}-${nextMonth}-${nextDay}`;
}

function deriveHotelNameFromUrl(url) {
  try {
    const parsed = new URL(url);
    const lastSegment = parsed.pathname.split("/").filter(Boolean).pop() || "Agoda 호텔";
    return lastSegment.replace(/[-_]+/g, " ").replace(/\.html?$/i, "").trim();
  } catch {
    return "Agoda 호텔";
  }
}

function validateAgodaPropertyUrl(url) {
  if (!url) {
    throw new Error("Agoda 호텔 URL을 입력해 주세요.");
  }

  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error("URL 형식이 올바르지 않습니다.");
  }

  if (!parsed.hostname.endsWith("agoda.com") || !/\/hotel\//i.test(parsed.pathname)) {
    throw new Error("Agoda 호텔 상세 페이지 URL만 등록할 수 있습니다.");
  }
}

function formatCurrencyAmount(amount, currency) {
  if (!Number.isFinite(amount)) {
    return "-";
  }

  return `${new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: amount % 1 === 0 ? 0 : 2
  }).format(amount)} ${currency || AGODA_MARKET.currency}`;
}

function buildScanProgressMessage(completedCount, total, workerCount, label) {
  const suffix = label ? ` Last finished: ${label}` : "";
  return `${total}개 시나리오를 ${workerCount}개 워커로 스캔 중... ${completedCount}/${total}.${suffix}`;
}

function getScenarioDisplayLabel(scenario) {
  if (!scenario) {
    return "";
  }

  if (!scenario.priceType) {
    return scenario.label || "";
  }

  return `${scenario.label || ""} [${scenario.priceType}]`;
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
  const timeoutMessage = `${scenario.label} 시나리오가 ${timeoutMs}ms 안에 끝나지 않았습니다.`;

  await navigateScanTab(
    tabId,
    scenario.scannedUrl,
    Math.min(SCAN_PAGE_READY_TIMEOUT_MS, getRemainingTimeout(deadline, timeoutMessage)),
    scanContext
  );
  throwIfScanCancelled(scanContext);

  await sleepWithCancellation(
    Math.min(SCAN_POST_READY_DELAY_MS, getRemainingTimeout(deadline, timeoutMessage)),
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
    priceType: scenario.priceType || "",
    variantKey: scenario.variantKey || "",
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
  let entryOrder = 0;

  for (const entry of selectedEntries) {
    const tag = entry.mode === "promo-page" ? "" : (entry.tag || AGODA_MARKET.defaultTag);
    if (entry.mode === "promo-page") {
      const key = `promo:${entry.id}`;
      if (seenKeys.has(key)) {
        continue;
      }
      seenKeys.add(key);

      scenarios.push({
        ...entry,
        tag,
        entryOrder: entryOrder++,
        variantOrder: 9,
        priceType: "",
        variantKey: entry.id,
        scannedUrl: buildScenarioUrl(baseUrl, entry)
      });
      continue;
    }

    const variants = buildCampaignScenarioVariants(baseUrl, entry, tag, entryOrder++);
    for (const scenario of variants) {
      const key = `${scenario.cid}|${scenario.tag}|${scenario.priceType}`;
      if (seenKeys.has(key)) {
        continue;
      }
      seenKeys.add(key);
      scenarios.push(scenario);
    }
  }

  return sortScenariosByPriority(scenarios);
}

function buildCampaignScenarioVariants(baseUrl, entry, tag, entryOrder) {
  return [
    { priceType: "desktop", variantOrder: 0 },
    { priceType: "mobile", variantOrder: 1 }
  ].map((variant) => ({
    ...entry,
    tag,
    entryOrder,
    variantOrder: variant.variantOrder,
    priceType: variant.priceType,
    variantKey: `${entry.id}:${variant.priceType}`,
    scannedUrl: buildScenarioUrl(baseUrl, {
      ...entry,
      tag,
      priceType: variant.priceType
    })
  }));
}

function sortScenariosByPriority(scenarios) {
  return [...scenarios].sort((left, right) => {
    const priorityDelta = getScenarioPriority(left) - getScenarioPriority(right);
    if (priorityDelta) {
      return priorityDelta;
    }

    const entryOrderDelta = (left.entryOrder || 0) - (right.entryOrder || 0);
    if (entryOrderDelta) {
      return entryOrderDelta;
    }

    const variantOrderDelta = (left.variantOrder || 0) - (right.variantOrder || 0);
    if (variantOrderDelta) {
      return variantOrderDelta;
    }

    return 0;
  });
}

function getScenarioPriority(scenario) {
  if (scenario.mode === "promo-page" || scenario.group === "promos") {
    return 9;
  }
  if (scenario.priority === "high") {
    return 0;
  }
  return 1;
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
      ? "프로모션 랜딩 페이지입니다. 결과 탭에서 직접 여세요."
      : "프로모션 URL이 임시값입니다. 실제 Agoda 프로모션 URL로 바꿔 주세요.",
    option: scenario,
    scannedUrl: scenario.scannedUrl,
    finalUrl: scenario.scannedUrl,
    priceType: scenario.priceType || "",
    variantKey: scenario.variantKey || scenario.id,
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
  params.set(
    "isShowMobileAppPrice",
    entry.priceType === "mobile" ? "true" : AGODA_MARKET.isShowMobileAppPrice
  );
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
    message: `스캔 실패: ${error.message || "알 수 없는 오류"}`
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
    priority: result.option.priority || result.priority || "normal",
    description: result.option.description || "",
    mode: result.option.mode || "campaign",
    cid: result.option.cid || "",
    tag: result.option.mode === "promo-page" ? "" : (result.option.tag || AGODA_MARKET.defaultTag),
    priceType: result.priceType || result.option.priceType || "",
    variantKey: result.variantKey || result.option.variantKey || "",
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

async function navigateScanTab(tabId, targetUrl, timeoutMs, scanContext) {
  const targetComparableUrl = normalizeComparableUrl(targetUrl);

  await new Promise((resolve, reject) => {
    let settled = false;
    let sawNavigation = false;
    let lastError = null;

    const cleanup = () => {
      clearTimeout(timeoutHandle);
      clearInterval(cancelHandle);
      clearInterval(pollHandle);
      chrome.tabs.onUpdated.removeListener(listener);
    };

    const fail = (error) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      reject(error);
    };

    const succeed = (tab) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      resolve(tab);
    };

    const refresh = async () => {
      try {
        throwIfScanCancelled(scanContext);
        const latestTab = await chrome.tabs.get(tabId).catch((error) => {
          lastError = error;
          return null;
        });

        if (!latestTab?.id) {
          fail(new Error("Agoda 페이지 로딩이 끝나기 전에 스캔 탭이 닫혔습니다."));
          return;
        }

        const latestUrl = normalizeComparableUrl(latestTab.url || "");
        const pendingUrl = normalizeComparableUrl(latestTab.pendingUrl || "");

        if (
          latestTab.status === "loading" ||
          Boolean(latestTab.pendingUrl) ||
          latestUrl === targetComparableUrl ||
          pendingUrl === targetComparableUrl
        ) {
          sawNavigation = true;
        }

        if (!sawNavigation) {
          return;
        }
        if (latestTab.status === "complete" && latestUrl && latestUrl !== "about:blank") {
          succeed(latestTab);
          return;
        }

        if (!latestUrl || latestUrl === "about:blank") {
          return;
        }

        const readiness = await chrome.scripting.executeScript({
          target: { tabId },
          world: "MAIN",
          func: () => ({
            href: location.href,
            readyState: document.readyState,
            hasBody: Boolean(document.body)
          })
        }).catch((error) => {
          lastError = error;
          return null;
        });

        const pageState = readiness?.[0]?.result;
        if (
          pageState?.hasBody &&
          pageState.readyState !== "loading" &&
          pageState.href &&
          pageState.href !== "about:blank"
        ) {
          succeed(latestTab);
        }
      } catch (error) {
        fail(error);
      }
    };

    const listener = (updatedTabId, info, tab) => {
      if (updatedTabId !== tabId) {
        return;
      }

      if (info.status === "loading" || info.url || tab?.pendingUrl) {
        sawNavigation = true;
      }

      refresh();
    };

    const timeoutHandle = setTimeout(() => {
      const suffix = lastError?.message ? ` (${lastError.message})` : "";
      fail(new Error(`Agoda 페이지 로딩 대기 시간이 초과되었습니다.${suffix}`));
    }, timeoutMs);

    const cancelHandle = setInterval(() => {
      if (scanContext?.cancelled) {
        fail(createCancelledError(scanContext.reason || "스캔이 중지되었습니다."));
      }
    }, 200);

    const pollHandle = setInterval(() => {
      refresh();
    }, SCAN_TAB_POLL_INTERVAL_MS);

    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.update(tabId, {
      url: targetUrl,
      active: false
    })
      .then((updatedTab) => {
        if (
          updatedTab?.status === "loading" ||
          Boolean(updatedTab?.pendingUrl) ||
          normalizeComparableUrl(updatedTab?.url || "") === targetComparableUrl
        ) {
          sawNavigation = true;
        }

        refresh();
      })
      .catch((error) => {
        fail(error);
      });
  });
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
    const error = new Error(result?.error || "보이는 가격을 추출하지 못했습니다.");
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
  const currencyCodePattern = /\b(KRW|USD|JPY|EUR|GBP|THB|TWD|VND|IDR|CNY|HKD|SGD|MYR|PHP|INR|AUD|CAD|CHF)\b/i;
  const numericPattern = /\d[\d., ]{0,15}\d|\d{2,}/g;
  const fromLabelPattern = /\uC2DC\uC791\uAC00/i;
  const oneNightLabelPattern = /1\s*\uBC15/i;
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
  const transportContextPattern =
    /([A-Z]{3}\s*-\s*[A-Z]{3}|flight|airport|airfare|fare|passenger|departure|arrival|\uD0D1\uC2B9\uAC1D|\uD3C9\uADE0\s*\uC694\uAE08|\uC9C0\uAE08\s*\uAC80\uC0C9\uD558\uAE30|\uC219\uC18C\uAE4C\uC9C0\s*\uC774\uB3D9|\uD56D\uACF5|\uD56D\uACF5\uAD8C)/i;
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

  const hasKnownCurrencyCode = (text) => currencyCodePattern.test(String(text || "").toUpperCase());

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

  const getAllMatches = (text, pattern) => {
    if (!text || !(pattern instanceof RegExp)) {
      return [];
    }

    const flags = pattern.flags.includes("g") ? pattern.flags : `${pattern.flags}g`;
    return Array.from(String(text).matchAll(new RegExp(pattern.source, flags)));
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
      if (transportContextPattern.test(combined)) {
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
      if (currencySymbolPattern.test(text) || hasKnownCurrencyCode(text)) {
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
    const matches = getAllMatches(text, fromLabelPattern);
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
        if (currencySymbolPattern.test(windowText) || hasKnownCurrencyCode(windowText)) {
          score += 3;
        }
        if (roomDealPattern.test(text)) {
          score += 6;
        }
        if (rewardPattern.test(text) && !roomDealPattern.test(text)) {
          score -= 6;
        }

        if (!best || score > best.score || (score === best.score && value < best.value)) {
          best = { value, score };
        }
      }
    }

    return best;
  };

  const extractFirstAmountAfterLabel = (text, labelPattern) => {
    const minimum = minimumReasonableAmount();
    const matches = getAllMatches(text, labelPattern);

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
        if (transportContextPattern.test(combined)) {
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
    const matches = getAllMatches(text, labelPattern);

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
        if (transportContextPattern.test(combined)) {
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
    const normalizedText = String(text || "").toUpperCase();
    const codeMatch = normalizedText.match(currencyCodePattern);
    if (codeMatch) {
      return codeMatch[1].toUpperCase();
    }

    if (normalizedText.includes("\u20A9")) return "KRW";
    if (normalizedText.includes("\u00A5")) return "JPY";
    if (normalizedText.includes("\u0E3F")) return "THB";
    if (normalizedText.includes("$")) return defaultCurrency || "USD";
    if (normalizedText.includes("\u20AC")) return "EUR";
    if (normalizedText.includes("\u00A3")) return "GBP";

    return defaultCurrency || null;
  };

  const scoreCandidate = (text, selectorHint, amountScore) => {
    const combined = `${selectorHint} ${text}`;
    if (installmentPattern.test(combined)) {
      return -100;
    }
    if (transportContextPattern.test(combined)) {
      return -100;
    }

    let score = amountScore;
    if (positiveCuePattern.test(selectorHint)) {
      score += 5;
    }
    if (positiveCuePattern.test(text)) {
      score += 4;
    }
    if (currencySymbolPattern.test(text) || hasKnownCurrencyCode(text)) {
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
        if (transportContextPattern.test(text)) {
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
        return left.amount - right.amount;
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
        return left.amount - right.amount;
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
      if (transportContextPattern.test(text)) {
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
        hasKnownCurrencyCode(text);

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
        if (transportContextPattern.test(text)) {
          return;
        }
        const amountInfo = extractor(text, labelPattern);
        if (!amountInfo) {
          return;
        }

        let score = 40;
        if (currencySymbolPattern.test(text) || hasKnownCurrencyCode(text)) {
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

  const collectScopedGuidedCandidates = () => {
    const visibleText = normalizeText(document.body?.innerText || "");
    const candidateMap = new Map();
    const sources = [
      {
        node: document.querySelector(
          '[data-element-name="cheapest-room-price-property-nav-bar"][data-element-cheapest-room-price]'
        ),
        labelPattern: fromLabelPattern,
        extractor: extractFirstAmountAfterLabel,
        selectorLabel: "start-guided-scope",
        beforeChars: 12,
        afterChars: 56,
        baseScore: 80
      },
      {
        node: document.querySelector('[data-element-name="fpc-room-price"][data-fpc-value]'),
        labelPattern: oneNightLabelPattern,
        extractor: extractLastAmountBeforeLabel,
        selectorLabel: "one-night-guided-scope",
        beforeChars: 48,
        afterChars: 36,
        baseScore: 70
      }
    ];

    sources.forEach((source, index) => {
      const snippets = [
        source.node
          ? buildGuidedText(
            source.node,
            source.labelPattern,
            "",
            source.beforeChars,
            source.afterChars
          )
          : "",
        firstMatchSnippet(visibleText, source.labelPattern, source.beforeChars, source.afterChars)
      ]
        .map((text) => normalizeText(text))
        .filter(Boolean);

      snippets.forEach((text, snippetIndex) => {
        const amountInfo = source.extractor(text, source.labelPattern);
        if (!amountInfo) {
          return;
        }

        const key = `${source.selectorLabel}|${text}|${amountInfo.value}`;
        if (candidateMap.has(key)) {
          return;
        }

        candidateMap.set(key, {
          text,
          selectorHint: `${source.selectorLabel}:${snippetIndex === 0 ? "scope" : "page"}`,
          amount: amountInfo.value,
          score: source.baseScore - index,
          currency: parseCurrency(text) || defaultCurrency,
          domIndex: index,
          sourceIndex: snippetIndex
        });
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

    const scopedGuidedCandidates = collectScopedGuidedCandidates();
    if (scopedGuidedCandidates.length) {
      return scopedGuidedCandidates;
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
        error: "Agoda 시작가 또는 1박 가격을 추출하지 못했습니다.",
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
