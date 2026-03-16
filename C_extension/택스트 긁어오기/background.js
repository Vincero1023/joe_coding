const MENU_UNLOCK_ID = "text-copy-helper-unlock";
const MENU_SETTINGS_ID = "text-copy-helper-settings";
const PICK_RESULT_MESSAGE = "text-copy-helper-pick-result";
const PICK_CANCEL_MESSAGE = "text-copy-helper-pick-cancel";
const SHORTCUT_TRIGGER_MESSAGE = "text-copy-helper-shortcut-trigger";
const CAPTURE_MODE_VIEWER = "viewer";
const CAPTURE_MODE_DOWNLOAD = "download";
const CAPTURE_SECURITY_MODE_KEY = "captureSecurityMode";
const CAPTURE_SECURITY_MODE_STANDARD = "standard";
const CAPTURE_SECURITY_MODE_SAFE = "safe";

const pendingPickRequests = new Map();

chrome.runtime.onInstalled.addListener(() => {
  ensureContextMenu();
  void ensureShortcutListenerOnOpenTabs();
});

chrome.runtime.onStartup.addListener(() => {
  ensureContextMenu();
  void ensureShortcutListenerOnOpenTabs();
});

chrome.tabs.onRemoved.addListener((tabId) => {
  for (const [requestId, state] of pendingPickRequests.entries()) {
    if (state.tabId === tabId) {
      pendingPickRequests.delete(requestId);
    }
  }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") {
    return;
  }

  const url = (tab && tab.url) || changeInfo.url || "";
  if (!isInjectablePageUrl(url)) {
    return;
  }

  void ensureShortcutListenerOnTab(tabId);
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab || !tab.id) {
    return;
  }
  await startFramePickMode(tab, CAPTURE_MODE_VIEWER);
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === MENU_SETTINGS_ID) {
    await chrome.runtime.openOptionsPage();
    return;
  }

  if (info.menuItemId !== MENU_UNLOCK_ID || !tab || !tab.id) {
    return;
  }

  try {
    await unlockTabProtections(tab.id);
    await showToastOnTab(tab.id, "Text Copy Helper: unlock patch applied");
  } catch (error) {
    console.error("[Text Copy Helper] unlock failed:", error);
    await openViewerWithError(tab.url || "", normalizeError(error));
  }
});

chrome.runtime.onMessage.addListener((message, sender) => {
  if (!message || typeof message !== "object") {
    return;
  }

  if (message.type === PICK_RESULT_MESSAGE) {
    void handleFramePickResult(message, sender);
    return;
  }

  if (message.type === PICK_CANCEL_MESSAGE) {
    void handleFramePickCancel(message);
    return;
  }

  if (message.type === SHORTCUT_TRIGGER_MESSAGE) {
    void handleShortcutTrigger(sender);
  }
});

function ensureContextMenu() {
  chrome.contextMenus.removeAll(() => {
    // Ignore if no existing menu is present.
    chrome.runtime.lastError;

    createContextMenuItem({
      id: MENU_UNLOCK_ID,
      title: "Text Copy Helper: Unlock right-click and text selection",
      contexts: ["all"]
    });

    createContextMenuItem({
      id: MENU_SETTINGS_ID,
      title: "Text Copy Helper: Open settings",
      contexts: ["action"]
    });
  });
}

function createContextMenuItem(details) {
  chrome.contextMenus.create(details, () => {
    const err = chrome.runtime.lastError;
    if (err && !err.message.toLowerCase().includes("duplicate")) {
      console.error("[Text Copy Helper] context menu create failed:", err.message);
    }
  });
}

async function ensureShortcutListenerOnOpenTabs() {
  let tabs = [];
  try {
    tabs = await chrome.tabs.query({});
  } catch {
    return;
  }

  for (const tab of tabs) {
    if (!tab || !tab.id || !isInjectablePageUrl(tab.url || "")) {
      continue;
    }

    await ensureShortcutListenerOnTab(tab.id);
  }
}

