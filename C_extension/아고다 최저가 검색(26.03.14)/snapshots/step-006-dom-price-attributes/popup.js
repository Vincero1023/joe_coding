const autoRunInput = document.getElementById("autoRunInput");
const statusText = document.getElementById("statusText");
const diagnosticsText = document.getElementById("diagnosticsText");
const currentCard = document.getElementById("currentCard");
const currentPrice = document.getElementById("currentPrice");
const currentDetail = document.getElementById("currentDetail");
const topEmpty = document.getElementById("topEmpty");
const topResults = document.getElementById("topResults");
const resultsHint = document.getElementById("resultsHint");
const resultsBody = document.getElementById("resultsBody");
const resultsEmpty = document.getElementById("resultsEmpty");
const resultsTableWrap = document.getElementById("resultsTableWrap");
const trafficList = document.getElementById("trafficList");
const cardList = document.getElementById("cardList");
const airlineList = document.getElementById("airlineList");
const trafficCount = document.getElementById("trafficCount");
const cardCount = document.getElementById("cardCount");
const airlineCount = document.getElementById("airlineCount");
const scanButton = document.getElementById("scanButton");
const scanAndOpenButton = document.getElementById("scanAndOpenButton");
const stopButton = document.getElementById("stopButton");
const resetButton = document.getElementById("resetButton");

let loadedConfig = null;
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
  stopButton.addEventListener("click", stopScan);
  resetButton.addEventListener("click", handleReset);
  autoRunInput.addEventListener("change", handleConfigChange);
  trafficList.addEventListener("change", handleConfigChange);
  cardList.addEventListener("change", handleConfigChange);
  airlineList.addEventListener("change", handleConfigChange);
  document.addEventListener("click", handleDocumentClick);
}

async function loadState() {
  const response = await chrome.runtime.sendMessage({ type: "getState" });
  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  loadedConfig = response.config;
  renderConfig(response.config);
  renderScanState(response.scanState);
}

function renderConfig(config) {
  autoRunInput.checked = Boolean(config.autoRunOnOpen);
  renderOptionGroup(trafficList, AGODA_CATALOG.traffic, config.selectedTrafficIds, "selectedTrafficIds");
  renderOptionGroup(cardList, AGODA_CATALOG.cards, config.selectedCardIds, "selectedCardIds");
  renderOptionGroup(airlineList, AGODA_CATALOG.airlines, config.selectedAirlineIds, "selectedAirlineIds");
  renderSelectionCounts();
}

function renderOptionGroup(container, entries, selectedIds, configKey) {
  const selectedSet = new Set(selectedIds);
  container.innerHTML = entries.map((entry) => {
    const checked = selectedSet.has(entry.id) ? "checked" : "";
    const tagText = entry.tag ? ` | tag ${entry.tag}` : "";
    return `
      <label class="option-chip">
        <input type="checkbox" data-config-key="${configKey}" value="${escapeHtml(entry.id)}" ${checked}>
        <span class="option-title">${escapeHtml(entry.label)}</span>
        <span class="option-meta">cid ${escapeHtml(entry.cid)}${escapeHtml(tagText)}</span>
      </label>
    `;
  }).join("");
}

function collectConfig() {
  return {
    autoRunOnOpen: autoRunInput.checked,
    selectedTrafficIds: collectCheckedIds("selectedTrafficIds"),
    selectedCardIds: collectCheckedIds("selectedCardIds"),
    selectedAirlineIds: collectCheckedIds("selectedAirlineIds")
  };
}

function collectCheckedIds(configKey) {
  return Array.from(document.querySelectorAll(`input[data-config-key="${configKey}"]:checked`))
    .map((input) => input.value);
}

function renderSelectionCounts() {
  trafficCount.textContent = `${collectCheckedIds("selectedTrafficIds").length} selected`;
  cardCount.textContent = `${collectCheckedIds("selectedCardIds").length} selected`;
  airlineCount.textContent = `${collectCheckedIds("selectedAirlineIds").length} selected`;
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
    setStatus("Agoda 숙소 상세 페이지에서만 자동 검색이 실행됩니다.");
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
    openBest
  });

  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  if (autoStarted) {
    setStatus("자동 검색을 시작했습니다.");
    return;
  }

  setStatus(openBest ? "검색 후 1위를 엽니다." : "검색을 시작했습니다.");
}

