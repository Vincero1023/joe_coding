(function () {
  if (window.top !== window) {
    return;
  }

  function isEditableTarget(target) {
    if (!target || !(target instanceof HTMLElement)) {
      return false;
    }
    const tag = target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      return true;
    }
    if (target.isContentEditable) {
      return true;
    }
    return Boolean(target.closest("[contenteditable='true'], input, textarea, select"));
  }

  function resolveActionByKey(event) {
    if (!event.ctrlKey || !event.shiftKey || event.altKey || event.metaKey) {
      return "";
    }
    switch (event.code) {
      case "Digit1":
        return "open";
      case "Digit2":
        return "copy";
      case "Digit3":
        return "download";
      case "Digit4":
        return "summarize";
      default:
        return "";
    }
  }

  document.addEventListener(
    "keydown",
    (event) => {
      if (event.repeat) {
        return;
      }
      if (isEditableTarget(event.target)) {
        return;
      }

      const action = resolveActionByKey(event);
      if (!action) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      chrome.runtime.sendMessage({
        type: "run-action",
        action,
        source: "content-shortcut"
      });
    },
    true
  );
})();