async function ensureShortcutListenerOnTab(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      files: ["shortcut-listener.js"],
      world: "ISOLATED"
    });
  } catch {
    // Ignore restricted pages or transient injection errors.
  }
}

function isInjectablePageUrl(url) {
  return /^(https?|file):/i.test(url);
}

async function startFramePickMode(tab, mode = CAPTURE_MODE_VIEWER) {
  try {
    await clearPendingPickRequestsForTab(tab.id);
    const captureSecurityMode = await getCaptureSecurityMode();
    let effectiveCaptureSecurityMode = captureSecurityMode;
    if (captureSecurityMode === CAPTURE_SECURITY_MODE_STANDARD) {
      try {
        await unlockTabProtections(tab.id);
      } catch (error) {
        if (!isPageAccessError(error)) {
          throw error;
        }
        effectiveCaptureSecurityMode = CAPTURE_SECURITY_MODE_SAFE;
      }
    }

    const requestId = createCaptureId();
    pendingPickRequests.set(requestId, {
      tabId: tab.id,
      url: tab.url || "",
      mode,
      captureSecurityMode: effectiveCaptureSecurityMode,
      startedAt: Date.now()
    });

    await executeScriptAllFramesWithFallback(tab.id, {
      func: installFramePicker,
      args: [requestId, PICK_RESULT_MESSAGE, PICK_CANCEL_MESSAGE]
    });

    await showToastOnTab(
      tab.id,
      buildPickModeToastMessage(mode, effectiveCaptureSecurityMode)
    );
  } catch (error) {
    console.error("[Text Copy Helper] frame pick mode failed:", error);
    await openViewerWithError(tab.url || "", normalizeError(error));
  }
}

async function handleFramePickResult(message, sender) {
  const requestId = message.requestId;
  if (!requestId || !pendingPickRequests.has(requestId)) {
    return;
  }

  const pending = pendingPickRequests.get(requestId);
  pendingPickRequests.delete(requestId);
  await clearFramePicker(pending.tabId, requestId);

  try {
    if (message.error) {
      throw new Error(message.error);
    }

    const result = message.result;
    if (!result || !result.html || !result.html.trim()) {
      throw new Error("Readable content was not found in the clicked frame.");
    }

    const payload = {
      ...result,
      pickedByClick: true,
      frameId: typeof sender.frameId === "number" ? sender.frameId : null
    };

    if (pending.mode === CAPTURE_MODE_DOWNLOAD) {
      await downloadCaptureAsHtml(payload);
      await showToastOnTab(pending.tabId, "Text Copy Helper: HTML downloaded.");
      return;
    }

    await openViewerWithCapture(payload);
  } catch (error) {
    if (pending.mode === CAPTURE_MODE_DOWNLOAD) {
      console.error("[Text Copy Helper] auto download failed:", error);
      await showToastOnTab(
        pending.tabId,
        `Text Copy Helper: auto download failed (${normalizeError(error)}).`
      );
    }
    const url = (pending && pending.url) || "";
    await openViewerWithError(url, normalizeError(error));
  }
}

async function handleShortcutTrigger(sender) {
  const tab = sender && sender.tab;
  if (!tab || !tab.id) {
    return;
  }

  try {
    await startFramePickMode(tab, CAPTURE_MODE_DOWNLOAD);
  } catch (error) {
    console.error("[Text Copy Helper] shortcut trigger failed:", error);
  }
}

async function handleFramePickCancel(message) {
  const requestId = message.requestId;
  if (!requestId || !pendingPickRequests.has(requestId)) {
    return;
  }

  const pending = pendingPickRequests.get(requestId);
  pendingPickRequests.delete(requestId);
  await clearFramePicker(pending.tabId, requestId);
}