async function stopScan() {
  const response = await chrome.runtime.sendMessage({ type: "stopScan" });
  if (!response.ok) {
    setStatus(response.error, true);
    return;
  }

  if (!response.stopped) {
    setStatus("진행 중인 검색이 없습니다.");
    return;
  }

  if (response.scanState) {
    renderScanState(response.scanState);
  }
}

function renderScanState(scanState) {
  if (!scanState) {
    return;
  }

  const busy = Boolean(scanState.running);
  scanButton.disabled = busy;
  scanAndOpenButton.disabled = busy;
  stopButton.disabled = !busy;
  resetButton.disabled = busy;
  setInputsDisabled(busy);

  if (scanState.message) {
    setStatus(scanState.message, /failed|error|open an agoda/i.test(scanState.message));
  }

  renderCurrentCard(scanState.currentPageResult);
  renderTopResults(scanState.results || [], scanState.currentPageResult, scanState.openedRank);
  renderResults(scanState.results || [], scanState.currentPageResult);
  diagnosticsText.textContent = scanState.diagnosticsNote ? `진단: ${scanState.diagnosticsNote}` : "";
  resultsHint.textContent = buildHintText(scanState.results || [], Boolean(scanState.comparable));
}

function setInputsDisabled(disabled) {
  document.querySelectorAll(".settings input, .settings button").forEach((element) => {
    element.disabled = disabled;
  });
  resetButton.disabled = disabled;
}

function renderCurrentCard(currentResult) {
  if (!currentResult || !Number.isFinite(currentResult.amount)) {
    currentCard.classList.add("hidden");
    return;
  }

  currentCard.classList.remove("hidden");
  currentPrice.textContent = `${formatAmount(currentResult.amount)} ${currentResult.currency}`;
  currentDetail.textContent = currentResult.priceText
    ? `추출 텍스트: ${currentResult.priceText}`
    : "현재 페이지 기준가를 찾았습니다.";
}

function renderTopResults(results, currentResult, openedRank) {
  const topThree = results
    .filter((result) => result.ok && Number.isFinite(result.amount))
    .slice(0, 3);

  if (!topThree.length) {
    topResults.innerHTML = "";
    topEmpty.classList.remove("hidden");
    return;
  }

  topEmpty.classList.add("hidden");
  topResults.innerHTML = topThree.map((result) => {
    const deltaText = buildDeltaText(result, currentResult);
    const openedText = openedRank === result.rank ? '<span class="pill opened">현재 열림</span>' : "";
    const openUrl = result.finalUrl || result.scannedUrl;
    return `
      <article class="result-card">
        <div class="result-head">
          <div>
            <p class="rank-label">#${result.rank || "-"}</p>
            <h3>${escapeHtml(result.label)}</h3>
            <p class="result-meta">${escapeHtml(result.groupLabel)} | cid ${escapeHtml(result.cid)}</p>
          </div>
          ${openedText}
        </div>
        <p class="result-price">${formatAmount(result.amount)} ${escapeHtml(result.currency)}</p>
        <p class="result-delta">${escapeHtml(deltaText)}</p>
        <p class="result-text">${result.priceText ? `추출 텍스트: ${escapeHtml(result.priceText)}` : "추출 텍스트 없음"}</p>
        <div class="result-actions">
          <button type="button" class="secondary" data-open-url="${escapeHtml(openUrl)}">열기</button>
        </div>
      </article>
    `;
  }).join("");
}

