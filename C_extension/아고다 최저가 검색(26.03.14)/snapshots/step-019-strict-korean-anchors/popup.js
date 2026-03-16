const autoRunInput = document.getElementById("autoRunInput");
const statusText = document.getElementById("statusText");
const scanSummary = document.getElementById("scanSummary");
const trafficList = document.getElementById("trafficList");
const cardList = document.getElementById("cardList");
const airlineList = document.getElementById("airlineList");
const promoList = document.getElementById("promoList");
const trafficCount = document.getElementById("trafficCount");
const cardCount = document.getElementById("cardCount");
const airlineCount = document.getElementById("airlineCount");
const promoCount = document.getElementById("promoCount");
const scanButton = document.getElementById("scanButton");
const scanAndOpenButton = document.getElementById("scanAndOpenButton");
const openResultsButton = document.getElementById("openResultsButton");
const stopButton = document.getElementById("stopButton");
const resetButton = document.getElementById("resetButton");

let loadedConfig = null;
let loadedState = null;
let hasAutoStarted = false;
let saveInFlight = false;

document.addEventListener("DOMContentLoaded", init);
chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "scanState") {
    renderScanState(message.scanState);
  }
});

async function init() {
  bindEvents();
  await loadState();
  await autoRunIfNeeded();
}

function bindEvents() {
  scanButton.addEventListener("click", () => startScan(false));
  scanAndOpenButton.addEventListener("click", () => startScan(true));
  openResultsButton.addEventListener("click", openResultsPage);
  stopButton.addEventListener("click", stopScan);
  resetButton.addEventListener("click", handleReset);
  autoRunInput.addEventListener("change", handleConfigChange);
  trafficList.addEventListener("change", handleConfigChange);
  cardList.addEventListener("change", handleConfigChange);
  airlineList.addEventListener("change", handleConfigChange);
  promoList.addEventListener("change", handleConfigChange);
  document.addEventListener("click", handleDocumentClick);
}

async function loadState() {
  const response = await chrome.runtime.sendMessage({ type: "getState" });
  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  loadedConfig = response.config;
  loadedState = response.scanState;
  renderConfig(response.config);
  renderScanState(response.scanState);
}

function renderConfig(config) {
  autoRunInput.checked = Boolean(config.autoRunOnOpen);
  renderOptionGroup(trafficList, AGODA_CATALOG.traffic, config.selectedTrafficIds, "selectedTrafficIds");
  renderOptionGroup(cardList, AGODA_CATALOG.cards, config.selectedCardIds, "selectedCardIds");
  renderOptionGroup(airlineList, AGODA_CATALOG.airlines, config.selectedAirlineIds, "selectedAirlineIds");
  renderOptionGroup(promoList, AGODA_CATALOG.promos, config.selectedPromoIds, "selectedPromoIds");
  renderSelectionCounts();
}

function renderOptionGroup(container, entries, selectedIds, configKey) {
  const selectedSet = new Set(selectedIds);
  container.innerHTML = entries.map((entry) => {
    const checked = selectedSet.has(entry.id) ? "checked" : "";
    const metaParts = [];
    if (entry.cid) {
      metaParts.push(`cid ${entry.cid}`);
    }
    if (entry.tag) {
      metaParts.push(`tag ${entry.tag}`);
    }
    if (entry.mode === "promo-page") {
      metaParts.push("열기 전용");
    }
    if (entry.description) {
      metaParts.push(entry.description);
    }

    return `
      <label class="option-chip">
        <input type="checkbox" data-config-key="${configKey}" value="${escapeHtml(entry.id)}" ${checked}>
        <span class="option-title">${escapeHtml(entry.label)}</span>
        <span class="option-meta">${escapeHtml(metaParts.join(" | "))}</span>
      </label>
    `;
  }).join("");
}

function renderSelectionCounts() {
  trafficCount.textContent = `${collectCheckedIds("selectedTrafficIds").length} selected`;
  cardCount.textContent = `${collectCheckedIds("selectedCardIds").length} selected`;
  airlineCount.textContent = `${collectCheckedIds("selectedAirlineIds").length} selected`;
  promoCount.textContent = `${collectCheckedIds("selectedPromoIds").length} selected`;
}

function collectConfig() {
  return {
    autoRunOnOpen: autoRunInput.checked,
    selectedTrafficIds: collectCheckedIds("selectedTrafficIds"),
    selectedCardIds: collectCheckedIds("selectedCardIds"),
    selectedAirlineIds: collectCheckedIds("selectedAirlineIds"),
    selectedPromoIds: collectCheckedIds("selectedPromoIds")
  };
}

function collectCheckedIds(configKey) {
  return Array.from(document.querySelectorAll(`input[data-config-key="${configKey}"]:checked`))
    .map((input) => input.value);
}

async function handleConfigChange() {
  renderSelectionCounts();
  if (saveInFlight) {
    return;
  }

  saveInFlight = true;
  const response = await chrome.runtime.sendMessage({
    type: "saveConfig",
    config: collectConfig()
  });
  saveInFlight = false;

  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  loadedConfig = response.config;
  setStatus("옵션을 저장했습니다.");
}