async function clearPendingPickRequestsForTab(tabId) {
  const requestIds = [];
  for (const [requestId, state] of pendingPickRequests.entries()) {
    if (state.tabId === tabId) {
      requestIds.push(requestId);
    }
  }

  for (const requestId of requestIds) {
    pendingPickRequests.delete(requestId);
    await clearFramePicker(tabId, requestId);
  }
}

async function clearFramePicker(tabId, requestId) {
  try {
    await executeScriptAllFramesWithFallback(tabId, {
      func: removeFramePicker,
      args: [requestId]
    });
  } catch {
    // Ignore cleanup failure.
  }
}

async function openViewerWithCapture(result) {
  const captureId = createCaptureId();
  const storageKey = `capture:${captureId}`;
  const payload = {
    ...result,
    capturedAt: new Date().toISOString()
  };

  await chrome.storage.local.set({ [storageKey]: payload });
  await openViewer(`viewer.html?id=${encodeURIComponent(captureId)}`);
}

function createCaptureId() {
  if (globalThis.crypto && globalThis.crypto.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function unlockTabProtections(tabId) {
  await executeScriptAllFramesWithFallback(tabId, {
    world: "MAIN",
    func: unlockPageProtection
  });
}

async function showToastOnTab(tabId, message) {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: showOnPageToast,
    args: [message]
  });
}

function buildPickModeToastMessage(mode, captureSecurityMode) {
  const isSafeMode = captureSecurityMode === CAPTURE_SECURITY_MODE_SAFE;
  const suffix = isSafeMode ? " (safe mode: unlock skipped)" : "";

  if (mode === CAPTURE_MODE_DOWNLOAD) {
    return `Text Copy Helper: click target once to capture and download HTML${suffix}.`;
  }

  return `Text Copy Helper: pick mode enabled. Click the target frame/page once${suffix}.`;
}

async function getCaptureSecurityMode() {
  const result = await chrome.storage.local.get(CAPTURE_SECURITY_MODE_KEY);
  return normalizeCaptureSecurityMode(result[CAPTURE_SECURITY_MODE_KEY]);
}

function normalizeCaptureSecurityMode(value) {
  if (value === CAPTURE_SECURITY_MODE_STANDARD) {
    return CAPTURE_SECURITY_MODE_STANDARD;
  }
  return CAPTURE_SECURITY_MODE_SAFE;
}

function isPageAccessError(error) {
  const message = error && typeof error.message === "string" ? error.message : String(error);
  return /Cannot access contents of (the )?(url|page)/i.test(message);
}

async function executeScriptAllFramesWithFallback(tabId, details) {
  try {
    return await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      ...details
    });
  } catch {
    return chrome.scripting.executeScript({
      target: { tabId },
      ...details
    });
  }
}

async function openViewerWithError(url, message) {
  const path = `viewer.html?error=${encodeURIComponent(message)}&url=${encodeURIComponent(url)}`;
  await openViewer(path);
}

async function openViewer(path) {
  const viewerUrl = chrome.runtime.getURL(path);

  try {
    await chrome.windows.create({
      url: viewerUrl,
      type: "popup",
      width: 1280,
      height: 940
    });
    return;
  } catch {
    // Fall back to a normal tab if popup creation is unavailable.
  }

  await chrome.tabs.create({ url: viewerUrl });
}