function renderResults(results, currentResult) {
  resultsBody.innerHTML = "";

  if (!results.length) {
    resultsEmpty.classList.remove("hidden");
    resultsTableWrap.classList.add("hidden");
    return;
  }

  resultsEmpty.classList.add("hidden");
  resultsTableWrap.classList.remove("hidden");

  results.forEach((result) => {
    const row = document.createElement("tr");
    if (result.rank === 1) {
      row.classList.add("best-row");
    }

    const price = Number.isFinite(result.amount)
      ? `${formatAmount(result.amount)} ${result.currency}`
      : "-";
    const deltaText = buildDeltaText(result, currentResult);
    const cidTag = result.tag ? `${result.cid} / ${result.tag}` : result.cid;
    const statusHtml = buildStatusHtml(result);
    const detailText = buildDetailText(result);
    const openUrl = result.finalUrl || result.scannedUrl;

    row.innerHTML = `
      <td>${result.rank || "-"}</td>
      <td>
        <strong>${escapeHtml(result.label)}</strong>
        <div class="subtle mono">${escapeHtml(detailText)}</div>
      </td>
      <td>${escapeHtml(result.groupLabel)}</td>
      <td class="mono">${escapeHtml(price)}</td>
      <td>${escapeHtml(deltaText)}</td>
      <td class="mono">${escapeHtml(cidTag)}</td>
      <td class="${result.ok ? "status-ok" : "status-error"}">${statusHtml}</td>
      <td><button type="button" class="mini secondary" data-open-url="${escapeHtml(openUrl)}">열기</button></td>
    `;

    resultsBody.appendChild(row);
  });
}

function buildDetailText(result) {
  const parts = [];

  if (result.priceText) {
    parts.push(result.priceText);
  } else if (result.debugSummary) {
    parts.push(result.debugSummary);
  }

  if (!result.ok && result.pageTitle) {
    parts.push(`title=${result.pageTitle}`);
  }

  return parts.join(" | ");
}

function buildStatusHtml(result) {
  const lines = [escapeHtml(result.ok ? "OK" : (result.error || "실패"))];

  if (result.failureReason) {
    lines.push(`<div class="subtle mono">${escapeHtml(result.failureReason)}</div>`);
  }

  return lines.join("");
}

function setStatus(message, isError = false) {
  statusText.textContent = message || "";
  statusText.classList.toggle("status-error", Boolean(isError));
  statusText.classList.toggle("status-ok", !isError && Boolean(message));
}

function formatAmount(amount) {
  return new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: amount % 1 === 0 ? 0 : 2
  }).format(amount);
}

function buildDeltaText(result, current) {
  if (!result?.ok || !current || !Number.isFinite(current.amount) || !Number.isFinite(result.amount)) {
    return "비교 불가";
  }

  const resultCurrency = result.currency || "";
  const currentCurrency = current.currency || "";
  if (!resultCurrency || resultCurrency !== currentCurrency) {
    return "통화 다름";
  }

  const delta = current.amount - result.amount;
  if (delta > 0) {
    return `${formatAmount(delta)} ${resultCurrency} 저렴`;
  }
  if (delta === 0) {
    return "현재와 동일";
  }
  return `${formatAmount(Math.abs(delta))} ${resultCurrency} 비쌈`;
}

function buildHintText(results, comparable) {
  if (!results.length) {
    return "";
  }

  const successCount = results.filter((result) => result.ok && Number.isFinite(result.amount)).length;
  if (!successCount) {
    return "가격 추출 실패. 실패 행의 디버그 텍스트를 확인하세요.";
  }

  if (!comparable) {
    return "통화가 섞여 있어 순위를 정확히 비교할 수 없습니다.";
  }

  return `${successCount}개 링크에서 가격을 찾았습니다.`;
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

function handleDocumentClick(event) {
  const actionButton = event.target.closest("button[data-action][data-group]");
  if (actionButton) {
    applyGroupAction(actionButton.dataset.group, actionButton.dataset.action);
    return;
  }

  const openButton = event.target.closest("button[data-open-url]");
  if (openButton) {
    openResult(openButton.dataset.openUrl);
  }
}

function applyGroupAction(group, action) {
  const configKeyMap = {
    traffic: "selectedTrafficIds",
    cards: "selectedCardIds",
    airlines: "selectedAirlineIds"
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

async function openResult(url) {
  if (!url) {
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    setStatus("현재 탭을 찾지 못했습니다.", true);
    return;
  }

  await chrome.tabs.update(tab.id, { url, active: true });
  window.close();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