async function handleReset() {
  const response = await chrome.runtime.sendMessage({ type: "resetConfig" });
  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  loadedConfig = response.config;
  renderConfig(response.config);
  setStatus("기본값으로 복원했습니다.");
}

async function autoRunIfNeeded() {
  if (hasAutoStarted || !loadedConfig?.autoRunOnOpen) {
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!isAgodaPropertyTab(tab?.url)) {
    setStatus("Agoda 숙소 상세 페이지에서만 자동 실행됩니다.");
    return;
  }

  const currentUrl = normalizeComparableUrl(tab.url);
  if (loadedState?.running && loadedState.sourceUrl === currentUrl) {
    setStatus("이미 이 페이지를 스캔 중입니다. 결과 탭에서 확인하세요.");
    return;
  }

  if (
    !loadedState?.running &&
    loadedState?.sourceUrl === currentUrl &&
    ((loadedState.results || []).length || loadedState.currentPageResult)
  ) {
    setStatus("이 페이지의 최근 결과가 남아 있습니다. 필요하면 수동으로 다시 검색하세요.");
    return;
  }

  hasAutoStarted = true;
  await startScan(false, true);
}

async function startScan(openBest, autoStarted = false) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!isAgodaPropertyTab(tab?.url)) {
    setStatus("Agoda 숙소 상세 페이지를 먼저 열어주세요.", true);
    return;
  }

  const response = await chrome.runtime.sendMessage({
    type: "scanCatalog",
    config: collectConfig(),
    tabId: tab.id,
    openBest,
    showResultsPage: true,
    focusResultsPage: true
  });

  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  loadedState = response.scanState || loadedState;
  renderScanState(loadedState);
  setStatus(
    openBest
      ? "결과 탭에서 스캔을 시작했고, 완료 시 1위를 엽니다."
      : "결과 탭에서 스캔을 시작했습니다."
  );

  if (autoStarted) {
    window.close();
    return;
  }

  window.setTimeout(() => window.close(), 120);
}

async function openResultsPage() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const response = await chrome.runtime.sendMessage({
    type: "openResultsPage",
    active: true,
    openerTabId: tab?.id || null
  });

  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  window.setTimeout(() => window.close(), 60);
}

async function stopScan() {
  const response = await chrome.runtime.sendMessage({ type: "stopScan" });
  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  loadedState = response.scanState || loadedState;
  renderScanState(loadedState);
  setStatus(response.stopped ? "검색을 중지했습니다." : "진행 중인 검색이 없습니다.");
}

function renderScanState(scanState) {
  if (!scanState) {
    return;
  }

  loadedState = scanState;
  const busy = Boolean(scanState.running);
  scanButton.disabled = busy;
  scanAndOpenButton.disabled = busy;
  stopButton.disabled = !busy;
  resetButton.disabled = busy;
  setInputsDisabled(busy);
  openResultsButton.disabled = false;

  if (scanState.message) {
    setStatus(scanState.message, /failed|error|open an agoda/i.test(scanState.message));
  }

  scanSummary.textContent = buildSummaryText(scanState);
}

function setInputsDisabled(disabled) {
  document.querySelectorAll(".settings input").forEach((element) => {
    element.disabled = disabled;
  });
  document.querySelectorAll(".settings button[data-group]").forEach((element) => {
    element.disabled = disabled;
  });
}

function buildSummaryText(scanState) {
  if (scanState.running && scanState.total) {
    return `${scanState.currentIndex || 0}/${scanState.total} 진행 중 | ${scanState.sourceTitle || "기준 페이지"}`;
  }

  if ((scanState.results || []).length) {
    const successCount = scanState.results.filter((result) => result.ok && Number.isFinite(result.amount)).length;
    const openOnlyCount = scanState.results.filter((result) => result.openOnly).length;
    const base = scanState.sourceTitle || "최근 스캔";
    return `${base} | 가격 성공 ${successCount}개 | 열기 전용 ${openOnlyCount}개`;
  }

  if (scanState.sourceTitle) {
    return scanState.sourceTitle;
  }

  return "팝업은 시작과 설정용입니다. 결과 확인은 결과 탭에서 진행하세요.";
}

function handleDocumentClick(event) {
  const actionButton = event.target.closest("button[data-action][data-group]");
  if (!actionButton) {
    return;
  }

  applyGroupAction(actionButton.dataset.group, actionButton.dataset.action);
}

function applyGroupAction(group, action) {
  const configKeyMap = {
    traffic: "selectedTrafficIds",
    cards: "selectedCardIds",
    airlines: "selectedAirlineIds",
    promos: "selectedPromoIds"
  };
  const configKey = configKeyMap[group];
  if (!configKey) {
    return;
  }

  document.querySelectorAll(`input[data-config-key="${configKey}"]`).forEach((input) => {
    input.checked = action === "all";
  });
  handleConfigChange();
}

function isAgodaPropertyTab(url) {
  if (!url) {
    return false;
  }

  try {
    const parsed = new URL(url);
    return parsed.hostname.endsWith("agoda.com") && /\/hotel\//i.test(parsed.pathname);
  } catch {
    return false;
  }
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

function setStatus(message, isError = false) {
  statusText.textContent = message || "";
  statusText.classList.toggle("status-error", Boolean(isError));
  statusText.classList.toggle("status-ok", !isError && Boolean(message));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
