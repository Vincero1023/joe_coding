(() => {
  const SHORTCUT_STORAGE_KEY = "shortcutHotkey";
  const SHORTCUT_TRIGGER_MESSAGE = "text-copy-helper-shortcut-trigger";
  const SHORTCUT_LISTENER_INIT_KEY = "__textCopyHelperShortcutListenerInstalled__";
  const DEFAULT_SHORTCUT = {
    code: "KeyH",
    ctrl: true,
    alt: false,
    shift: true,
    meta: false
  };

  let currentShortcut = { ...DEFAULT_SHORTCUT };
  const extensionApi = getExtensionApi();

  if (extensionApi && !globalThis[SHORTCUT_LISTENER_INIT_KEY]) {
    globalThis[SHORTCUT_LISTENER_INIT_KEY] = true;
    initShortcutListener().catch((error) => {
      console.error("[Text Copy Helper] shortcut listener init failed:", error);
    });
  }

  async function initShortcutListener() {
    await loadShortcutFromStorage();
    extensionApi.storage.onChanged.addListener(handleStorageChange);
    window.addEventListener("keydown", handleKeyDown, true);
  }

  async function loadShortcutFromStorage() {
    const result = await extensionApi.storage.local.get(SHORTCUT_STORAGE_KEY);
    currentShortcut = normalizeShortcut(result[SHORTCUT_STORAGE_KEY]);
  }

  function handleStorageChange(changes, areaName) {
    if (areaName !== "local" || !changes[SHORTCUT_STORAGE_KEY]) {
      return;
    }

    currentShortcut = normalizeShortcut(changes[SHORTCUT_STORAGE_KEY].newValue);
  }

  function handleKeyDown(event) {
    if (event.repeat) {
      return;
    }

    if (isEditableTarget(event.target)) {
      return;
    }

    if (!matchesShortcut(event, currentShortcut)) {
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    event.stopPropagation();

    sendShortcutTriggerMessage();
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

  function matchesShortcut(event, shortcut) {
    return (
      event.code === shortcut.code &&
      event.ctrlKey === shortcut.ctrl &&
      event.altKey === shortcut.alt &&
      event.shiftKey === shortcut.shift &&
      event.metaKey === shortcut.meta
    );
  }

  function isEditableTarget(target) {
    if (!(target instanceof Element)) {
      return false;
    }

    const editableContainer = target.closest("input, textarea, select, [contenteditable]");
    if (editableContainer) {
      const tag = editableContainer.tagName.toLowerCase();
      if (["input", "textarea", "select"].includes(tag)) {
        return true;
      }
      if (editableContainer.isContentEditable) {
        return true;
      }
    }

    return target.getAttribute("role") === "textbox";
  }

  function sendShortcutTriggerMessage() {
    if (!extensionApi || !extensionApi.runtime || typeof extensionApi.runtime.sendMessage !== "function") {
      return;
    }

    try {
      const maybePromise = extensionApi.runtime.sendMessage({
        type: SHORTCUT_TRIGGER_MESSAGE
      });
      if (maybePromise && typeof maybePromise.catch === "function") {
        maybePromise.catch(() => {
          // Ignore if the extension context is reloading.
        });
        return;
      }

      // Callback form fallback (no promise) to consume runtime errors silently.
      extensionApi.runtime.sendMessage(
        { type: SHORTCUT_TRIGGER_MESSAGE },
        () => extensionApi.runtime.lastError
      );
    } catch {
      // Ignore transient runtime errors.
    }
  }

  function getExtensionApi() {
    const api = globalThis.chrome;
    if (!api || !api.runtime || !api.runtime.id || !api.storage || !api.storage.local) {
      return null;
    }
    return api;
  }
})();
