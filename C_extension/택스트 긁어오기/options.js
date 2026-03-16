const SHORTCUT_STORAGE_KEY = "shortcutHotkey";
const CAPTURE_SECURITY_MODE_KEY = "captureSecurityMode";
const CAPTURE_SECURITY_MODE_STANDARD = "standard";
const CAPTURE_SECURITY_MODE_SAFE = "safe";
const DEFAULT_SHORTCUT = {
  code: "KeyH",
  ctrl: true,
  alt: false,
  shift: true,
  meta: false
};

const MODIFIER_CODES = new Set([
  "ShiftLeft",
  "ShiftRight",
  "ControlLeft",
  "ControlRight",
  "AltLeft",
  "AltRight",
  "MetaLeft",
  "MetaRight"
]);

const shortcutPreviewEl = document.getElementById("shortcut-preview");
const recordBtn = document.getElementById("record-btn");
const resetBtn = document.getElementById("reset-btn");
const statusEl = document.getElementById("status");
const modeStatusEl = document.getElementById("mode-status");
const modeInputs = Array.from(
  document.querySelectorAll("input[name='capture-security-mode']")
);

let recording = false;
let currentShortcut = { ...DEFAULT_SHORTCUT };
let currentCaptureSecurityMode = CAPTURE_SECURITY_MODE_SAFE;

recordBtn.addEventListener("click", () => {
  recording = true;
  setStatus("Press the key combination now. (Esc: cancel)");
  renderRecordingState();
});

resetBtn.addEventListener("click", async () => {
  await saveShortcut(DEFAULT_SHORTCUT);
  currentShortcut = { ...DEFAULT_SHORTCUT };
  recording = false;
  renderShortcut();
  renderRecordingState();
  setStatus(`Reset to default: ${formatShortcut(currentShortcut)}`);
});

window.addEventListener("keydown", async (event) => {
  if (!recording) {
    return;
  }

  event.preventDefault();
  event.stopImmediatePropagation();
  event.stopPropagation();

  if (event.key === "Escape") {
    recording = false;
    renderRecordingState();
    setStatus("Shortcut recording was cancelled.");
    return;
  }

  if (MODIFIER_CODES.has(event.code)) {
    setStatus("Modifier-only shortcut is not allowed.");
    return;
  }

  const hasModifier = event.ctrlKey || event.altKey || event.shiftKey || event.metaKey;
  const isFunctionKey = /^F\d{1,2}$/.test(event.code);
  if (!hasModifier && !isFunctionKey) {
    setStatus("Use at least one modifier key (or a function key like F8).");
    return;
  }

  const shortcut = {
    code: event.code,
    ctrl: event.ctrlKey,
    alt: event.altKey,
    shift: event.shiftKey,
    meta: event.metaKey
  };

  await saveShortcut(shortcut);
  currentShortcut = shortcut;
  recording = false;
  renderShortcut();
  renderRecordingState();
  setStatus(`Saved: ${formatShortcut(currentShortcut)}`);
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local") {
    return;
  }

  if (changes[SHORTCUT_STORAGE_KEY]) {
    currentShortcut = normalizeShortcut(changes[SHORTCUT_STORAGE_KEY].newValue);
    renderShortcut();
  }

  if (changes[CAPTURE_SECURITY_MODE_KEY]) {
    currentCaptureSecurityMode = normalizeCaptureSecurityMode(
      changes[CAPTURE_SECURITY_MODE_KEY].newValue
    );
    renderCaptureSecurityMode();
  }
});

init().catch((error) => {
  setStatus(`Init failed: ${error.message}`);
});

async function init() {
  modeInputs.forEach((input) => {
    input.addEventListener("change", async () => {
      if (!input.checked) {
        return;
      }

      const nextMode = normalizeCaptureSecurityMode(input.value);
      await saveCaptureSecurityMode(nextMode);
      currentCaptureSecurityMode = nextMode;
      renderCaptureSecurityMode();
      setStatus(`Capture mode changed: ${buildCaptureSecurityModeLabel(nextMode)}`);
    });
  });

  const result = await chrome.storage.local.get([
    SHORTCUT_STORAGE_KEY,
    CAPTURE_SECURITY_MODE_KEY
  ]);
  currentShortcut = normalizeShortcut(result[SHORTCUT_STORAGE_KEY]);
  currentCaptureSecurityMode = normalizeCaptureSecurityMode(
    result[CAPTURE_SECURITY_MODE_KEY]
  );
  renderShortcut();
  renderRecordingState();
  renderCaptureSecurityMode();
  setStatus(`Current shortcut: ${formatShortcut(currentShortcut)}`);
}

function normalizeShortcut(value) {
  if (!value || typeof value !== "object" || typeof value.code !== "string" || !value.code) {
    return { ...DEFAULT_SHORTCUT };
  }

  return {
    code: value.code,
    ctrl: Boolean(value.ctrl),
    alt: Boolean(value.alt),
    shift: Boolean(value.shift),
    meta: Boolean(value.meta)
  };
}

async function saveShortcut(shortcut) {
  await chrome.storage.local.set({
    [SHORTCUT_STORAGE_KEY]: normalizeShortcut(shortcut)
  });
}

function normalizeCaptureSecurityMode(value) {
  if (value === CAPTURE_SECURITY_MODE_STANDARD) {
    return CAPTURE_SECURITY_MODE_STANDARD;
  }
  return CAPTURE_SECURITY_MODE_SAFE;
}

async function saveCaptureSecurityMode(mode) {
  await chrome.storage.local.set({
    [CAPTURE_SECURITY_MODE_KEY]: normalizeCaptureSecurityMode(mode)
  });
}

function renderShortcut() {
  shortcutPreviewEl.textContent = formatShortcut(currentShortcut);
}

function renderRecordingState() {
  recordBtn.textContent = recording ? "Waiting for keys..." : "Record Shortcut";
  recordBtn.disabled = recording;
}

function setStatus(message) {
  statusEl.textContent = message;
}

function renderCaptureSecurityMode() {
  for (const input of modeInputs) {
    input.checked = input.value === currentCaptureSecurityMode;
  }
  modeStatusEl.textContent = `Current mode: ${buildCaptureSecurityModeLabel(
    currentCaptureSecurityMode
  )}`;
}

function buildCaptureSecurityModeLabel(mode) {
  if (mode === CAPTURE_SECURITY_MODE_SAFE) {
    return "Safe";
  }
  return "Standard";
}

function formatShortcut(shortcut) {
  const parts = [];
  if (shortcut.ctrl) {
    parts.push("Ctrl");
  }
  if (shortcut.alt) {
    parts.push("Alt");
  }
  if (shortcut.shift) {
    parts.push("Shift");
  }
  if (shortcut.meta) {
    parts.push("Meta");
  }
  parts.push(formatCodeLabel(shortcut.code));
  return parts.join(" + ");
}

function formatCodeLabel(code) {
  if (!code) {
    return "?";
  }

  if (code.startsWith("Key")) {
    return code.slice(3).toUpperCase();
  }

  if (code.startsWith("Digit")) {
    return code.slice(5);
  }

  const mapping = {
    Backquote: "`",
    Minus: "-",
    Equal: "=",
    BracketLeft: "[",
    BracketRight: "]",
    Backslash: "\\",
    Semicolon: ";",
    Quote: "'",
    Comma: ",",
    Period: ".",
    Slash: "/",
    Space: "Space",
    Escape: "Esc"
  };

  return mapping[code] || code;
}
