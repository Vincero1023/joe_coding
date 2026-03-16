const statusPill = document.getElementById("statusPill");
const statusText = document.getElementById("statusText");
const progressText = document.getElementById("progressText");
const updatedText = document.getElementById("updatedText");
const sourceTitle = document.getElementById("sourceTitle");
const sourceUrl = document.getElementById("sourceUrl");
const diagnosticsText = document.getElementById("diagnosticsText");
const currentSection = document.getElementById("currentSection");
const currentPrice = document.getElementById("currentPrice");
const currentDetail = document.getElementById("currentDetail");
const resultsHint = document.getElementById("resultsHint");
const topEmpty = document.getElementById("topEmpty");
const topResults = document.getElementById("topResults");
const resultsEmpty = document.getElementById("resultsEmpty");
const resultsTableWrap = document.getElementById("resultsTableWrap");
const resultsBody = document.getElementById("resultsBody");
const refreshButton = document.getElementById("refreshButton");
const stopButton = document.getElementById("stopButton");
const openSourceButton = document.getElementById("openSourceButton");
const saveReservationButton = document.getElementById("saveReservationButton");
const openReservationsButton = document.getElementById("openReservationsButton");
const reservationStatus = document.getElementById("reservationStatus");

let pollTimer = null;
let latestState = null;

document.addEventListener("DOMContentLoaded", init);
chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "scanState") {
    renderScanState(message.scanState);
  }
});

async function init() {
  bindEvents();
  await loadState();
  pollTimer = window.setInterval(loadState, 1500);
}

function bindEvents() {
  refreshButton.addEventListener("click", loadState);
  stopButton.addEventListener("click", stopScan);
  openSourceButton.addEventListener("click", openSourcePage);
  saveReservationButton.addEventListener("click", saveReservation);
  openReservationsButton.addEventListener("click", openReservationsPage);
  document.addEventListener("click", handleDocumentClick);
  window.addEventListener("focus", loadState);
  window.addEventListener("beforeunload", () => {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  });
}

async function loadState() {
  const response = await chrome.runtime.sendMessage({ type: "getState" }).catch(() => null);
  if (!response?.ok) {
    setStatus("스캔 상태를 불러오지 못했습니다.", "error");
    return;
  }

  renderScanState(response.scanState);
}

async function stopScan() {
  const response = await chrome.runtime.sendMessage({ type: "stopScan" });
  if (!response.ok) {
    setStatus(response.error, "error");
    return;
  }

  renderScanState(response.scanState || latestState);
}

async function openSourcePage() {
  if (!latestState?.sourceUrl) {
    return;
  }

  await chrome.tabs.create({ url: latestState.sourceUrl, active: true });
}

async function saveReservation() {
  reservationStatus.textContent = "";
  const response = await chrome.runtime.sendMessage({ type: "saveCurrentReservation" }).catch(() => null);
  if (!response?.ok) {
    reservationStatus.textContent = response?.error || "예약 저장에 실패했습니다.";
    return;
  }

  reservationStatus.textContent = response.updated
    ? "같은 URL 예약을 갱신했습니다."
    : "현재 예약을 저장했습니다.";
}

async function openReservationsPage() {
  const response = await chrome.runtime.sendMessage({ type: "openReservationsPage", active: true }).catch(() => null);
  if (!response?.ok) {
    reservationStatus.textContent = response?.error || "예약 추적기를 열지 못했습니다.";
  }
}

function renderScanState(scanState) {
  if (!scanState) {
    return;
  }

  latestState = scanState;
  renderStatus(scanState);
  renderSource(scanState);
  renderCurrentCard(scanState.currentPageResult);
  renderTopResults(scanState.results || [], scanState.currentPageResult, scanState.openedRank);
  renderResults(scanState.results || [], scanState.currentPageResult);
  resultsHint.textContent = buildHintText(scanState.results || [], Boolean(scanState.comparable));
  diagnosticsText.textContent = scanState.diagnosticsNote ? `진단: ${scanState.diagnosticsNote}` : "";
  stopButton.disabled = !scanState.running;
  openSourceButton.disabled = !scanState.sourceUrl;
  saveReservationButton.disabled = !canSaveReservation(scanState);
}

function renderStatus(scanState) {
  let tone = "idle";
  let pillText = "대기";

  if (scanState.running) {
    tone = "running";
    pillText = "진행 중";
  } else if (/실패|오류|error|failed/i.test(scanState.message || "")) {
    tone = "error";
    pillText = "오류";
  } else if ((scanState.results || []).length) {
    tone = "done";
    pillText = "완료";
  }

  statusPill.className = `pill ${tone}`;
  statusPill.textContent = pillText;
  statusText.textContent = scanState.message || "스캔 대기 중입니다.";
  progressText.textContent = scanState.total
    ? `${Math.min(scanState.currentIndex || 0, scanState.total)} / ${scanState.total}`
    : "";
  updatedText.textContent = scanState.updatedAt ? `업데이트 ${formatDateTime(scanState.updatedAt)}` : "";
}

function renderSource(scanState) {
  sourceTitle.textContent = scanState.sourceTitle || "아직 Agoda Best 스캔이 시작되지 않았습니다.";
  sourceUrl.textContent = scanState.sourceUrl || "";
}

