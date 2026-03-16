document.addEventListener("DOMContentLoaded", () => {
  restoreOptions();
  setupWheelControls();

  document.getElementById("saveBtn").addEventListener("click", saveOptions);
  document.getElementById("runBtn").addEventListener("click", sendPublishCommand);
  document.getElementById("resetTimeBtn").addEventListener("click", resetLastTime);
  document.getElementById("addProfileBtn").addEventListener("click", addProfile);
  document.getElementById("delProfileBtn").addEventListener("click", deleteProfile);
  document.getElementById("profileSelect").addEventListener("change", loadProfileData);
  document.getElementById("setTodayBtn").addEventListener("click", () => setBaseDate(0));
  document.getElementById("setTomorrowBtn").addEventListener("click", () => setBaseDate(1));
  document.getElementById("applyBaseDateBtn").addEventListener("click", applyBaseDateInputs);
});

let currentProfile = "default";
let allSettings = {};

function setupWheelControls() {
  const inputs = document.querySelectorAll(".num-input");
  inputs.forEach((input) => {
    input.addEventListener("wheel", function (e) {
      e.preventDefault();
      let val = parseInt(this.value) || 0;
      const max = this.max ? parseInt(this.max) : (this.id.includes("Hour") || this.id.includes("H") ? 23 : 59);
      const min = this.min ? parseInt(this.min) : 0;
      if (e.deltaY < 0) val++; else val--;
      if (val > max) val = min;
      if (val < min) val = max;
      this.value = val.toString().padStart(2, "0");
    });
  });
}

async function setBaseDate(addDays) {
  const now = new Date();
  now.setDate(now.getDate() + addDays);
  const h = parseInt(document.getElementById("startHour").value || "9", 10);
  const m = parseInt(document.getElementById("startMin").value || "0", 10);
  now.setHours(h, m, 0, 0);

  document.getElementById("baseYear").value = now.getFullYear();
  document.getElementById("baseMonth").value = String(now.getMonth() + 1).padStart(2, "0");
  document.getElementById("baseDay").value = String(now.getDate()).padStart(2, "0");

  updateLastScheduled(now);
  await saveOptions(true);
  loadProfileData();
  alert(`기준 날짜가 [${addDays === 0 ? "오늘" : "내일"}]로 설정되었습니다.\n다음 발행은 설정된 시간 이후 계산됩니다.`);
}

function applyBaseDateInputs() {
  const y = parseInt(document.getElementById("baseYear").value, 10);
  const m = parseInt(document.getElementById("baseMonth").value, 10);
  const d = parseInt(document.getElementById("baseDay").value, 10);
  if (!y || !m || !d) return alert("년/월/일을 모두 입력하세요.");
  const h = parseInt(document.getElementById("startHour").value || "9", 10);
  const mi = parseInt(document.getElementById("startMin").value || "0", 10);
  const base = new Date(y, m - 1, d, h, mi, 0, 0);
  updateLastScheduled(base);
  saveOptions(true);
  loadProfileData();
  alert(`기준 날짜가 ${y}.${String(m).padStart(2, "0")}.${String(d).padStart(2, "0")} ${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")} 로 설정되었습니다.`);
}

function updateLastScheduled(date) {
  if (!allSettings[currentProfile]) allSettings[currentProfile] = {};
  allSettings[currentProfile].lastScheduled = date.toISOString();
}

async function restoreOptions() {
  const data = await chrome.storage.local.get(["settings", "currentProfile"]);
  allSettings = data.settings || { default: {} };
  currentProfile = data.currentProfile || "default";
  updateProfileSelect();
  loadProfileData();
}

function updateProfileSelect() {
  const select = document.getElementById("profileSelect");
  select.innerHTML = "";
  Object.keys(allSettings).forEach((key) => {
    const option = document.createElement("option");
    option.value = key;
    option.text = key;
    if (key === currentProfile) option.selected = true;
    select.appendChild(option);
  });
}

function loadProfileData() {
  currentProfile = document.getElementById("profileSelect").value;
  const settings = allSettings[currentProfile] || {};
  document.getElementById("categoryName").value = settings.category || "";
  const [sh, sm] = (settings.startTime || "09:00").split(":");
  document.getElementById("startHour").value = sh || "";
  document.getElementById("startMin").value = sm || "";
  document.getElementById("intervalMin").value = settings.interval || 60;
  if (document.getElementById("blockStartH")) document.getElementById("blockStartH").value = settings.blockStartH || "";
  if (document.getElementById("blockStartM")) document.getElementById("blockStartM").value = settings.blockStartM || "00";
  if (document.getElementById("blockEndH")) document.getElementById("blockEndH").value = settings.blockEndH || "";
  if (document.getElementById("blockEndM")) document.getElementById("blockEndM").value = settings.blockEndM || "00";

  const lastTime = settings.lastScheduled ? new Date(settings.lastScheduled) : null;
  if (lastTime) {
    document.getElementById("baseYear").value = lastTime.getFullYear();
    document.getElementById("baseMonth").value = String(lastTime.getMonth() + 1).padStart(2, "0");
    document.getElementById("baseDay").value = String(lastTime.getDate()).padStart(2, "0");
  }
  document.getElementById("lastScheduledInfo").value = lastTime
    ? `${lastTime.getMonth() + 1}/${lastTime.getDate()} ${lastTime.getHours()}:${String(lastTime.getMinutes()).padStart(2, "0")}`
    : "기록 없음 (시작 시간부터 계산)";
}

async function saveOptions(skipAlert) {
  const sh = (document.getElementById("startHour").value || "09").padStart(2, "0");
  const sm = (document.getElementById("startMin").value || "00").padStart(2, "0");
  const getVal = (id) => (document.getElementById(id) ? document.getElementById(id).value : "");
  const settings = {
    category: document.getElementById("categoryName").value,
    startTime: `${sh}:${sm}`,
    interval: document.getElementById("intervalMin").value || 60,
    blockStartH: getVal("blockStartH"),
    blockStartM: getVal("blockStartM") || "00",
    blockEndH: getVal("blockEndH"),
    blockEndM: getVal("blockEndM") || "00",
    lastScheduled: allSettings[currentProfile]?.lastScheduled || null,
  };
  allSettings[currentProfile] = settings;
  await chrome.storage.local.set({ settings: allSettings, currentProfile });
  if (skipAlert) return;
  const btn = document.getElementById("saveBtn");
  btn.innerText = "저장 완료";
  btn.classList.add("saved");
  setTimeout(() => {
    btn.innerText = "설정 저장";
    btn.classList.remove("saved");
  }, 1000);
}

function addProfile() {
  const name = prompt("새 프로필 이름:");
  if (name) {
    allSettings[name] = {};
    currentProfile = name;
    saveOptions(true);
    restoreOptions();
  }
}

function deleteProfile() {
  if (!confirm("현재 프로필을 삭제할까요?")) return;
  delete allSettings[currentProfile];
  currentProfile = Object.keys(allSettings)[0] || "default";
  saveOptions(true);
  restoreOptions();
}

function resetLastTime() {
  if (allSettings[currentProfile]) {
    allSettings[currentProfile].lastScheduled = null;
    saveOptions(true);
    loadProfileData();
    alert("마지막 예약 기록을 초기화했습니다.");
  }
}

function sendPublishCommand() {
  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
    if (tabs.length > 0) {
      chrome.tabs.sendMessage(tabs[0].id, { action: "TRIGGER_PUBLISH_BY_POPUP" });
    }
  });
}
