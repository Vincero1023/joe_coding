const RESERVATIONS_KEY = "savedReservations";

const refreshButton = document.getElementById("refreshButton");
const saveManualButton = document.getElementById("saveManualButton");
const hotelNameInput = document.getElementById("hotelNameInput");
const reservationUrlInput = document.getElementById("reservationUrlInput");
const priceBookedInput = document.getElementById("priceBookedInput");
const currencyInput = document.getElementById("currencyInput");
const savedCount = document.getElementById("savedCount");
const monitoringText = document.getElementById("monitoringText");
const pageStatus = document.getElementById("pageStatus");
const emptyState = document.getElementById("emptyState");
const tableWrap = document.getElementById("tableWrap");
const reservationsBody = document.getElementById("reservationsBody");

let latestReservations = [];

document.addEventListener("DOMContentLoaded", init);
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes[RESERVATIONS_KEY]) {
    return;
  }

  renderReservations(changes[RESERVATIONS_KEY].newValue || []);
});

async function init() {
  bindEvents();
  await loadReservations();
}

function bindEvents() {
  refreshButton.addEventListener("click", loadReservations);
  saveManualButton.addEventListener("click", saveManualReservation);
  document.addEventListener("click", handleDocumentClick);
  window.addEventListener("focus", loadReservations);
}

async function loadReservations() {
  const response = await chrome.runtime.sendMessage({ type: "getReservations" }).catch(() => null);
  if (!response?.ok) {
    pageStatus.textContent = response?.error || "저장한 예약 목록을 불러오지 못했습니다.";
    return;
  }

  renderReservations(response.reservations || []);
}

async function saveManualReservation() {
  pageStatus.textContent = "";

  const payload = {
    hotelName: hotelNameInput.value.trim(),
    url: reservationUrlInput.value.trim(),
    priceBooked: Number(priceBookedInput.value),
    currency: currencyInput.value.trim().toUpperCase() || "KRW"
  };

  const response = await chrome.runtime.sendMessage({
    type: "saveReservationManual",
    payload
  }).catch(() => null);

  if (!response?.ok) {
    pageStatus.textContent = response?.error || "예약 직접 등록에 실패했습니다.";
    return;
  }

  hotelNameInput.value = "";
  reservationUrlInput.value = "";
  priceBookedInput.value = "";
  currencyInput.value = payload.currency || "KRW";
  renderReservations(response.reservations || []);
  pageStatus.textContent = response.updated
    ? "같은 URL 예약을 갱신했습니다."
    : "예약을 직접 등록했습니다.";
}

function renderReservations(reservations) {
  latestReservations = Array.isArray(reservations) ? reservations : [];
  savedCount.textContent = `저장 ${latestReservations.length} / 5`;
  monitoringText.textContent = latestReservations.length
    ? "자동 가격 모니터링이 활성화되어 있습니다."
    : "예약을 저장하면 24시간마다 자동 확인합니다.";

  if (!latestReservations.length) {
    emptyState.classList.remove("hidden");
    tableWrap.classList.add("hidden");
    reservationsBody.innerHTML = "";
    return;
  }

  emptyState.classList.add("hidden");
  tableWrap.classList.remove("hidden");
  reservationsBody.innerHTML = "";

  latestReservations.forEach((reservation) => {
    const row = document.createElement("tr");
    const bestPriceText = Number.isFinite(reservation.currentBestPrice)
      ? `${formatAmount(reservation.currentBestPrice)} ${reservation.currency}`
      : "-";
    const actionButtons = [
      `<button type="button" class="mini secondary" data-action="check" data-id="${escapeHtml(reservation.id)}">확인</button>`
    ];

    if (reservation.status === "lower" && reservation.currentBestUrl) {
      actionButtons.push(
        `<button type="button" class="mini secondary" data-action="open-best" data-url="${escapeHtml(reservation.currentBestUrl)}">최저가 열기</button>`
      );
    }

    actionButtons.push(
      `<button type="button" class="mini ghost" data-action="remove" data-id="${escapeHtml(reservation.id)}">삭제</button>`
    );

    row.innerHTML = `
      <td>
        <strong>${escapeHtml(reservation.hotelName || "저장한 Agoda 호텔")}</strong>
        <div class="hotel-meta mono">${escapeHtml(buildDateText(reservation))}</div>
        <div class="hotel-meta mono">${escapeHtml(reservation.url)}</div>
      </td>
      <td class="mono">
        ${escapeHtml(formatBookedPrice(reservation))}
        <div class="price-meta">${escapeHtml(`저장일 ${formatDateTime(reservation.createdAt)}`)}</div>
      </td>
      <td class="mono">
        ${escapeHtml(bestPriceText)}
        <div class="price-meta">${escapeHtml(buildBestPriceMeta(reservation))}</div>
      </td>
      <td>
        <span class="status-pill ${escapeHtml(reservation.status || "unknown")}">${escapeHtml(formatStatus(reservation.status))}</span>
        <div class="price-meta">${escapeHtml(reservation.lastMessage || "")}</div>
      </td>
      <td>
        <div class="action-row">
          ${actionButtons.join("")}
        </div>
      </td>
    `;

    reservationsBody.appendChild(row);
  });
}