function renderCurrentCard(currentResult) {
  if (!currentResult || !Number.isFinite(currentResult.amount)) {
    currentSection.classList.add("hidden");
    currentPrice.textContent = "-";
    currentDetail.textContent = "";
    return;
  }

  currentSection.classList.remove("hidden");
  currentPrice.textContent = `${formatAmount(currentResult.amount)} ${currentResult.currency}`;
  currentDetail.textContent = currentResult.priceText
    ? `추출 텍스트: ${currentResult.priceText}`
    : "현재 페이지 기준가로 사용한 값입니다.";
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
    const openUrl = result.finalUrl || result.scannedUrl;
    const opened = openedRank === result.rank ? '<span class="pill error">열림</span>' : "";
    return `
      <article class="result-card">
        <div class="result-head">
          <div>
            <p class="rank-label">#${result.rank || "-"}</p>
            <h3>${escapeHtml(result.label)}</h3>
            <p class="result-meta">${escapeHtml(result.groupLabel)} | ${escapeHtml(formatPriceType(result.priceType))} | cid ${escapeHtml(result.cid)}</p>
          </div>
          ${opened}
        </div>
        <p class="result-price">${formatAmount(result.amount)} ${escapeHtml(result.currency)}</p>
        <p class="result-delta">${escapeHtml(buildDeltaText(result, currentResult))}</p>
        <p class="result-text">${result.priceText ? `추출 텍스트: ${escapeHtml(result.priceText)}` : "추출 텍스트가 없습니다."}</p>
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
    const openUrl = result.finalUrl || result.scannedUrl || "";
    const cidTag = result.mode === "promo-page"
      ? "PROMO_PAGE"
      : (result.tag ? `${result.cid} / ${result.tag}` : result.cid);
    const detailText = buildDetailText(result);
    const statusHtml = buildStatusHtml(result);
    const openButton = openUrl
      ? `<button type="button" class="mini secondary" data-open-url="${escapeHtml(openUrl)}">열기</button>`
      : '<button type="button" class="mini secondary" disabled>URL 필요</button>';

    row.innerHTML = `
      <td>${result.rank || "-"}</td>
      <td>
        <strong>${escapeHtml(result.label)}</strong>
        <div class="subtle mono">${escapeHtml(detailText)}</div>
      </td>
      <td>${escapeHtml(result.groupLabel)}</td>
      <td class="mono">${escapeHtml(formatPriceType(result.priceType))}</td>
      <td class="mono">${escapeHtml(price)}</td>
      <td>${escapeHtml(buildDeltaText(result, currentResult))}</td>
      <td class="mono">${escapeHtml(cidTag)}</td>
      <td class="${result.ok ? "status-ok" : "status-error"}">${statusHtml}</td>
      <td>${openButton}</td>
    `;

    resultsBody.appendChild(row);
  });
}

function buildStatusHtml(result) {
  let title = result.ok ? "정상" : (result.error || "실패");
  if (result.failureReason === "promo-page-open-only") {
    title = "직접 열기";
  } else if (result.failureReason === "promo-page-url-needed") {
    title = "실제 URL 필요";
  }

  const lines = [escapeHtml(title)];
  if (result.failureReason) {
    lines.push(`<div class="subtle mono">${escapeHtml(result.failureReason)}</div>`);
  }

  return lines.join("");
}

function buildDetailText(result) {
  const parts = [];

  if (result.priceType && result.variantKey) {
    parts.push(`변형 ${result.variantKey}`);
  }
  if (result.description) {
    parts.push(result.description);
  }
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

function buildDeltaText(result, current) {
  if (result?.openOnly || result?.mode === "promo-page") {
    return "비교 제외";
  }
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
    return "가격 추출에 실패했습니다. 실패 행의 디버그 텍스트를 확인하세요.";
  }
  if (!comparable) {
    return "통화가 섞여 있어 순위 비교가 완전히 정확하지 않을 수 있습니다.";
  }

  return `${successCount}개 결과에서 가격을 읽었습니다.`;
}

function canSaveReservation(scanState) {
  return Boolean(
    scanState?.sourceUrl &&
    scanState?.currentPageResult &&
    Number.isFinite(scanState.currentPageResult.amount)
  );
}

function formatAmount(amount) {
  return new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: amount % 1 === 0 ? 0 : 2
  }).format(amount);
}

function formatPriceType(priceType) {
  if (priceType === "mobile") {
    return "모바일";
  }
  if (priceType === "desktop") {
    return "데스크톱";
  }
  return "-";
}

function formatDateTime(value) {
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    }).format(new Date(value));
  } catch {
    return value || "";
  }
}

function setStatus(message, tone = "idle") {
  statusPill.className = `pill ${tone}`;
  statusText.textContent = message || "";
}

function handleDocumentClick(event) {
  const openButton = event.target.closest("button[data-open-url]");
  if (openButton) {
    openResult(openButton.dataset.openUrl);
  }
}

async function openResult(url) {
  if (!url) {
    return;
  }

  await chrome.tabs.create({ url, active: true });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;");
}