async function downloadCaptureAsHtml(result) {
  const html = resolveHtmlForDownload(result);
  if (!html || !html.trim()) {
    throw new Error("Nothing to download");
  }

  const filename = buildHtmlFileName(result.title || "capture");
  const dataUrl = `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;

  await chrome.downloads.download({
    url: dataUrl,
    filename,
    saveAs: false,
    conflictAction: "uniquify"
  });
}

function resolveHtmlForDownload(result) {
  if (result.fullDocumentHtml && result.fullDocumentHtml.trim()) {
    return result.fullDocumentHtml;
  }

  return buildFallbackDocument(result.html || "", result.url || "");
}

function buildFallbackDocument(bodyHtml, baseUrl) {
  const escapedBase = escapeAttribute(baseUrl || "about:blank");
  return [
    "<!doctype html><html><head>",
    '<meta charset="utf-8">',
    `<base href="${escapedBase}">`,
    "</head><body>",
    bodyHtml,
    "</body></html>"
  ].join("");
}

function buildHtmlFileName(rawTitle) {
  const safeTitle =
    String(rawTitle || "capture")
      .replace(/[\\/:*?"<>|]/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 80) || "capture";

  const stamp = new Date().toISOString().replace(/[:]/g, "-").replace(/\..+$/, "");
  return `${safeTitle}-${stamp}.html`;
}

function escapeAttribute(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function normalizeError(error) {
  const message = error && typeof error.message === "string" ? error.message : String(error);
  if (!message) {
    return "Unknown error";
  }
  if (message.includes("Cannot access contents of url")) {
    return "Chrome policy blocks this page (for example chrome:// or Chrome Web Store).";
  }
  return message;
}

function installFramePicker(requestId, pickResultMessage, pickCancelMessage) {
  const stateKey = "__textCopyHelperFramePickerState__";
  const registry = window[stateKey] || {};
  if (registry[requestId]) {
    return;
  }
  window[stateKey] = registry;

  const priorCursor = document.documentElement.style.cursor;
  document.documentElement.style.cursor = "crosshair";

  const banner = document.createElement("div");
  banner.dataset.textCopyHelper = "picker-banner";
  banner.textContent = "Text Copy Helper: click this frame/page to capture. Esc to cancel.";
  banner.style.position = "fixed";
  banner.style.top = "10px";
  banner.style.left = "10px";
  banner.style.zIndex = "2147483647";
  banner.style.background = "rgba(18, 20, 23, 0.95)";
  banner.style.color = "#fff";
  banner.style.padding = "8px 10px";
  banner.style.borderRadius = "6px";
  banner.style.fontFamily = "Segoe UI, sans-serif";
  banner.style.fontSize = "12px";
  banner.style.pointerEvents = "none";
  document.documentElement.appendChild(banner);

  const cleanup = () => {
    document.removeEventListener("click", onClick, true);
    window.removeEventListener("keydown", onKeyDown, true);
    if (banner.isConnected) {
      banner.remove();
    }
    document.documentElement.style.cursor = priorCursor;
    delete registry[requestId];
  };

  const onClick = (event) => {
    if (event.button !== 0) {
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    event.stopPropagation();
    cleanup();

    try {
      const result = extractFrameSnapshot();
      chrome.runtime.sendMessage({
        type: pickResultMessage,
        requestId,
        result
      });
    } catch (error) {
      chrome.runtime.sendMessage({
        type: pickResultMessage,
        requestId,
        error: error && error.message ? error.message : String(error)
      });
    }
  };

  const onKeyDown = (event) => {
    if (event.key !== "Escape") {
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    event.stopPropagation();
    cleanup();

    chrome.runtime.sendMessage({
      type: pickCancelMessage,
      requestId
    });
  };

  document.addEventListener("click", onClick, true);
  window.addEventListener("keydown", onKeyDown, true);
  registry[requestId] = { cleanup };

  function extractFrameSnapshot() {
    const snapshot = buildVisualSnapshot();

    if (!snapshot.bodyHtml.trim()) {
      const fallback = buildTextFallback();
      snapshot.bodyHtml = fallback.html;
      snapshot.fullDocumentHtml = buildFallbackDocumentHtml(fallback.html);
      snapshot.textLength = fallback.textLength;
    }

    return {
      title: document.title || "Untitled",
      url: location.href,
      selectionUsed: false,
      html: snapshot.bodyHtml,
      fullDocumentHtml: snapshot.fullDocumentHtml,
      textLength: snapshot.textLength,
      renderMode: "visual"
    };
  }

  function buildVisualSnapshot() {
    const headClone = document.head ? document.head.cloneNode(true) : document.createElement("head");
    const bodyClone = document.body ? document.body.cloneNode(true) : document.createElement("body");

    stripDisallowedNodes(headClone, true);
    stripDisallowedNodes(bodyClone, false);

    sanitizeClone(headClone, true);
    sanitizeClone(bodyClone, false);

    const baseHref = document.baseURI || location.href;
    const unlockStyle = `
      <style id="__text_copy_helper_snapshot_unlock__">
        html, body, body * {
          user-select: text !important;
          -webkit-user-select: text !important;
          -moz-user-select: text !important;
          -ms-user-select: text !important;
        }
      </style>
    `;

    const fullDocumentHtml = [
      "<!doctype html><html><head>",
      '<meta charset="utf-8">',
      `<base href="${escapeAttr(baseHref)}">`,
      headClone.innerHTML,
      unlockStyle,
      "</head><body>",
      bodyClone.innerHTML,
      "</body></html>"
    ].join("");

    return {
      bodyHtml: bodyClone.innerHTML.trim(),
      fullDocumentHtml,
      textLength: (bodyClone.textContent || "").trim().length
    };
  }

  function stripDisallowedNodes(root, inHead) {
    const selectors = inHead
      ? ["script", "noscript", "template", "base"]
      : ["script", "noscript", "template"];

    for (const selector of selectors) {
      root.querySelectorAll(selector).forEach((node) => node.remove());
    }

    if (inHead) {
      root.querySelectorAll("meta[http-equiv]").forEach((meta) => {
        const equiv = (meta.getAttribute("http-equiv") || "").toLowerCase();
        if (equiv === "content-security-policy") {
          meta.remove();
        }
      });
    }

    root
      .querySelectorAll(
        "#__text_copy_helper_toast__,#__text_copy_helper_unlock_style__,#__text_copy_helper_snapshot_unlock__,[data-text-copy-helper='picker-banner']"
      )
      .forEach((node) => node.remove());
  }

  function sanitizeClone(root, inHead) {
    const nodes = [root, ...Array.from(root.querySelectorAll("*"))];

    for (const node of nodes) {
      for (const attr of Array.from(node.attributes || [])) {
        const name = attr.name.toLowerCase();
        const value = attr.value || "";

        if (name.startsWith("on")) {
          node.removeAttribute(attr.name);
          continue;
        }

        if (["href", "src", "poster"].includes(name)) {
          if (/^\s*javascript:/i.test(value)) {
            node.removeAttribute(attr.name);
            continue;
          }
          node.setAttribute(attr.name, toAbsoluteUrl(value));
          continue;
        }

        if (name === "srcset") {
          node.setAttribute(attr.name, absolutizeSrcset(value));
          continue;
        }
      }

      if (!inHead) {
        const tag = node.tagName ? node.tagName.toLowerCase() : "";
        if (tag === "a") {
          node.setAttribute("target", "_blank");
          node.setAttribute("rel", "noopener noreferrer");
        }
        if (tag === "img") {
          hydrateLazyImage(node);
        }
      }
    }
  }

  function toAbsoluteUrl(rawValue) {
    if (!rawValue || rawValue.startsWith("data:")) {
      return rawValue || "";
    }
    try {
      return new URL(rawValue, document.baseURI).href;
    } catch {
      return rawValue;
    }
  }

  function absolutizeSrcset(srcset) {
    if (!srcset) {
      return "";
    }

    return srcset
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
      .map((entry) => {
        const parts = entry.split(/\s+/);
        const urlPart = parts.shift() || "";
        const descriptor = parts.join(" ");
        const absoluteUrl = toAbsoluteUrl(urlPart);
        return descriptor ? `${absoluteUrl} ${descriptor}` : absoluteUrl;
      })
      .join(", ");
  }

  function hydrateLazyImage(img) {
    if (img.getAttribute("src")) {
      return;
    }

    const fallbackAttrs = ["data-src", "data-original", "data-lazy-src", "data-url"];
    for (const attr of fallbackAttrs) {
      const value = img.getAttribute(attr);
      if (value) {
        img.setAttribute("src", toAbsoluteUrl(value));
        return;
      }
    }
  }

  function buildFallbackDocumentHtml(bodyHtml) {
    return [
      "<!doctype html><html><head>",
      '<meta charset="utf-8">',
      `<base href="${escapeAttr(document.baseURI || location.href)}">`,
      "</head><body>",
      bodyHtml,
      "</body></html>"
    ].join("");
  }

  function buildTextFallback() {
    const raw = (document.body && document.body.innerText ? document.body.innerText : "").trim();
    if (!raw) {
      return { html: "", textLength: 0 };
    }

    const paragraphs = raw
      .split(/\n{2,}/)
      .map((part) => part.trim())
      .filter(Boolean)
      .slice(0, 1200);

    const html = paragraphs
      .map((part) => `<p>${escapeHtml(part).replace(/\n/g, "<br>")}</p>`)
      .join("\n");

    return { html, textLength: raw.length };
  }

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escapeAttr(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
}

function removeFramePicker(requestId) {
  const stateKey = "__textCopyHelperFramePickerState__";
  const registry = window[stateKey];
  if (!registry || !registry[requestId]) {
    return;
  }

  const entry = registry[requestId];
  if (entry && typeof entry.cleanup === "function") {
    entry.cleanup();
  }
}

function unlockPageProtection() {
  const styleId = "__text_copy_helper_unlock_style__";
  if (!document.getElementById(styleId)) {
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      html, body, body * {
        user-select: text !important;
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
        -webkit-touch-callout: default !important;
      }
      body * {
        caret-color: auto !important;
      }
    `;
    document.documentElement.appendChild(style);
  }

  document.documentElement.style.userSelect = "text";
  if (document.body) {
    document.body.style.userSelect = "text";
  }

  const inlineHandlers = [
    "oncopy",
    "oncut",
    "onpaste",
    "oncontextmenu",
    "onselectstart",
    "ondragstart",
    "onmousedown",
    "onmouseup",
    "onkeydown"
  ];

  const all = [document.documentElement, ...Array.from(document.querySelectorAll("*"))];
  for (const element of all) {
    for (const attr of inlineHandlers) {
      if (element.hasAttribute(attr)) {
        element.removeAttribute(attr);
      }
    }
  }

  document.oncontextmenu = null;
  document.onselectstart = null;
  document.ondragstart = null;
  document.oncopy = null;
  document.oncut = null;
  document.onpaste = null;

  if (!window.__textCopyHelperPatchApplied) {
    const blockedTypes = new Set([
      "contextmenu",
      "selectstart",
      "copy",
      "cut",
      "paste",
      "dragstart"
    ]);

    const originalPreventDefault = Event.prototype.preventDefault;
    Event.prototype.preventDefault = function patchedPreventDefault() {
      if (blockedTypes.has(this.type)) {
        return;
      }
      return originalPreventDefault.call(this);
    };

    window.__textCopyHelperPatchApplied = true;
  }

  return true;
}

function showOnPageToast(message) {
  const existing = document.getElementById("__text_copy_helper_toast__");
  if (existing) {
    existing.remove();
  }

  const toast = document.createElement("div");
  toast.id = "__text_copy_helper_toast__";
  toast.textContent = message;
  toast.style.position = "fixed";
  toast.style.right = "16px";
  toast.style.bottom = "16px";
  toast.style.zIndex = "2147483647";
  toast.style.background = "rgba(18, 20, 23, 0.95)";
  toast.style.color = "#fff";
  toast.style.padding = "10px 12px";
  toast.style.borderRadius = "8px";
  toast.style.fontFamily = "Segoe UI, sans-serif";
  toast.style.fontSize = "12px";
  toast.style.lineHeight = "1.2";
  toast.style.boxShadow = "0 8px 30px rgba(0,0,0,0.25)";
  document.documentElement.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 1800);
}