async function handleDocumentClick(event) {
  const actionButton = event.target.closest("button[data-action]");
  if (!actionButton) {
    return;
  }

  const { action } = actionButton.dataset;
  if (action === "check") {
    await runCheck(actionButton.dataset.id);
    return;
  }

  if (action === "remove") {
    await removeReservation(actionButton.dataset.id);
    return;
  }

  if (action === "open-best") {
    await openBestPrice(actionButton.dataset.url);
  }
}

async function runCheck(reservationId) {
  pageStatus.textContent = "최신 Agoda 가격을 확인하는 중입니다...";
  const response = await chrome.runtime.sendMessage({
    type: "checkReservation",
    reservationId
  }).catch(() => null);

  if (!response?.ok) {
    pageStatus.textContent = response?.error || "예약 가격 확인에 실패했습니다.";
    return;
  }

  renderReservations(response.reservations || latestReservations);
  pageStatus.textContent = "예약 가격 확인이 완료되었습니다.";
}

async function removeReservation(reservationId) {
  const response = await chrome.runtime.sendMessage({
    type: "removeReservation",
    reservationId
  }).catch(() => null);

  if (!response?.ok) {
    pageStatus.textContent = response?.error || "예약 삭제에 실패했습니다.";
    return;
  }

  renderReservations(response.reservations || []);
  pageStatus.textContent = "예약을 삭제했습니다.";
}

async function openBestPrice(url) {
  if (!url) {
    return;
  }

  await chrome.tabs.create({ url, active: true });
}

function formatBookedPrice(reservation) {
  if (!Number.isFinite(reservation.priceBooked)) {
    return "-";
  }

  return `${formatAmount(reservation.priceBooked)} ${reservation.currency}`;
}

function buildBestPriceMeta(reservation) {
  const parts = [];
  if (reservation.currentBestLabel) {
    parts.push(reservation.currentBestLabel);
  }
  if (reservation.currentBestPriceType) {
    parts.push(reservation.currentBestPriceType === "mobile" ? "모바일가" : "데스크톱가");
  }
  if (reservation.lastCheckedAt) {
    parts.push(`확인 ${formatDateTime(reservation.lastCheckedAt)}`);
  }
  return parts.join(" | ");
}

function buildDateText(reservation) {
  const parts = [];
  if (reservation.checkin) {
    parts.push(`체크인 ${reservation.checkin}`);
  }
  if (reservation.checkout) {
    parts.push(`체크아웃 ${reservation.checkout}`);
  }
  return parts.join(" | ");
}

function formatStatus(status) {
  if (status === "lower") {
    return "가격 하락";
  }
  if (status === "higher") {
    return "가격 상승";
  }
  if (status === "same") {
    return "가격 동일";
  }
  if (status === "checking") {
    return "확인 중";
  }
  return "미확인";
}

function formatDateTime(value) {
  if (!value) {
    return "";
  }

  try {
    return new Intl.DateTimeFormat("ko-KR", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatAmount(amount) {
  return new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: amount % 1 === 0 ? 0 : 2
  }).format(amount);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;");
}
