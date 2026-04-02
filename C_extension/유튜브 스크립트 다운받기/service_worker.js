const STORAGE_KEYS = {
  settings: "settings",
  lastResult: "lastResult",
  errorLogs: "errorLogs",
  transcriptCache: "transcriptCache",
  debugState: "debugState"
};

const BUILD_ID = "2026-04-02-direct-llm-stability";
const MAX_ERROR_LOGS = 200;
const TRANSCRIPT_CACHE_TTL_MS = 6 * 60 * 60 * 1000;
const SHORTCUT_DEDUP_MS = 900;
const FETCH_RETRY_ATTEMPTS = 2;
const FETCH_RETRY_DELAY_MS = 450;
const FETCH_TIMEOUT_MS = 7000;
const TRANSCRIPT_LINE_TARGET = 88;
const SENTENCE_HARD_MAX = Math.round(TRANSCRIPT_LINE_TARGET * 1.65);
const PARAGRAPH_MIN_SENTENCES = 3;
const PARAGRAPH_MAX_SENTENCES = 5;
const PARAGRAPH_HARD_MAX = Math.round(TRANSCRIPT_LINE_TARGET * 4.8);
const recentShortcutActions = new Map();
const TRANSCRIPT_FETCH_STEP_IDS = Object.freeze([
  "current-page",
  "source-tab",
  "watch-html",
  "temporary-watch-tab"
]);
const TRANSCRIPT_HEALTH_RECENT_SUCCESS_MS = 3 * 24 * 60 * 60 * 1000;
const MOBILE_PLAYER_CLIENTS = Object.freeze([
  {
    label: "ios",
    headerClientName: "5",
    headerClientVersion: "20.10.4",
    contextClient: {
      clientName: "IOS",
      clientVersion: "20.10.4",
      deviceModel: "iPhone16,2",
      hl: "ko",
      gl: "KR",
      utcOffsetMinutes: 540
    }
  },
  {
    label: "android",
    headerClientName: "3",
    headerClientVersion: "20.10.38",
    contextClient: {
      clientName: "ANDROID",
      clientVersion: "20.10.38",
      androidSdkVersion: 34,
      hl: "ko",
      gl: "KR",
      utcOffsetMinutes: 540
    }
  }
]);
const DEFAULT_DEBUG_STATE = Object.freeze({
  lastFetch: null,
  lastError: null,
  pathHealth: {
    lastSuccessfulPath: "",
    strategies: {}
  }
});

const DEFAULT_SUMMARY_TEMPLATE = [
  "Analyze the following YouTube transcript and organize it in a 2-layer output.",
  "",
  "[Layer 1: Structure For Understanding]",
  "- One-sentence core claim of the video",
  "- Organize into 5-10 thought blocks",
  "- Compress each block into 2-3 sentences",
  "- Keep the logical flow explicit",
  "",
  "[Layer 2: Reusable Material Extraction]",
  "Extract and present as a table:",
  "- Quotes / notable lines",
  "- Statistics / data / experiment results",
  "- Cases / examples",
  "- References / books / papers",
  "For each item include:",
  "- Short summary",
  "- Where it can be reused (sermon/lecture/blog/etc)",
  "- Category",
  "- 3-5 hashtags",
  "",
  "Focus on thought-structure decomposition and material extraction, not generic summarization.",
  "",
  "Title: {{TITLE}}",
  "URL: {{URL}}",
  "",
  "Transcript:",
  "{{TEXT}}"
].join("\n");

const DEFAULT_MANUAL_TEMPLATE = [
  "Turn the following YouTube transcript into a detailed practical manual in Markdown.",
  "",
  "Context:",
  "- The source is usually an information video, explainer, tutorial, walkthrough, review, or process guide.",
  "- Reconstruct the content into a usable manual even if the speaker is conversational or repetitive.",
  "- Remove filler, repetition, sponsor talk, greetings, and off-topic remarks.",
  "",
  "Output requirements:",
  "- Return valid Markdown only",
  "- Start with `# {{TITLE}} Manual`",
  "- Then include these sections in order:",
  "  1. `## Overview`",
  "  2. `## Who This Is For`",
  "  3. `## What You Need Before Starting`",
  "  4. `## Key Concepts`",
  "  5. `## Step-by-Step Instructions`",
  "  6. `## Important Tips and Warnings`",
  "  7. `## Common Mistakes / Troubleshooting`",
  "  8. `## Quick Checklist`",
  "  9. `## Source Notes`",
  "- In `Step-by-Step Instructions`, create numbered steps and add sub-bullets for details, conditions, examples, and decision points.",
  "- If the video implies missing assumptions, state them explicitly as `Assumption:` instead of inventing facts.",
  "- If there are multiple methods, split them into separate subsections and explain when to use each.",
  "- Keep technical details concrete and operational.",
  "- Preserve important terminology from the source.",
  "- End `Source Notes` with:",
  "  - `Video Title: {{TITLE}}`",
  "  - `Video URL: {{URL}}`",
  "",
  "Transcript:",
  "{{TEXT}}"
].join("\n");

const AI_TARGETS = {
  chatgpt: "https://chatgpt.com/",
  gpt5_2: "https://chatgpt.com/",
  gpt5_2_instant: "https://chatgpt.com/",
  gpt5_2_thinking: "https://chatgpt.com/",
  gpt5_1_instant: "https://chatgpt.com/",
  gpt5_1_thinking: "https://chatgpt.com/",
  gpt4o: "https://chatgpt.com/",
  custom: "https://chatgpt.com/",
  custom_gpts: "https://chatgpt.com/gpts",
  claude: "https://claude.ai/new",
  opus_4_5: "https://claude.ai/new",
  haiku_4_5: "https://claude.ai/new",
  mistral: "https://chat.mistral.ai/chat",
  gemini: "https://gemini.google.com/app",
  ai_studio: "https://aistudio.google.com/prompts/new_chat",
  grok: "https://grok.com/"
};

const DEFAULT_SETTINGS = {
  preferredLanguage: "",
  gptSiteUrl: "https://chatgpt.com/",
  aiModel: "chatgpt",
  autoSubmit: true,
  chatgptTemporaryChat: true,
  summaryTemplate: DEFAULT_SUMMARY_TEMPLATE,
  summaryPreset: "default",
  manualTemplate: DEFAULT_MANUAL_TEMPLATE,
  manualPreset: "default"
};

const COMMAND_TO_ACTION = {
  open_transcript_1: "open",
  copy_transcript_2: "copy",
  download_transcript_3: "download",
  summarize_transcript_4: "summarize"
};

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get([
    STORAGE_KEYS.settings,
    STORAGE_KEYS.errorLogs,
    STORAGE_KEYS.transcriptCache,
    STORAGE_KEYS.debugState
  ]);

  await chrome.storage.local.set({
    [STORAGE_KEYS.settings]: { ...DEFAULT_SETTINGS, ...(current[STORAGE_KEYS.settings] || {}) },
    [STORAGE_KEYS.errorLogs]: Array.isArray(current[STORAGE_KEYS.errorLogs])
      ? current[STORAGE_KEYS.errorLogs]
      : [],
    [STORAGE_KEYS.transcriptCache]:
      current[STORAGE_KEYS.transcriptCache] &&
      typeof current[STORAGE_KEYS.transcriptCache] === "object"
        ? current[STORAGE_KEYS.transcriptCache]
        : {},
    [STORAGE_KEYS.debugState]:
      current[STORAGE_KEYS.debugState] &&
      typeof current[STORAGE_KEYS.debugState] === "object"
        ? current[STORAGE_KEYS.debugState]
        : { lastFetch: null, lastError: null }
  });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "run-action" && message?.action) {
    respondWith(
      sendResponse,
      "run-action",
      () =>
        runAction(message.action, {
          source: String(message.source || "popup"),
          fromShortcut: message.source === "content-shortcut"
        }),
      { action: message.action, source: message.source || "popup" }
    );
    return true;
  }

  if (message?.type === "get-settings") {
    respondWith(sendResponse, "get-settings", getSettings);
    return true;
  }

  if (message?.type === "save-settings" && message?.settings) {
    respondWith(sendResponse, "save-settings", () => saveSettings(message.settings));
    return true;
  }

  if (message?.type === "get-error-log" && message?.errorCode) {
    respondWith(sendResponse, "get-error-log", async () => ({ log: await getErrorLogByCode(message.errorCode) }));
    return true;
  }

  if (message?.type === "get-latest-error-log") {
    respondWith(sendResponse, "get-latest-error-log", async () => ({ log: await getLatestErrorLog() }));
    return true;
  }

  if (message?.type === "get-debug-state") {
    respondWith(sendResponse, "get-debug-state", getDebugState);
    return true;
  }

  return false;
});

chrome.commands.onCommand.addListener(async (command) => {
  const action = COMMAND_TO_ACTION[command];
  if (!action) {
    return;
  }

  try {
    const options = { fromShortcut: true, source: "commands-api" };
    if (command === "summarize_transcript_4") {
      options.forceAiModel = "chatgpt";
    }

    const result = await runAction(action, options);
    console.log(`Command success (${command}): ${result}`);
  } catch (error) {
    await writeErrorLog({
      scope: "command",
      error,
      meta: { command }
    });
    if (command === "copy_transcript_2") {
      await showNotification("Copy failed", "Could not copy transcript. Open popup and try again.");
    }
    console.error(`Command failed (${command}):`, error);
  }
});

async function respondWith(sendResponse, scope, fn, meta = {}) {
  try {
    const value = await fn();
    if (value && typeof value === "object" && "log" in value) {
      sendResponse({ ok: true, log: value.log || null });
      return;
    }
    if (scope === "run-action") {
      sendResponse({ ok: true, result: value });
      return;
    }
    if (scope === "get-settings" || scope === "save-settings") {
      sendResponse({ ok: true, settings: value });
      return;
    }
    sendResponse({ ok: true, data: value });
  } catch (error) {
    const code = await writeErrorLog({ scope, error, meta });
    sendResponse({
      ok: false,
      error: safeErrorMessage(error),
      errorCode: code
    });
  }
}

async function writeErrorLog({ scope, error, meta = {} }) {
  const message = safeErrorMessage(error);
  const category = classifyErrorCategory(message, scope);
  const code = generateErrorCode(category);
  const version = chrome.runtime.getManifest()?.version || "unknown";

  const entry = {
    code,
    scope: String(scope || "unknown"),
    category,
    message,
    stack: safeErrorStack(error),
    meta,
    buildId: BUILD_ID,
    version,
    createdAt: new Date().toISOString()
  };

  try {
    const stored = await chrome.storage.local.get(STORAGE_KEYS.errorLogs);
    const current = Array.isArray(stored[STORAGE_KEYS.errorLogs])
      ? stored[STORAGE_KEYS.errorLogs]
      : [];
    await chrome.storage.local.set({
      [STORAGE_KEYS.errorLogs]: [entry, ...current].slice(0, MAX_ERROR_LOGS)
    });
    await saveDebugState({ lastError: entry });
  } catch (storageError) {
    console.error("Failed to write error log:", storageError);
  }

  return code;
}

function generateErrorCode(category = "E999") {
  const t = Date.now().toString(36).toUpperCase();
  const r = Math.random().toString(36).slice(2, 8).toUpperCase();
  return `YT-${category}-${t}-${r}`;
}

function classifyErrorCategory(message, scope) {
  const text = String(message || "").toLowerCase();
  const s = String(scope || "").toLowerCase();

  if (text.includes("not youtube watch") || text.includes("video id")) return "E101";
  if (text.includes("android player") || text.includes("mobile player")) return "E202";
  if (text.includes("innertube failed") || text.includes("precondition check failed")) return "E301";
  if (text.includes("source tab extract failed")) return "E350";
  if (text.includes("temporary-watch-tab") || text.includes("helper tab")) return "E351";
  if (text.includes("html-response") || text.includes("timedtext failed")) return "E201";
  if (text.includes("texttracks")) return "E401";
  if (text.includes("transcript panel")) return "E501";
  if (text.includes("download") || text.includes("createobjecturl")) return "E701";
  if (text.includes("clipboard") || text.includes("copy")) return "E702";
  if (s.includes("save-settings") || s.includes("get-settings")) return "E601";
  return "E999";
}

function safeErrorMessage(error) {
  if (error && typeof error.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  return String(error || "unknown error");
}

function safeErrorStack(error) {
  return error && typeof error.stack === "string" ? error.stack : "";
}

async function getErrorLogByCode(code) {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.errorLogs);
  const list = Array.isArray(stored[STORAGE_KEYS.errorLogs]) ? stored[STORAGE_KEYS.errorLogs] : [];
  return list.find((item) => item?.code === code) || null;
}

async function getLatestErrorLog() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.errorLogs);
  const list = Array.isArray(stored[STORAGE_KEYS.errorLogs]) ? stored[STORAGE_KEYS.errorLogs] : [];
  return list[0] || null;
}

async function getDebugState() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.debugState);
  const state = stored[STORAGE_KEYS.debugState];
  if (state && typeof state === "object") {
    return {
      ...DEFAULT_DEBUG_STATE,
      ...state,
      pathHealth: normalizeTranscriptPathHealth(state.pathHealth)
    };
  }
  return {
    ...DEFAULT_DEBUG_STATE,
    pathHealth: normalizeTranscriptPathHealth(DEFAULT_DEBUG_STATE.pathHealth)
  };
}

async function saveDebugState(patch) {
  const current = await getDebugState();
  await chrome.storage.local.set({
    [STORAGE_KEYS.debugState]: {
      ...current,
      ...patch
    }
  });
}

function normalizeTranscriptPathHealth(value) {
  const normalized = {
    lastSuccessfulPath: "",
    strategies: {}
  };

  if (!value || typeof value !== "object") {
    return normalized;
  }

  if (typeof value.lastSuccessfulPath === "string") {
    normalized.lastSuccessfulPath = value.lastSuccessfulPath;
  }

  const strategies =
    value.strategies && typeof value.strategies === "object" ? value.strategies : {};

  for (const step of TRANSCRIPT_FETCH_STEP_IDS) {
    const current = strategies[step];
    if (!current || typeof current !== "object") continue;

    normalized.strategies[step] = {
      successCount: Number.isFinite(Number(current.successCount)) ? Number(current.successCount) : 0,
      failureCount: Number.isFinite(Number(current.failureCount)) ? Number(current.failureCount) : 0,
      consecutiveFailures: Number.isFinite(Number(current.consecutiveFailures))
        ? Number(current.consecutiveFailures)
        : 0,
      lastResult: current.lastResult === "ok" ? "ok" : current.lastResult === "fail" ? "fail" : "",
      lastOkAt: Number.isFinite(Number(current.lastOkAt)) ? Number(current.lastOkAt) : 0,
      lastFailAt: Number.isFinite(Number(current.lastFailAt)) ? Number(current.lastFailAt) : 0,
      lastMessage: typeof current.lastMessage === "string" ? current.lastMessage : "",
      lastDetail: typeof current.lastDetail === "string" ? current.lastDetail : ""
    };
  }

  return normalized;
}

function getTranscriptPathPriority(step, baseIndex, pathHealth, now = Date.now()) {
  const strategies = pathHealth?.strategies || {};
  const state = strategies[step] || null;
  let score = baseIndex * 100;

  // Keep the helper-tab path as a last-resort option unless other paths have clearly degraded.
  if (step === "temporary-watch-tab") score += 180;

  if (pathHealth?.lastSuccessfulPath === step) score -= 260;
  if (state?.lastResult === "ok") score -= 70;
  if (state?.lastOkAt && now - state.lastOkAt < TRANSCRIPT_HEALTH_RECENT_SUCCESS_MS) score -= 35;

  const failStreak = Number(state?.consecutiveFailures || 0);
  if (failStreak >= 2) score += 80 + (failStreak - 2) * 25;
  if (state?.lastResult === "fail") score += 10;
  if ((state?.failureCount || 0) > 0 && !(state?.successCount || 0)) score += 20;

  return score;
}

function prioritizeTranscriptFetchSteps(steps, pathHealth) {
  const baseOrder = new Map(steps.map((item, index) => [item.step, index]));
  const normalizedHealth = normalizeTranscriptPathHealth(pathHealth);
  const now = Date.now();

  return [...steps].sort((a, b) => {
    const scoreA = getTranscriptPathPriority(a.step, baseOrder.get(a.step) ?? 99, normalizedHealth, now);
    const scoreB = getTranscriptPathPriority(b.step, baseOrder.get(b.step) ?? 99, normalizedHealth, now);
    if (scoreA !== scoreB) return scoreA - scoreB;
    return (baseOrder.get(a.step) ?? 99) - (baseOrder.get(b.step) ?? 99);
  });
}

async function updateTranscriptPathHealth(step, ok, message = "", detail = "") {
  if (!TRANSCRIPT_FETCH_STEP_IDS.includes(step)) return null;

  const current = await getDebugState();
  const pathHealth = normalizeTranscriptPathHealth(current.pathHealth);
  const existing = pathHealth.strategies[step] || {
    successCount: 0,
    failureCount: 0,
    consecutiveFailures: 0,
    lastResult: "",
    lastOkAt: 0,
    lastFailAt: 0,
    lastMessage: "",
    lastDetail: ""
  };
  const now = Date.now();

  const next = {
    ...existing,
    lastResult: ok ? "ok" : "fail",
    lastMessage: String(message || "").slice(0, 300),
    lastDetail: String(detail || "").slice(0, 300)
  };

  if (ok) {
    next.successCount += 1;
    next.consecutiveFailures = 0;
    next.lastOkAt = now;
    pathHealth.lastSuccessfulPath = step;
  } else {
    next.failureCount += 1;
    next.consecutiveFailures += 1;
    next.lastFailAt = now;
  }

  pathHealth.strategies[step] = next;
  await saveDebugState({ pathHealth });
  return pathHealth;
}
async function getSettings() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.settings);
  const merged = { ...DEFAULT_SETTINGS, ...(stored[STORAGE_KEYS.settings] || {}) };
  merged.aiModel = normalizeAiModel(merged.aiModel);
  merged.autoSubmit = Boolean(merged.autoSubmit);
  merged.chatgptTemporaryChat = Boolean(merged.chatgptTemporaryChat);
  merged.gptSiteUrl = normalizeGptSiteUrl(merged.gptSiteUrl);
  merged.summaryTemplate = normalizePromptTemplate(merged.summaryTemplate, DEFAULT_SUMMARY_TEMPLATE);
  if (!merged.summaryTemplate.includes("{{TEXT}}")) {
    merged.summaryTemplate = DEFAULT_SUMMARY_TEMPLATE;
  }
  merged.manualTemplate = normalizePromptTemplate(merged.manualTemplate, DEFAULT_MANUAL_TEMPLATE);
  if (!merged.manualTemplate.includes("{{TEXT}}")) {
    merged.manualTemplate = DEFAULT_MANUAL_TEMPLATE;
  }
  return merged;
}

async function saveSettings(partialSettings) {
  const next = { ...(await getSettings()), ...partialSettings };
  next.aiModel = normalizeAiModel(next.aiModel);
  next.autoSubmit = Boolean(next.autoSubmit);
  next.chatgptTemporaryChat = Boolean(next.chatgptTemporaryChat);
  next.summaryTemplate = normalizePromptTemplate(next.summaryTemplate, DEFAULT_SUMMARY_TEMPLATE);
  next.manualTemplate = normalizePromptTemplate(next.manualTemplate, DEFAULT_MANUAL_TEMPLATE);
  next.gptSiteUrl = normalizeGptSiteUrl(next.gptSiteUrl);
  await chrome.storage.local.set({ [STORAGE_KEYS.settings]: next });
  return next;
}

async function getCachedTranscript(videoId) {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.transcriptCache);
  const cache =
    stored[STORAGE_KEYS.transcriptCache] &&
    typeof stored[STORAGE_KEYS.transcriptCache] === "object"
      ? stored[STORAGE_KEYS.transcriptCache]
      : {};

  const item = cache[videoId];
  if (!item || typeof item !== "object") return null;
  if (!item.transcript || typeof item.transcript !== "string") return null;

  const ageMs = Date.now() - Number(item.cachedAt || 0);
  if (!Number.isFinite(ageMs) || ageMs > TRANSCRIPT_CACHE_TTL_MS) return null;

  return item;
}

async function saveCachedTranscript(videoId, data) {
  if (!videoId || !data?.transcript) return;

  const stored = await chrome.storage.local.get(STORAGE_KEYS.transcriptCache);
  const current =
    stored[STORAGE_KEYS.transcriptCache] &&
    typeof stored[STORAGE_KEYS.transcriptCache] === "object"
      ? stored[STORAGE_KEYS.transcriptCache]
      : {};

  await chrome.storage.local.set({
    [STORAGE_KEYS.transcriptCache]: {
      ...current,
      [videoId]: {
        ...data,
        cachedAt: Date.now()
      }
    }
  });
}

async function runAction(action, options = {}) {
  if (options.fromShortcut && isDuplicateShortcutAction(action)) {
    return "Shortcut duplicate ignored.";
  }

  const tabInfo = await resolveActiveVideoTab();
  const transcriptData = await fetchTranscriptForVideo(tabInfo.videoId, tabInfo.tabId);
  const settings = action === "summarize" || action === "manualize" ? await getSettings() : null;

  if (action === "open") {
    await saveResultForViewer({
      ...transcriptData,
      promptText: "",
      promptKind: "",
      promptTitle: "",
      gptSiteUrl: ""
    });
    await openTranscriptViewer(tabInfo.tabId);
    return "Transcript opened.";
  }

  if (action === "download") {
    await downloadTranscript(transcriptData);
    return "Transcript downloaded.";
  }

  if (action === "summarize") {
    const forcedModel =
      options.forceAiModel || (options.fromShortcut ? "chatgpt" : settings.aiModel);
    const aiModel = normalizeAiModel(forcedModel);
    const targetUrl = resolveAiTargetUrl(aiModel, settings.gptSiteUrl, {
      temporaryChat: Boolean(settings.chatgptTemporaryChat)
    });
    const summaryPrompt = buildPromptFromTemplate(transcriptData, settings.summaryTemplate);

    await saveResultForViewer({
      ...transcriptData,
      promptText: summaryPrompt,
      promptKind: "summary",
      promptTitle: "AI Summary Prompt",
      gptSiteUrl: targetUrl,
      aiModel
    });
    let gptTab = null;
    try {
      gptTab = await chrome.tabs.create({ url: targetUrl });
    } catch {
      const copiedPrompt = await copyTextToClipboard(tabInfo.tabId, summaryPrompt);
      return copiedPrompt
        ? "Could not open the AI page automatically, so the prompt was copied to clipboard."
        : "Could not open the AI page automatically, but the prompt was saved. Use action 1 only if you need to inspect or copy it.";
    }
    const insertResult = await tryInsertPromptToTab(gptTab?.id, summaryPrompt, {
      autoSubmit: Boolean(settings.autoSubmit),
      model: aiModel,
      temporaryChat: Boolean(settings.chatgptTemporaryChat)
    });
    if (insertResult?.inserted && insertResult?.submitted) {
      return "Prompt inserted and sent automatically.";
    }
    if (insertResult?.inserted) {
      return "Prompt inserted. Press Enter if send did not trigger.";
    }
    const copiedPrompt = await copyTextToClipboard(tabInfo.tabId, summaryPrompt);
    return copiedPrompt
      ? "Prompt ready. Auto-fill failed, so the prompt was copied to clipboard."
      : "Prompt ready. Auto-fill failed, but the prompt was saved. Use action 1 only if you need to inspect or copy it.";
  }

  if (action === "manualize") {
    const forcedModel =
      options.forceAiModel || (options.fromShortcut ? "chatgpt" : settings.aiModel);
    const aiModel = normalizeAiModel(forcedModel);
    const targetUrl = resolveAiTargetUrl(aiModel, settings.gptSiteUrl, {
      temporaryChat: Boolean(settings.chatgptTemporaryChat)
    });
    const manualPrompt = buildPromptFromTemplate(transcriptData, settings.manualTemplate);

    await saveResultForViewer({
      ...transcriptData,
      promptText: manualPrompt,
      promptKind: "manual",
      promptTitle: "AI Manual Prompt",
      gptSiteUrl: targetUrl,
      aiModel
    });
    let gptTab = null;
    try {
      gptTab = await chrome.tabs.create({ url: targetUrl });
    } catch {
      const copiedPrompt = await copyTextToClipboard(tabInfo.tabId, manualPrompt);
      return copiedPrompt
        ? "Could not open the AI page automatically, so the manual prompt was copied to clipboard."
        : "Could not open the AI page automatically, but the manual prompt was saved. Use action 1 only if you need to inspect or copy it.";
    }
    const insertResult = await tryInsertPromptToTab(gptTab?.id, manualPrompt, {
      autoSubmit: Boolean(settings.autoSubmit),
      model: aiModel,
      temporaryChat: Boolean(settings.chatgptTemporaryChat)
    });
    if (insertResult?.inserted && insertResult?.submitted) {
      return "Manual prompt inserted and sent automatically.";
    }
    if (insertResult?.inserted) {
      return "Manual prompt inserted. Press Enter if send did not trigger.";
    }
    const copiedPrompt = await copyTextToClipboard(tabInfo.tabId, manualPrompt);
    return copiedPrompt
      ? "Manual prompt ready. Auto-fill failed, so the prompt was copied to clipboard."
      : "Manual prompt ready. Auto-fill failed, but the prompt was saved. Use action 1 only if you need to inspect or copy it.";
  }

  if (action === "copy") {
    await copyTranscriptToClipboard(tabInfo.tabId, transcriptData.transcript);
    await showNotification("Transcript copied", "Transcript copied to clipboard.");
    return "Transcript copied to clipboard.";
  }

  throw new Error(`Unsupported action: ${action}`);
}

function isDuplicateShortcutAction(action) {
  const key = String(action || "");
  const now = Date.now();
  const last = Number(recentShortcutActions.get(key) || 0);
  recentShortcutActions.set(key, now);
  return now - last < SHORTCUT_DEDUP_MS;
}

async function showNotification(title, message) {
  try {
    if (!chrome.notifications?.create) {
      return;
    }
    await chrome.notifications.create({
      type: "basic",
      iconUrl: chrome.runtime.getURL("icons/icon128.png"),
      title: String(title || "Notification"),
      message: String(message || "")
    });
  } catch {
    // ignore notification failure
  }
}

async function saveLastResult(result) {
  await chrome.storage.local.set({ [STORAGE_KEYS.lastResult]: result });
}

async function saveResultForViewer(result) {
  try {
    await saveLastResult(result);
    return { storageFallback: false };
  } catch (error) {
    const compact = {
      videoId: result?.videoId || "",
      videoUrl: result?.videoUrl || "",
      title: result?.title || "YouTube Transcript",
      languageCode: result?.languageCode || "unknown",
      trackName: result?.trackName || "-",
      fetchedAt: result?.fetchedAt || new Date().toISOString(),
      transcript: "",
      promptText: String(result?.promptText || "").trim(),
      promptKind: String(result?.promptKind || "").trim(),
      promptTitle: String(result?.promptTitle || "").trim(),
      gptSiteUrl: result?.gptSiteUrl || "",
      aiModel: result?.aiModel || "",
      debugInfo: result?.debugInfo || null,
      storageFallback: true
    };

    await saveLastResult(compact);
    return { storageFallback: true, originalError: error };
  }
}

async function openTranscriptViewer(tabId) {
  await chrome.tabs.create({ url: chrome.runtime.getURL("transcript.html") });
}

async function resolveActiveVideoTab() {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  const tab = tabs[0];

  if (!tab?.url || typeof tab.id !== "number") {
    throw new Error("Active tab not found.");
  }

  let videoId = extractVideoId(tab.url);
  if (!videoId) {
    videoId = await detectEmbeddedVideoId(tab.id);
  }

  if (!videoId) {
    throw new Error("YouTube video ID not found on this page.");
  }

  return {
    tabId: tab.id,
    sourceUrl: tab.url,
    videoId
  };
}

function extractVideoId(rawUrl) {
  try {
    const url = new URL(rawUrl);
    const host = url.hostname.replace(/^www\./, "");

    if (host === "youtu.be") {
      return normalizeVideoId(url.pathname.split("/").filter(Boolean)[0] || "");
    }

    if (!host.includes("youtube.com") && host !== "youtube-nocookie.com") {
      return null;
    }

    if (url.pathname === "/watch") {
      return normalizeVideoId(url.searchParams.get("v") || "");
    }

    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "embed" || parts[0] === "shorts" || parts[0] === "live" || parts[0] === "v") {
      return normalizeVideoId(parts[1] || "");
    }

    return null;
  } catch {
    return null;
  }
}

function normalizeVideoId(input) {
  const value = String(input || "").trim();
  return /^[A-Za-z0-9_-]{10,15}$/.test(value) ? value : null;
}

async function detectEmbeddedVideoId(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const idRegex = /^[A-Za-z0-9_-]{10,15}$/;

        function normalizeId(value) {
          const id = String(value || "").trim();
          return idRegex.test(id) ? id : null;
        }

        function fromUrl(rawUrl) {
          try {
            const url = new URL(rawUrl, window.location.href);
            const host = url.hostname.replace(/^www\./, "");

            if (host === "youtu.be") {
              return normalizeId(url.pathname.split("/").filter(Boolean)[0] || "");
            }

            if (!host.includes("youtube.com") && host !== "youtube-nocookie.com") {
              return null;
            }

            if (url.pathname === "/watch") {
              return normalizeId(url.searchParams.get("v") || "");
            }

            const parts = url.pathname.split("/").filter(Boolean);
            if (parts[0] === "embed" || parts[0] === "shorts" || parts[0] === "live" || parts[0] === "v") {
              return normalizeId(parts[1] || "");
            }
          } catch {
            return null;
          }
          return null;
        }

        const selectors = [
          "iframe[src]",
          "embed[src]",
          "object[data]",
          "a[href*='youtube.com']",
          "a[href*='youtu.be']"
        ];

        const found = [];
        for (const selector of selectors) {
          document.querySelectorAll(selector).forEach((node) => {
            const raw = node.getAttribute("src") || node.getAttribute("data") || node.getAttribute("href");
            const id = fromUrl(raw || "");
            if (id) found.push(id);
          });
        }

        return found[0] || null;
      }
    });

    return results?.[0]?.result || null;
  } catch {
    return null;
  }
}

function buildTranscriptFetchSteps({ videoId, sourceTabId, sourceTab, preferredLanguage, fallbackTitle }) {
  return [
    {
      step: "current-page",
      canRun: typeof sourceTabId === "number",
      run: () => fetchTranscriptFromCurrentPage(sourceTabId, videoId, preferredLanguage)
    },
    {
      step: "source-tab",
      canRun:
        typeof sourceTabId === "number" &&
        Boolean(sourceTab?.url && sourceTab.url.includes("youtube.com/watch")),
      run: () => fetchTranscriptViaSourceTab(sourceTabId, preferredLanguage)
    },
    {
      step: "watch-html",
      canRun: true,
      run: () => fetchTranscriptViaWatchPage(videoId, preferredLanguage, fallbackTitle)
    },
    {
      step: "temporary-watch-tab",
      canRun: true,
      run: () => fetchTranscriptViaTemporaryWatchTab(videoId, preferredLanguage)
    }
  ].filter((item) => item.canRun);
}

function buildTranscriptFetchOutput({
  videoId,
  fallbackTitle,
  step,
  data,
  attempts,
  strategyOrder
}) {
  return {
    videoId,
    videoUrl: `https://www.youtube.com/watch?v=${videoId}`,
    title: data.title || fallbackTitle || `youtube-${videoId}`,
    languageCode: data.languageCode || "unknown",
    trackName: data.trackName || step,
    transcript: reflowTranscriptForReading(data.transcript),
    fetchedAt: new Date().toISOString(),
    debugInfo: {
      successPath: step,
      strategyOrder,
      attempts: [...attempts, { step, ok: true, message: data.trackName || "success" }],
      buildId: BUILD_ID
    }
  };
}

async function fetchTranscriptForVideo(videoId, sourceTabId) {
  const settings = await getSettings();
  const cached = await getCachedTranscript(videoId);
  if (cached) {
    const output = {
      videoId,
      videoUrl: `https://www.youtube.com/watch?v=${videoId}`,
      title: cached.title || `youtube-${videoId}`,
      languageCode: cached.languageCode || "unknown",
      trackName: `${cached.trackName || "cache"} (cached)`,
      transcript: reflowTranscriptForReading(cached.transcript),
      fetchedAt: new Date().toISOString(),
      debugInfo: {
        successPath: "cache",
        attempts: [{ step: "cache", ok: true, message: "cache hit" }],
        buildId: BUILD_ID
      }
    };
    await saveDebugState({ lastFetch: output.debugInfo });
    return output;
  }

  const errors = [];
  const attempts = [];
  const sourceTab =
    typeof sourceTabId === "number" ? await chrome.tabs.get(sourceTabId).catch(() => null) : null;
  const fallbackTitle = normalizeYoutubeTitle(sourceTab?.title || "");
  const debugState = await getDebugState();
  const orderedSteps = prioritizeTranscriptFetchSteps(
    buildTranscriptFetchSteps({
      videoId,
      sourceTabId,
      sourceTab,
      preferredLanguage: settings.preferredLanguage,
      fallbackTitle
    }),
    debugState.pathHealth
  );
  const strategyOrder = orderedSteps.map((item) => item.step);

  for (const item of orderedSteps) {
    try {
      const data = await item.run();
      const output = buildTranscriptFetchOutput({
        videoId,
        fallbackTitle,
        step: item.step,
        data,
        attempts,
        strategyOrder
      });
      await saveCachedTranscript(videoId, output);
      await updateTranscriptPathHealth(item.step, true, data.trackName || "success", data.languageCode || "");
      await saveDebugState({ lastFetch: output.debugInfo });
      return output;
    } catch (error) {
      const message = error?.message || String(error);
      errors.push(`${item.step}: ${message}`);
      attempts.push({ step: item.step, ok: false, message });
      await updateTranscriptPathHealth(item.step, false, message);
    }
  }

  await saveDebugState({
    lastFetch: {
      successPath: "",
      failed: true,
      strategyOrder,
      attempts,
      buildId: BUILD_ID
    }
  });
  throw new Error(`[${BUILD_ID}] Failed to fetch transcript. Attempts: ${errors.slice(0, 4).join(" | ")}`);
}

async function fetchTranscriptFromCurrentPage(tabId, videoId, preferredLanguage) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    world: "MAIN",
    args: [videoId || "", preferredLanguage || ""],
    func: async (expectedVideoId, preferredLang) => {
      try {
        function normalizeVideoId(value) {
          const text = String(value || "").trim();
          return /^[A-Za-z0-9_-]{10,15}$/.test(text) ? text : "";
        }

        function normalizeLang(value) {
          return String(value || "").toLowerCase().split("-")[0].trim();
        }

        function decodeHtmlEntities(value) {
          return String(value || "")
            .replace(/&#x([0-9a-fA-F]+);/g, (_m, hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
            .replace(/&#([0-9]+);/g, (_m, dec) => String.fromCodePoint(Number.parseInt(dec, 10)))
            .replace(/&amp;/g, "&")
            .replace(/&lt;/g, "<")
            .replace(/&gt;/g, ">")
            .replace(/&quot;/g, "\"")
            .replace(/&#39;/g, "'")
            .replace(/&nbsp;/g, " ");
        }

        function parseJsonObjectSlice(text, startIndex) {
          let depth = 0;
          let inString = false;
          let escaped = false;

          for (let i = startIndex; i < text.length; i += 1) {
            const ch = text[i];
            if (inString) {
              if (escaped) escaped = false;
              else if (ch === "\\") escaped = true;
              else if (ch === "\"") inString = false;
              continue;
            }
            if (ch === "\"") {
              inString = true;
              continue;
            }
            if (ch === "{") depth += 1;
            if (ch === "}") {
              depth -= 1;
              if (depth === 0) {
                try {
                  return JSON.parse(text.slice(startIndex, i + 1));
                } catch {
                  return null;
                }
              }
            }
          }

          return null;
        }

        function getPlayerResponse() {
          try {
            if (window.ytInitialPlayerResponse) return window.ytInitialPlayerResponse;
          } catch {
            // ignore
          }

          const scripts = Array.from(document.querySelectorAll("script"));
          for (const script of scripts) {
            const text = script.textContent || "";
            if (!text.includes("ytInitialPlayerResponse")) continue;
            for (const marker of ["var ytInitialPlayerResponse =", "ytInitialPlayerResponse ="]) {
              const markerIndex = text.indexOf(marker);
              if (markerIndex < 0) continue;
              const start = text.indexOf("{", markerIndex + marker.length);
              if (start < 0) continue;
              const parsed = parseJsonObjectSlice(text, start);
              if (parsed) return parsed;
            }
          }

          return null;
        }

        function readTitle() {
          const heading = document.querySelector("ytd-watch-metadata h1, h1.ytd-watch-metadata");
          const raw = (heading?.textContent || document.title || "").trim();
          return raw.replace(/\s*-\s*YouTube\s*$/i, "").trim();
        }

        function finalize(lines) {
          const output = [];
          let prev = "";
          for (const raw of lines || []) {
            const line = String(raw || "").replace(/\s+/g, " ").trim();
            if (!line || line === prev) continue;
            output.push(line);
            prev = line;
          }
          return output.join("\n").trim();
        }

        function parsePayload(payload) {
          const text = String(payload || "");
          return parseJson(text) || parseXml(text) || parseVtt(text);
        }

        function parseJson(text) {
          const start = text.indexOf("{");
          if (start < 0) return "";
          try {
            const data = JSON.parse(text.slice(start));
            const events = Array.isArray(data?.events) ? data.events : [];
            const lines = [];
            for (const event of events) {
              if (!Array.isArray(event?.segs)) continue;
              const line = event.segs
                .map((seg) => seg?.utf8 || seg?.text || "")
                .join("")
                .replace(/\s+/g, " ")
                .trim();
              if (line) lines.push(decodeHtmlEntities(line));
            }
            return finalize(lines);
          } catch {
            return "";
          }
        }

        function parseXml(text) {
          if (!text.includes("<")) return "";
          const pattern = /<(text|p|w|s)\b[^>]*>([\s\S]*?)<\/\1>/gi;
          const lines = [];
          let match;
          while ((match = pattern.exec(text)) !== null) {
            const raw = decodeHtmlEntities(
              String(match[2] || "")
                .replace(/<br\s*\/?>/gi, "\n")
                .replace(/<[^>]+>/g, "")
            );
            const line = raw
              .split("\n")
              .map((part) => part.replace(/\s+/g, " ").trim())
              .filter(Boolean)
              .join(" ");
            if (line) lines.push(line);
          }
          return finalize(lines);
        }

        function parseVtt(text) {
          if (!text.includes("WEBVTT")) return "";
          const lines = [];
          for (const rawLine of text.split(/\r?\n/)) {
            const line = rawLine.trim();
            if (!line || line === "WEBVTT" || line.includes("-->")) continue;
            if (/^\d+$/.test(line) || /^(NOTE|STYLE|REGION)\b/i.test(line)) continue;
            const cleaned = decodeHtmlEntities(line.replace(/<[^>]+>/g, "").trim());
            if (cleaned) lines.push(cleaned);
          }
          return finalize(lines);
        }

        function getCurrentVideoId() {
          const direct = normalizeVideoId(expectedVideoId);
          if (direct) return direct;
          try {
            const url = new URL(window.location.href);
            const queryId = normalizeVideoId(url.searchParams.get("v") || "");
            if (queryId) return queryId;
            const parts = url.pathname.split("/").filter(Boolean);
            if (["shorts", "live", "embed", "v"].includes(parts[0])) {
              return normalizeVideoId(parts[1] || "");
            }
          } catch {
            // ignore
          }
          return "";
        }

        function trackName(track) {
          if (track?.name?.simpleText) return track.name.simpleText;
          if (Array.isArray(track?.name?.runs)) {
            return track.name.runs.map((item) => item?.text || "").join("").trim() || track?.languageCode || "unknown";
          }
          return track?.languageCode || "unknown";
        }

        function buildUrls(track, activeVideoId) {
          const urls = [];
          const seen = new Set();
          const pushUrl = (value) => {
            if (!value || seen.has(value)) return;
            seen.add(value);
            urls.push(value);
          };

          const base = String(track?.baseUrl || "").trim();
          if (!base) return urls;
          pushUrl(base);

          try {
            const baseUrl = new URL(base);
            for (const fmt of ["json3", "srv3", "vtt"]) {
              const next = new URL(baseUrl.toString());
              next.searchParams.set("fmt", fmt);
              pushUrl(next.toString());
            }
          } catch {
            // ignore
          }

          const lang = String(track?.languageCode || "").trim();
          if (activeVideoId && lang) {
            for (const endpoint of ["https://www.youtube.com/api/timedtext", "https://video.google.com/timedtext"]) {
              const minimal = new URL(endpoint);
              minimal.searchParams.set("v", activeVideoId);
              minimal.searchParams.set("lang", lang);
              if (track?.kind) minimal.searchParams.set("kind", track.kind);
              pushUrl(minimal.toString());
              for (const fmt of ["json3", "srv3", "vtt"]) {
                const next = new URL(minimal.toString());
                next.searchParams.set("fmt", fmt);
                pushUrl(next.toString());
              }
            }
          }

          return urls;
        }

        const playerResponse = getPlayerResponse();
        const tracks = playerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
        if (!tracks.length) {
          return { ok: false, error: "caption tracks not found in current page" };
        }

        const preferred = normalizeLang(preferredLang);
        const sorted = [...tracks].sort((a, b) => {
          const score = (track) => {
            const lang = normalizeLang(track?.languageCode);
            let value = 0;
            if (preferred && lang === preferred) value += 220;
            if (track?.kind !== "asr") value += 80;
            if (lang === "ko") value += 30;
            if (lang === "en") value += 15;
            return value;
          };
          return score(b) - score(a);
        });

        const currentVideoId = getCurrentVideoId();
        const errors = [];
        for (const track of sorted.slice(0, 5)) {
          for (const url of buildUrls(track, currentVideoId)) {
            try {
              const response = await fetch(url, { credentials: "include" });
              if (!response.ok) {
                errors.push(`${trackName(track)} HTTP ${response.status}`);
                continue;
              }
              const payload = await response.text();
              const transcript = parsePayload(payload);
              if (transcript) {
                return {
                  ok: true,
                  data: {
                    title: readTitle() || playerResponse?.videoDetails?.title || "",
                    languageCode: normalizeLang(track?.languageCode) || "unknown",
                    trackName: trackName(track),
                    transcript
                  }
                };
              }
              errors.push(`${trackName(track)} empty-parse`);
            } catch (error) {
              errors.push(error?.message || String(error));
            }
          }
        }

        return {
          ok: false,
          error: errors.slice(0, 4).join(" | ") || "caption fetch failed in current page"
        };
      } catch (error) {
        return {
          ok: false,
          error: error?.message || String(error)
        };
      }
    }
  });

  const payload = results?.[0]?.result;
  if (!payload?.ok || !payload?.data?.transcript) {
    throw new Error(payload?.error || "current page result empty");
  }

  return payload.data;
}

async function fetchTranscriptViaWatchPage(videoId, preferredLanguage, fallbackTitle = "") {
  const html = await fetchYoutubeWatchHtml(videoId);
  const localErrors = [];
  const playerResponse = extractPlayerResponseFromHtml(html);
  const tracks = playerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];

  async function tryTrackSet(sourceLabel, sourceResponse, sourceTracks) {
    const sortedTracks = sortCaptionTracksForPreference(sourceTracks, preferredLanguage);

    for (const track of sortedTracks.slice(0, 5)) {
      const urls = buildCaptionCandidateUrls(track, videoId);
      for (const url of urls) {
        try {
          const payload = await fetchCaptionPayload(url);
          const transcript = parseCaptionPayloadText(payload);
          if (!transcript) {
            localErrors.push(`${sourceLabel} ${trackDisplayName(track)} empty-parse`);
            continue;
          }

          return {
            title:
              normalizeYoutubeTitle(sourceResponse?.videoDetails?.title) ||
              extractTitleFromHtml(html) ||
              fallbackTitle ||
              `youtube-${videoId}`,
            languageCode: normalizeCaptionLanguage(track?.languageCode) || "unknown",
            trackName:
              sourceLabel === "watch-html"
                ? trackDisplayName(track)
                : `${sourceLabel}-${trackDisplayName(track)}`,
            transcript
          };
        } catch (error) {
          localErrors.push(`${sourceLabel} ${error?.message || String(error)}`);
        }
      }
    }

    return null;
  }

  if (tracks.length) {
    const fromHtmlTracks = await tryTrackSet("watch-html", playerResponse, tracks);
    if (fromHtmlTracks) return fromHtmlTracks;
  }

  try {
    const mobilePlayerResponse = await fetchPlayerResponseViaInnertube(videoId, html);
    const mobileTracks = mobilePlayerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
    if (mobileTracks.length) {
      const fromMobileTracks = await tryTrackSet("mobile-player", mobilePlayerResponse, mobileTracks);
      if (fromMobileTracks) return fromMobileTracks;
    } else {
      localErrors.push("mobile-player captionTracks not found");
    }
  } catch (error) {
    localErrors.push(error?.message || String(error));
  }

  const detail = localErrors.slice(0, 4).join(" | ");
  throw new Error(`caption fetch failed: ${detail || "caption tracks not found"}`);
}

async function fetchYoutubeWatchHtml(videoId) {
  const url =
    `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}` +
    "&hl=ko&persist_hl=1&bpctr=9999999999&has_verified=1";

  return retryOperation(
    async () => {
      const response = await fetchWithTimeout(
        url,
        {
          credentials: "include",
          cache: "no-store",
          redirect: "follow",
          headers: {
            "accept-language": "ko,en-US;q=0.9,en;q=0.8"
          }
        },
        FETCH_TIMEOUT_MS
      );

      if (!response.ok) {
        const message = `watch page HTTP ${response.status}`;
        if (isRetryableHttpStatus(response.status)) {
          throw createRetryableError(message);
        }
        throw new Error(message);
      }

      const html = await response.text();
      if (!html || html.length < 1000) {
        throw createRetryableError("watch page empty");
      }
      return html;
    },
    {
      attempts: FETCH_RETRY_ATTEMPTS,
      delayMs: FETCH_RETRY_DELAY_MS
    }
  );
}

async function fetchPlayerResponseViaInnertube(videoId, html) {
  const apiKey = extractInnertubeConfigValue(html, "INNERTUBE_API_KEY");

  if (!apiKey) {
    return null;
  }
  const localErrors = [];

  for (const client of MOBILE_PLAYER_CLIENTS) {
    const response = await retryOperation(
      () =>
        fetchWithTimeout(
          `https://www.youtube.com/youtubei/v1/player?key=${encodeURIComponent(apiKey)}&prettyPrint=false`,
          {
            method: "POST",
            credentials: "omit",
            headers: {
              "content-type": "application/json",
              "x-youtube-client-name": client.headerClientName,
              "x-youtube-client-version": client.headerClientVersion
            },
            body: JSON.stringify({
              videoId,
              contentCheckOk: true,
              racyCheckOk: true,
              context: {
                client: client.contextClient
              }
            })
          },
          FETCH_TIMEOUT_MS
        ),
      {
        attempts: FETCH_RETRY_ATTEMPTS,
        delayMs: FETCH_RETRY_DELAY_MS,
        shouldRetry: isRetryableOperationError
      }
    );

    if (!response.ok) {
      const sample = (await response.text()).slice(0, 140).replace(/\s+/g, " ").trim();
      const message = `${client.label} player HTTP ${response.status} ${sample}`;
      localErrors.push(message);
      if (isRetryableHttpStatus(response.status)) {
        continue;
      }
      continue;
    }

    const json = await response.json();
    const tracks = json?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
    if (tracks.length) {
      return json;
    }

    localErrors.push(`${client.label} captionTracks not found`);
  }

  throw new Error(`mobile player failed: ${localErrors.slice(0, 2).join(" | ") || "captionTracks not found"}`);
}

function extractPlayerResponseFromHtml(html) {
  return (
    extractJsonAssignment(html, "var ytInitialPlayerResponse =") ||
    extractJsonAssignment(html, "ytInitialPlayerResponse =") ||
    extractJsonFromKey(html, "\"playerResponse\":")
  );
}

function extractJsonAssignment(text, marker) {
  const markerIndex = text.indexOf(marker);
  if (markerIndex < 0) return null;
  const start = text.indexOf("{", markerIndex + marker.length);
  if (start < 0) return null;
  return parseJsonObjectSlice(text, start);
}

function extractJsonFromKey(text, marker) {
  const markerIndex = text.indexOf(marker);
  if (markerIndex < 0) return null;
  const start = text.indexOf("{", markerIndex + marker.length);
  if (start < 0) return null;
  return parseJsonObjectSlice(text, start);
}

function parseJsonObjectSlice(text, startIndex) {
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = startIndex; i < text.length; i += 1) {
    const ch = text[i];

    if (inString) {
      if (escaped) escaped = false;
      else if (ch === "\\") escaped = true;
      else if (ch === "\"") inString = false;
      continue;
    }

    if (ch === "\"") {
      inString = true;
      continue;
    }

    if (ch === "{") depth += 1;
    if (ch === "}") {
      depth -= 1;
      if (depth === 0) {
        try {
          return JSON.parse(text.slice(startIndex, i + 1));
        } catch {
          return null;
        }
      }
    }
  }

  return null;
}

function extractInnertubeConfigValue(html, key) {
  const patterns = [
    new RegExp(`"${escapeRegex(key)}":"([^"]+)"`),
    new RegExp(`${escapeRegex(key)}\\s*:\\s*"([^"]+)"`)
  ];

  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match?.[1]) {
      return decodeJsonEscapes(match[1]);
    }
  }

  return "";
}

function escapeRegex(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function decodeJsonEscapes(value) {
  try {
    return JSON.parse(`"${String(value || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`);
  } catch {
    return String(value || "");
  }
}

function extractTitleFromHtml(html) {
  const metaMatch =
    html.match(/<meta\s+name="title"\s+content="([^"]+)"/i) ||
    html.match(/<meta\s+property="og:title"\s+content="([^"]+)"/i);
  if (metaMatch?.[1]) {
    return decodeHtmlEntities(metaMatch[1]);
  }

  const titleMatch = html.match(/<title>([\s\S]*?)<\/title>/i);
  return normalizeYoutubeTitle(decodeHtmlEntities(titleMatch?.[1] || ""));
}

function normalizeYoutubeTitle(value) {
  return String(value || "")
    .replace(/\s*-\s*YouTube\s*$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeCaptionLanguage(value) {
  return String(value || "").toLowerCase().split("-")[0].trim();
}

function sortCaptionTracksForPreference(tracks, preferredLanguage) {
  const preferred = normalizeCaptionLanguage(preferredLanguage);

  const score = (track) => {
    const lang = normalizeCaptionLanguage(track?.languageCode);
    let value = 0;
    if (preferred && lang === preferred) value += 300;
    if (track?.kind !== "asr") value += 100;
    if (lang === "ko") value += 50;
    if (lang === "en") value += 25;
    return value;
  };

  return [...(tracks || [])].sort((a, b) => score(b) - score(a));
}

function trackDisplayName(track) {
  if (track?.name?.simpleText) return track.name.simpleText;
  if (Array.isArray(track?.name?.runs)) {
    return track.name.runs.map((item) => item?.text || "").join("").trim() || track?.languageCode || "unknown";
  }
  return track?.languageCode || "unknown";
}

function buildCaptionCandidateUrls(track, videoId) {
  const urls = [];
  const seen = new Set();
  const pushUrl = (value) => {
    if (!value || seen.has(value)) return;
    seen.add(value);
    urls.push(value);
  };

  const base = String(track?.baseUrl || "").trim();
  if (!base) return urls;

  pushUrl(base);

  try {
    const baseUrl = new URL(base);
    for (const fmt of ["json3", "srv3", "vtt"]) {
      const next = new URL(baseUrl.toString());
      next.searchParams.set("fmt", fmt);
      pushUrl(next.toString());
    }
  } catch {
    // ignore malformed base URL
  }

  const lang = String(track?.languageCode || "").trim();
  if (videoId && lang) {
    for (const endpoint of [
      "https://www.youtube.com/api/timedtext",
      "https://video.google.com/timedtext"
    ]) {
      const minimal = new URL(endpoint);
      minimal.searchParams.set("v", videoId);
      minimal.searchParams.set("lang", lang);
      if (track?.kind) minimal.searchParams.set("kind", track.kind);
      const name = getCaptionTrackNameParam(track);
      if (name) minimal.searchParams.set("name", name);
      pushUrl(minimal.toString());

      for (const fmt of ["json3", "srv3", "vtt"]) {
        const next = new URL(minimal.toString());
        next.searchParams.set("fmt", fmt);
        pushUrl(next.toString());
      }
    }
  }

  return urls;
}

function getCaptionTrackNameParam(track) {
  if (track?.vssId && String(track.vssId).includes(".")) {
    return "";
  }
  if (track?.name?.simpleText) {
    return track.name.simpleText;
  }
  if (Array.isArray(track?.name?.runs)) {
    return track.name.runs.map((item) => item?.text || "").join("").trim();
  }
  return "";
}

async function fetchCaptionPayload(url) {
  return retryOperation(
    async () => {
      const response = await fetchWithTimeout(
        url,
        {
          credentials: "include",
          cache: "no-store"
        },
        FETCH_TIMEOUT_MS
      );

      if (!response.ok) {
        const message = `caption HTTP ${response.status}`;
        if (isRetryableHttpStatus(response.status)) {
          throw createRetryableError(message);
        }
        throw new Error(message);
      }

      const text = await response.text();
      if (!text) {
        throw createRetryableError("caption empty");
      }
      if ((response.headers.get("content-type") || "").toLowerCase().includes("text/html")) {
        throw new Error("caption html-response");
      }
      return text;
    },
    {
      attempts: FETCH_RETRY_ATTEMPTS,
      delayMs: FETCH_RETRY_DELAY_MS
    }
  );
}

function parseCaptionPayloadText(payload) {
  return parseCaptionJsonText(payload) || parseCaptionXmlText(payload) || parseCaptionVttText(payload);
}

function parseCaptionJsonText(text) {
  const start = String(text || "").indexOf("{");
  if (start < 0) return "";

  try {
    const data = JSON.parse(String(text).slice(start));
    const events = Array.isArray(data?.events) ? data.events : [];
    const lines = [];

    for (const event of events) {
      if (!Array.isArray(event?.segs)) continue;
      const line = event.segs
        .map((segment) => segment?.utf8 || segment?.text || "")
        .join("")
        .replace(/\s+/g, " ")
        .trim();
      if (line) lines.push(decodeHtmlEntities(line));
    }

    return finalizeCaptionLines(lines);
  } catch {
    return "";
  }
}

function parseCaptionXmlText(text) {
  if (!String(text || "").includes("<")) return "";

  const pattern = /<(text|p|w|s)\b[^>]*>([\s\S]*?)<\/\1>/gi;
  const lines = [];
  let match;

  while ((match = pattern.exec(String(text))) !== null) {
    const raw = decodeHtmlEntities(
      String(match[2] || "")
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<[^>]+>/g, "")
    );
    const line = raw
      .split("\n")
      .map((part) => part.replace(/\s+/g, " ").trim())
      .filter(Boolean)
      .join(" ");
    if (line) lines.push(line);
  }

  return finalizeCaptionLines(lines);
}

function parseCaptionVttText(text) {
  if (!String(text || "").includes("WEBVTT")) return "";

  const lines = [];
  for (const rawLine of String(text).split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line === "WEBVTT" || line.includes("-->")) continue;
    if (/^\d+$/.test(line) || /^(NOTE|STYLE|REGION)\b/i.test(line)) continue;
    const cleaned = decodeHtmlEntities(line.replace(/<[^>]+>/g, "").trim());
    if (cleaned) lines.push(cleaned);
  }

  return finalizeCaptionLines(lines);
}

function finalizeCaptionLines(lines) {
  if (!Array.isArray(lines) || !lines.length) return "";

  const output = [];
  let prev = "";
  for (const raw of lines) {
    const line = String(raw || "").trim();
    if (!line || line === prev) continue;
    output.push(line);
    prev = line;
  }
  return output.join("\n").trim();
}

function decodeHtmlEntities(value) {
  return String(value || "")
    .replace(/&#x([0-9a-fA-F]+);/g, (_m, hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
    .replace(/&#([0-9]+);/g, (_m, dec) => String.fromCodePoint(Number.parseInt(dec, 10)))
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

async function fetchTranscriptViaTemporaryWatchTab(videoId, preferredLanguage) {
  const url =
    `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}` +
    "&hl=ko&autoplay=0&mute=1";

  const tab = await chrome.tabs.create({ url, active: false });
  const tabId = tab?.id;
  if (typeof tabId !== "number") {
    throw new Error("temporary watch tab create failed");
  }

  try {
    await chrome.tabs.update(tabId, { muted: true }).catch(() => {});
    await waitForTabComplete(tabId, 25000);
    return await fetchTranscriptViaSourceTab(tabId, preferredLanguage);
  } finally {
    await chrome.tabs.remove(tabId).catch(() => {});
  }
}

async function waitForTabComplete(tabId, timeoutMs = 20000) {
  const existing = await chrome.tabs.get(tabId).catch(() => null);
  if (!existing) {
    throw new Error("helper tab not found");
  }
  if (existing.status === "complete") {
    return;
  }

  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("helper tab loading timeout"));
    }, timeoutMs);

    function cleanup() {
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      chrome.tabs.onRemoved.removeListener(onRemoved);
    }

    function onUpdated(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === "complete") {
        cleanup();
        resolve();
      }
    }

    function onRemoved(removedTabId) {
      if (removedTabId === tabId) {
        cleanup();
        reject(new Error("helper tab removed"));
      }
    }

    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.onRemoved.addListener(onRemoved);
  });
}

async function tryInsertPromptToTab(tabId, prompt, options = {}) {
  if (typeof tabId !== "number" || !prompt) {
    return { inserted: false, submitted: false };
  }

  try {
    await waitForTabComplete(tabId, 25000);
  } catch {
    // ignore; many AI pages are interactive before full load completes
  }

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      args: [
        String(prompt),
        Boolean(options.autoSubmit),
        String(options.model || ""),
        Boolean(options.temporaryChat)
      ],
      func: async (text, autoSubmit, model, temporaryChat) => {
        const CHATGPT_MODEL_LABELS = {
          chatgpt: [],
          gpt5_2: ["GPT-5.2"],
          gpt5_2_instant: ["GPT-5.2 Instant"],
          gpt5_2_thinking: ["GPT-5.2 Thinking"],
          gpt5_1_instant: ["GPT-5.1 Instant"],
          gpt5_1_thinking: ["GPT-5.1 Thinking"],
          gpt4o: ["GPT-4o"]
        };

        function sleep(ms) {
          return new Promise((resolve) => setTimeout(resolve, ms));
        }

        function setTextareaValue(el, value) {
          const proto = Object.getPrototypeOf(el);
          const desc = Object.getOwnPropertyDescriptor(proto, "value");
          if (desc?.set) {
            desc.set.call(el, value);
          } else {
            el.value = value;
          }
          el.dispatchEvent(new InputEvent("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
        }

        function setEditableValue(el, value) {
          el.textContent = value;
          el.dispatchEvent(new InputEvent("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
        }

        function isVisible(el) {
          if (!el) return false;
          const rect = el.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        }

        function isDisabled(el) {
          return Boolean(el.disabled || el.getAttribute("aria-disabled") === "true");
        }

        function findPromptInput() {
          const selectors = [
            "textarea#prompt-textarea",
            "textarea[data-id]",
            "textarea[placeholder*='message' i]",
            "textarea[placeholder*='ask' i]",
            "rich-textarea div[contenteditable='true']",
            "div[contenteditable='true'][role='textbox']",
            "div[contenteditable='true'][data-lexical-editor='true']",
            "div.ProseMirror[contenteditable='true']",
            "div[contenteditable='true']",
            "textarea"
          ];

          for (const selector of selectors) {
            const el = document.querySelector(selector);
            if (!isVisible(el)) continue;
            return el;
          }
          return null;
        }

        function findSendButton() {
          const selectors = [
            "button[data-testid='send-button']",
            "button[data-testid*='send']",
            "button[aria-label*='Send' i]",
            "button[aria-label*='submit' i]",
            "button[aria-label*='send' i]",
            "button[type='submit']"
          ];
          for (const selector of selectors) {
            const button = document.querySelector(selector);
            if (!isVisible(button) || isDisabled(button)) continue;
            return button;
          }

          const byText = Array.from(document.querySelectorAll("button")).find((button) => {
            if (!isVisible(button) || isDisabled(button)) return false;
            const textValue = String(button.textContent || "").toLowerCase().trim();
            return textValue.includes("send") || textValue.includes("submit");
          });

          return byText || null;
        }

        function findTemporaryChatToggle() {
          const selectors = [
            "button[data-testid*='temporary']",
            "button[aria-label*='Temporary' i]",
            "button[aria-label*='임시']",
            "button[title*='Temporary' i]",
            "button[title*='임시']"
          ];
          for (const selector of selectors) {
            const button = document.querySelector(selector);
            if (!isVisible(button) || isDisabled(button)) continue;
            return button;
          }
          return null;
        }

        function normalizeText(value) {
          return String(value || "")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();
        }

        function isChatGptFamilyModel(value) {
          return Object.prototype.hasOwnProperty.call(CHATGPT_MODEL_LABELS, String(value || ""));
        }

        function findModelTrigger() {
          const selectors = [
            "button[data-testid*='model']",
            "button[aria-haspopup='menu']",
            "button[aria-haspopup='dialog']",
            "header button",
            "nav button"
          ];

          for (const selector of selectors) {
            const buttons = Array.from(document.querySelectorAll(selector));
            for (const button of buttons) {
              if (!isVisible(button) || isDisabled(button)) continue;
              const textValue = normalizeText(button.textContent || button.getAttribute("aria-label") || "");
              if (textValue.includes("gpt") || textValue.includes("model")) {
                return button;
              }
            }
          }

          return null;
        }

        function findModelOption(labels) {
          const normalizedLabels = labels.map((label) => normalizeText(label));
          const candidates = Array.from(
            document.querySelectorAll("[role='menuitem'], [role='option'], button, div")
          );

          for (const node of candidates) {
            if (!isVisible(node) || isDisabled(node)) continue;
            const textValue = normalizeText(node.textContent || node.getAttribute("aria-label") || "");
            if (!textValue) continue;
            if (normalizedLabels.some((label) => textValue.includes(label))) {
              return node;
            }
          }

          return null;
        }

        async function selectModelIfPossible() {
          if (!isChatGptFamilyModel(model)) {
            return false;
          }

          const labels = CHATGPT_MODEL_LABELS[model] || [];
          if (!labels.length) {
            return true;
          }

          const deadline = Date.now() + 8000;
          while (Date.now() < deadline) {
            const option = findModelOption(labels);
            if (option) {
              option.click();
              await sleep(350);
              return true;
            }

            const trigger = findModelTrigger();
            if (!trigger) {
              await sleep(250);
              continue;
            }

            trigger.click();
            await sleep(500);
          }

          return false;
        }

        async function enableTemporaryChatIfPossible() {
          if (!isChatGptFamilyModel(model) || !temporaryChat) {
            return false;
          }

          const deadline = Date.now() + 7000;
          while (Date.now() < deadline) {
            const toggle = findTemporaryChatToggle();
            if (!toggle) {
              await sleep(250);
              continue;
            }

            const pressed = toggle.getAttribute("aria-pressed");
            if (pressed === "true") {
              return true;
            }
            if (pressed === "false") {
              toggle.click();
              await sleep(400);
              if (toggle.getAttribute("aria-pressed") === "true") {
                return true;
              }
              continue;
            }

            // Unknown state (no aria-pressed): do not force-click to avoid accidental toggle-off.
            return false;
          }
          return false;
        }

        function triggerEnter(input) {
          input.dispatchEvent(
            new KeyboardEvent("keydown", {
              key: "Enter",
              code: "Enter",
              keyCode: 13,
              which: 13,
              bubbles: true
            })
          );
          input.dispatchEvent(
            new KeyboardEvent("keyup", {
              key: "Enter",
              code: "Enter",
              keyCode: 13,
              which: 13,
              bubbles: true
            })
          );
        }

        const deadline = Date.now() + 20000;
        while (Date.now() < deadline) {
          await selectModelIfPossible();
          await enableTemporaryChatIfPossible();

          const input = findPromptInput();
          if (!input) {
            await sleep(250);
            continue;
          }

          input.focus();
          if (input instanceof HTMLTextAreaElement || input instanceof HTMLInputElement) {
            setTextareaValue(input, text);
          } else {
            setEditableValue(input, text);
          }

          if (!autoSubmit) {
            return { inserted: true, submitted: false };
          }

          const sendDeadline = Date.now() + 6000;
          while (Date.now() < sendDeadline) {
            const sendButton = findSendButton();
            if (sendButton) {
              sendButton.click();
              return { inserted: true, submitted: true };
            }
            triggerEnter(input);
            await sleep(300);

            const retrySendButton = findSendButton();
            if (retrySendButton && (model === "chatgpt" || model === "claude" || model === "gemini")) {
              retrySendButton.click();
              return { inserted: true, submitted: true };
            }
          }

          return { inserted: true, submitted: false };
        }

        return { inserted: false, submitted: false };
      }
    });

    const payload = results?.[0]?.result;
    if (payload && typeof payload === "object") {
      return {
        inserted: Boolean(payload.inserted),
        submitted: Boolean(payload.submitted)
      };
    }
    return { inserted: false, submitted: false };
  } catch {
    return { inserted: false, submitted: false };
  }
}

async function fetchTranscriptViaSourceTab(tabId, preferredLanguage) {
  const tab = await chrome.tabs.get(tabId).catch(() => null);
  if (!tab) {
    throw new Error("source tab lookup failed");
  }
  if (!tab.url || !tab.url.includes("youtube.com/watch")) {
    throw new Error("source tab is not a youtube watch page");
  }

  const results = await chrome.scripting.executeScript({
    target: { tabId },
    world: "MAIN",
    args: [preferredLanguage || "", MOBILE_PLAYER_CLIENTS],
    func: async (preferredLang, mobileClients) => {
      function sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
      }

      async function waitForCondition(predicate, timeoutMs = 6000, intervalMs = 250) {
        const startedAt = Date.now();
        while (Date.now() - startedAt < timeoutMs) {
          try {
            const value = predicate();
            if (value) return value;
          } catch {
            // ignore
          }
          await sleep(intervalMs);
        }
        return null;
      }

      function decodeHtmlEntities(value) {
        return String(value || "")
          .replace(/&#x([0-9a-fA-F]+);/g, (_m, hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
          .replace(/&#([0-9]+);/g, (_m, dec) => String.fromCodePoint(Number.parseInt(dec, 10)))
          .replace(/&amp;/g, "&")
          .replace(/&lt;/g, "<")
          .replace(/&gt;/g, ">")
          .replace(/&quot;/g, "\"")
          .replace(/&#39;/g, "'")
          .replace(/&nbsp;/g, " ");
      }

      function finalize(lines) {
        if (!Array.isArray(lines) || !lines.length) return "";
        const deduped = [];
        let prev = "";
        for (const raw of lines) {
          const line = String(raw || "").trim();
          if (!line || line === prev) continue;
          deduped.push(line);
          prev = line;
        }
        return deduped.join("\n").trim();
      }

      function normalizeLang(value) {
        return String(value || "").toLowerCase().split("-")[0].trim();
      }

      function readTitle() {
        const h1 = document.querySelector("ytd-watch-metadata h1");
        const raw = (h1?.textContent || document.title || "").trim();
        return raw.replace(/\s*-\s*YouTube\s*$/i, "").trim();
      }

      function getPlayerResponse() {
        try {
          if (window.ytInitialPlayerResponse) return window.ytInitialPlayerResponse;
        } catch {
          // ignore
        }

        const scripts = Array.from(document.querySelectorAll("script"));
        for (const script of scripts) {
          const text = script.textContent || "";
          if (!text.includes("ytInitialPlayerResponse")) continue;

          const marker = text.includes("var ytInitialPlayerResponse =")
            ? "var ytInitialPlayerResponse ="
            : "ytInitialPlayerResponse =";
          const markerIndex = text.indexOf(marker);
          if (markerIndex < 0) continue;

          const start = text.indexOf("{", markerIndex + marker.length);
          if (start < 0) continue;

          let depth = 0;
          let inString = false;
          let escaped = false;

          for (let i = start; i < text.length; i += 1) {
            const ch = text[i];
            if (inString) {
              if (escaped) escaped = false;
              else if (ch === "\\") escaped = true;
              else if (ch === "\"") inString = false;
              continue;
            }
            if (ch === "\"") {
              inString = true;
              continue;
            }
            if (ch === "{") depth += 1;
            if (ch === "}") {
              depth -= 1;
              if (depth === 0) {
                try {
                  return JSON.parse(text.slice(start, i + 1));
                } catch {
                  break;
                }
              }
            }
          }
        }
        return null;
      }

      function trackName(track) {
        if (track?.name?.simpleText) return track.name.simpleText;
        if (Array.isArray(track?.name?.runs)) {
          return track.name.runs.map((item) => item?.text || "").join("").trim();
        }
        return track?.languageCode || "unknown";
      }

      function sortTracks(tracks, preferredLang) {
        const preferred = normalizeLang(preferredLang);
        const score = (track) => {
          const lang = normalizeLang(track?.languageCode);
          let v = 0;
          if (preferred && lang === preferred) v += 220;
          if (track?.kind !== "asr") v += 80;
          if (lang === "ko") v += 40;
          else if (lang === "en") v += 20;
          return v;
        };
        return [...(tracks || [])].sort((a, b) => score(b) - score(a));
      }

      function parseCaptionPayload(payload) {
        const text = String(payload || "");
        return parseJson(text) || parseXml(text) || parseVtt(text);
      }

      function parseJson(text) {
        const start = text.indexOf("{");
        if (start < 0) return "";
        try {
          const data = JSON.parse(text.slice(start));
          const events = Array.isArray(data?.events) ? data.events : [];
          const lines = [];
          for (const event of events) {
            if (!Array.isArray(event?.segs)) continue;
            const line = event.segs
              .map((seg) => seg?.utf8 || seg?.text || "")
              .join("")
              .replace(/\s+/g, " ")
              .trim();
            if (line) lines.push(decodeHtmlEntities(line));
          }
          return finalize(lines);
        } catch {
          return "";
        }
      }

      function parseXml(text) {
        if (!text.includes("<")) return "";
        const pattern = /<(text|p|w|s)\b[^>]*>([\s\S]*?)<\/\1>/gi;
        const lines = [];
        let match;
        while ((match = pattern.exec(text)) !== null) {
          const raw = decodeHtmlEntities(
            (match[2] || "")
              .replace(/<br\s*\/?>/gi, "\n")
              .replace(/<[^>]+>/g, "")
          );
          const line = raw
            .split("\n")
            .map((part) => part.replace(/\s+/g, " ").trim())
            .filter(Boolean)
            .join(" ");
          if (line) lines.push(line);
        }
        return finalize(lines);
      }

      function parseVtt(text) {
        if (!text.includes("WEBVTT")) return "";
        const lines = [];
        for (const rawLine of text.split(/\r?\n/)) {
          const line = rawLine.trim();
          if (!line || line === "WEBVTT" || line.includes("-->")) continue;
          if (/^\d+$/.test(line) || /^(NOTE|STYLE|REGION)\b/i.test(line)) continue;
          const cleaned = decodeHtmlEntities(line.replace(/<[^>]+>/g, "").trim());
          if (cleaned) lines.push(cleaned);
        }
        return finalize(lines);
      }

      async function fetchTextWithTimeout(url, timeoutMs = 4500) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        try {
          return await fetch(url, { credentials: "include", signal: controller.signal });
        } finally {
          clearTimeout(timer);
        }
      }

      async function tryTimedText() {
        const playerResponse = getPlayerResponse();
        const tracks = playerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
        if (!tracks.length) return { ok: false, error: "captionTracks not found" };

        const localErrors = [];
        for (const track of sortTracks(tracks, preferredLang).slice(0, 3)) {
          const base = String(track?.baseUrl || "").trim();
          if (!base) continue;

          const urls = [];
          const seen = new Set();
          const pushUrl = (value) => {
            if (!value || seen.has(value)) return;
            seen.add(value);
            urls.push(value);
          };

          pushUrl(base);
          for (const fmt of ["json3", "srv3", "vtt"]) {
            try {
              const next = new URL(base);
              next.searchParams.set("fmt", fmt);
              pushUrl(next.toString());
            } catch {
              // ignore
            }
          }

          // Fallback: rebuild minimal timedtext URLs without volatile signature params.
          try {
            const baseUrl = new URL(base);
            const videoId =
              baseUrl.searchParams.get("v") ||
              new URL(window.location.href).searchParams.get("v") ||
              "";
            const lang = track?.languageCode || baseUrl.searchParams.get("lang") || "";
            const kind = track?.kind || baseUrl.searchParams.get("kind") || "";
            const name = baseUrl.searchParams.get("name") || "";

            if (videoId && lang) {
              for (const endpoint of [
                "https://www.youtube.com/api/timedtext",
                "https://video.google.com/timedtext"
              ]) {
                const minimal = new URL(endpoint);
                minimal.searchParams.set("v", videoId);
                minimal.searchParams.set("lang", lang);
                if (kind) minimal.searchParams.set("kind", kind);
                if (name) minimal.searchParams.set("name", name);
                pushUrl(minimal.toString());

                for (const fmt of ["json3", "srv3", "vtt"]) {
                  const withFmt = new URL(minimal.toString());
                  withFmt.searchParams.set("fmt", fmt);
                  pushUrl(withFmt.toString());
                }
              }
            }
          } catch {
            // ignore URL parse errors
          }

          for (const url of urls) {
            try {
              const response = await fetchTextWithTimeout(url, 4500);
              if (!response.ok) {
                localErrors.push(`${trackName(track)} HTTP ${response.status}`);
                continue;
              }

              const payload = await response.text();
              const transcript = parseCaptionPayload(payload);
              if (transcript) {
                return {
                  ok: true,
                  data: {
                    title: readTitle(),
                    languageCode: normalizeLang(track.languageCode) || "unknown",
                    trackName: `timedtext-${trackName(track)}`,
                    transcript
                  }
                };
              }

              const contentType = (response.headers.get("content-type") || "").toLowerCase();
              if (contentType.includes("text/html")) {
                localErrors.push(`${trackName(track)} html-response`);
              } else {
                localErrors.push(`${trackName(track)} empty-parse [${contentType || "unknown"}]`);
              }
            } catch (error) {
              localErrors.push(error?.name === "AbortError" ? "timedtext timeout" : (error?.message || String(error)));
            }
          }
        }

        return { ok: false, error: `timedtext failed: ${localErrors.slice(0, 3).join(" | ")}` };
      }

      async function tryMobilePlayerCaptions() {
        const apiKey = String(getYtcfgValue("INNERTUBE_API_KEY") || "").trim();
        const videoId = new URL(window.location.href).searchParams.get("v") || "";
        if (!apiKey || !videoId) {
          return { ok: false, error: "mobile player config missing" };
        }

        const localErrors = [];
        try {
          for (const client of Array.isArray(mobileClients) ? mobileClients : []) {
            const response = await fetch(
              `https://www.youtube.com/youtubei/v1/player?key=${encodeURIComponent(apiKey)}&prettyPrint=false`,
              {
                method: "POST",
                credentials: "omit",
                headers: {
                  "content-type": "application/json",
                  "x-youtube-client-name": client.headerClientName,
                  "x-youtube-client-version": client.headerClientVersion
                },
                body: JSON.stringify({
                  videoId,
                  contentCheckOk: true,
                  racyCheckOk: true,
                  context: {
                    client: client.contextClient
                  }
                })
              }
            );

            if (!response.ok) {
              const sample = (await response.text()).slice(0, 140).replace(/\s+/g, " ").trim();
              localErrors.push(`${client.label} player HTTP ${response.status} ${sample}`);
              continue;
            }

            const json = await response.json();
            const tracks = json?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
            if (!tracks.length) {
              localErrors.push(`${client.label} captionTracks not found`);
              continue;
            }

            for (const track of sortTracks(tracks, preferredLang).slice(0, 4)) {
              const base = String(track?.baseUrl || "").trim();
              if (!base) continue;

              const urls = [];
              const seen = new Set();
              const pushUrl = (value) => {
                if (!value || seen.has(value)) return;
                seen.add(value);
                urls.push(value);
              };

              pushUrl(base);
              for (const fmt of ["json3", "srv3", "vtt"]) {
                try {
                  const next = new URL(base);
                  next.searchParams.set("fmt", fmt);
                  pushUrl(next.toString());
                } catch {
                  // ignore URL parse errors
                }
              }

              for (const url of urls) {
                try {
                  const res = await fetchTextWithTimeout(url, 4500);
                  if (!res.ok) {
                    localErrors.push(`${client.label} ${trackName(track)} HTTP ${res.status}`);
                    continue;
                  }
                  const payload = await res.text();
                  const transcript = parseCaptionPayload(payload);
                  if (transcript) {
                    return {
                      ok: true,
                      data: {
                        title: readTitle() || json?.videoDetails?.title || "",
                        languageCode: normalizeLang(track.languageCode) || "unknown",
                        trackName: `${client.label}-player-${trackName(track)}`,
                        transcript
                      }
                    };
                  }
                  const contentType = (res.headers.get("content-type") || "").toLowerCase();
                  localErrors.push(
                    `${client.label} ${trackName(track)} empty-parse [${contentType || "unknown"}]`
                  );
                } catch (error) {
                  localErrors.push(
                    error?.name === "AbortError"
                      ? `${client.label} timedtext timeout`
                      : `${client.label} ${error?.message || String(error)}`
                  );
                }
              }
            }
          }

          return { ok: false, error: `mobile player failed: ${localErrors.slice(0, 2).join(" | ")}` };
        } catch (error) {
          return { ok: false, error: error?.message || String(error) };
        }
      }

      function runsText(runs) {
        if (!Array.isArray(runs)) return "";
        return runs
          .map((item) => (typeof item?.text === "string" ? item.text : ""))
          .join("")
          .replace(/\s+/g, " ")
          .trim();
      }

      function anyText(node) {
        if (!node || typeof node !== "object") return "";
        if (typeof node.simpleText === "string") {
          return node.simpleText.replace(/\s+/g, " ").trim();
        }
        return runsText(node.runs);
      }

      function collectInnertubeLines(node, lines) {
        if (node == null) return;
        if (typeof node === "string" || typeof node === "number" || typeof node === "boolean") return;
        if (Array.isArray(node)) {
          for (const item of node) collectInnertubeLines(item, lines);
          return;
        }

        const segment = node.transcriptSegmentRenderer;
        if (segment) {
          const line = anyText(segment.snippet);
          if (line) lines.push(line);
        }

        const cue = node.transcriptCueRenderer || node.cueRenderer || node.cue;
        if (cue && typeof cue === "object") {
          const line = anyText(cue.cue) || anyText(cue.snippet) || anyText(cue);
          if (line) lines.push(line);
        }

        for (const value of Object.values(node)) {
          collectInnertubeLines(value, lines);
        }
      }

      function findGetTranscriptEndpoints(node) {
        const endpoints = [];
        const visited = new Set();

        function walk(current) {
          if (!current || typeof current !== "object") return;
          if (visited.has(current)) return;
          visited.add(current);

          const endpoint = current.getTranscriptEndpoint;
          if (endpoint && typeof endpoint === "object") {
            endpoints.push(endpoint);
          }

          for (const value of Object.values(current)) {
            walk(value);
          }
        }

        walk(node);
        return endpoints;
      }

      function findGetTranscriptParams(node) {
        const params = [];
        const visited = new Set();

        function walk(current) {
          if (!current || typeof current !== "object") return;
          if (visited.has(current)) return;
          visited.add(current);

          const endpoint = current.getTranscriptEndpoint;
          if (endpoint && typeof endpoint === "object") {
            if (typeof endpoint.params === "string" && endpoint.params) {
              params.push(endpoint.params);
            }
          }

          for (const value of Object.values(current)) {
            walk(value);
          }
        }

        walk(node);
        return params;
      }

      function getYtcfgValue(key) {
        try {
          if (window.ytcfg?.get) {
            const value = window.ytcfg.get(key);
            if (value !== undefined) return value;
          }
        } catch {
          // ignore
        }
        try {
          if (window.ytcfg?.data_ && key in window.ytcfg.data_) {
            return window.ytcfg.data_[key];
          }
        } catch {
          // ignore
        }
        return undefined;
      }

      async function tryInnertubeTranscript() {
        const apiKey = String(getYtcfgValue("INNERTUBE_API_KEY") || "").trim();
        const context = getYtcfgValue("INNERTUBE_CONTEXT");
        const videoId = new URL(window.location.href).searchParams.get("v") || "";

        if (!apiKey || !context || !videoId) {
          return { ok: false, error: "innertube config missing" };
        }

        const clientName = getYtcfgValue("INNERTUBE_CLIENT_NAME");
        const clientVersion = getYtcfgValue("INNERTUBE_CLIENT_VERSION");
        const visitorData = String(getYtcfgValue("VISITOR_DATA") || "").trim();

        const headers = { "content-type": "application/json" };
        if (clientName != null) headers["x-youtube-client-name"] = String(clientName);
        if (clientVersion != null) headers["x-youtube-client-version"] = String(clientVersion);
        if (visitorData) headers["x-goog-visitor-id"] = visitorData;
        headers["x-origin"] = window.location.origin;
        const loggedIn = getYtcfgValue("LOGGED_IN");
        if (loggedIn != null) {
          headers["x-youtube-bootstrap-logged-in"] = String(Boolean(loggedIn));
        }
        const sessionIndex = getYtcfgValue("SESSION_INDEX");
        if (sessionIndex != null && String(sessionIndex).trim()) {
          headers["x-goog-authuser"] = String(sessionIndex).trim();
        }

        async function postInnertube(path, body) {
          const response = await fetch(
            `https://www.youtube.com/youtubei/v1/${path}?key=${encodeURIComponent(apiKey)}`,
            {
              method: "POST",
              credentials: "include",
              headers,
              body: JSON.stringify(body)
            }
          );
          if (!response.ok) {
            const sample = (await response.text()).slice(0, 140).replace(/\s+/g, " ").trim();
            throw new Error(`innertube ${path} HTTP ${response.status} ${sample}`);
          }
          return response.json();
        }

        function buildBodyFromEndpoint(endpoint) {
          const body = { context };
          for (const [key, value] of Object.entries(endpoint || {})) {
            if (key === "commandMetadata" || key === "clickTrackingParams") continue;
            body[key] = value;
          }
          if (endpoint?.clickTrackingParams) {
            body.context = {
              ...context,
              clickTracking: { clickTrackingParams: endpoint.clickTrackingParams }
            };
          }
          return body;
        }

        function normalizeEndpointKey(endpoint) {
          try {
            return JSON.stringify(endpoint);
          } catch {
            return String(Math.random());
          }
        }

        function collectTranscriptFromJson(transcriptJson) {
          const lines = [];
          collectInnertubeLines(transcriptJson, lines);
          return finalize(
            lines
              .map((line) => decodeHtmlEntities(line).replace(/\s+/g, " ").trim())
              .filter(Boolean)
          );
        }

        const localErrors = [];
        const endpointMap = new Map();
        const paramsSet = new Set();

        function addCandidatesFrom(node) {
          if (!node) return;
          const endpoints = findGetTranscriptEndpoints(node);
          for (const endpoint of endpoints) {
            endpointMap.set(normalizeEndpointKey(endpoint), endpoint);
          }
          const params = findGetTranscriptParams(node);
          for (const p of params) {
            if (typeof p === "string" && p) paramsSet.add(p);
          }
        }

        // Directly use transcript endpoints already present in initial page data.
        addCandidatesFrom(window.ytInitialData);
        addCandidatesFrom(window.__INITIAL_DATA__);
        addCandidatesFrom(getPlayerResponse());

        const tryEndpoint = async (endpoint) => {
          const apiUrl =
            endpoint?.commandMetadata?.webCommandMetadata?.apiUrl ||
            "/youtubei/v1/get_transcript";
          const path = String(apiUrl).replace(/^\/youtubei\/v1\//, "");
          const transcriptJson = await postInnertube(path, buildBodyFromEndpoint(endpoint));
          const transcript = collectTranscriptFromJson(transcriptJson);
          if (!transcript) {
            throw new Error(`endpoint empty lines (${path})`);
          }
          return {
            ok: true,
            data: {
              title: readTitle(),
              languageCode: normalizeLang(preferredLang) || "unknown",
              trackName: "innertube-endpoint",
              transcript
            }
          };
        };

        const tryParams = async (params) => {
          const transcriptJson = await postInnertube("get_transcript", {
            context,
            params
          });
          const transcript = collectTranscriptFromJson(transcriptJson);
          if (!transcript) {
            throw new Error("params empty lines");
          }
          return {
            ok: true,
            data: {
              title: readTitle(),
              languageCode: normalizeLang(preferredLang) || "unknown",
              trackName: "innertube-params",
              transcript
            }
          };
        };

        try {
          // 1) Try endpoints discovered directly from initial page data.
          for (const endpoint of Array.from(endpointMap.values()).slice(0, 8)) {
            try {
              return await tryEndpoint(endpoint);
            } catch (error) {
              localErrors.push(error?.message || String(error));
            }
          }

          // 2) Try params discovered from initial page data.
          for (const params of Array.from(paramsSet).slice(0, 6)) {
            try {
              return await tryParams(params);
            } catch (error) {
              localErrors.push(error?.message || String(error));
            }
          }

          // 3) Fallback to next -> endpoint/params.
          const nextJson = await postInnertube("next", { context, videoId });
          addCandidatesFrom(nextJson);

          for (const endpoint of Array.from(endpointMap.values()).slice(0, 10)) {
            try {
              return await tryEndpoint(endpoint);
            } catch (error) {
              localErrors.push(error?.message || String(error));
            }
          }

          for (const params of Array.from(paramsSet).slice(0, 8)) {
            try {
              return await tryParams(params);
            } catch (error) {
              localErrors.push(error?.message || String(error));
            }
          }

          return { ok: false, error: `innertube failed: ${localErrors.slice(0, 2).join(" | ")}` };
        } catch (error) {
          return { ok: false, error: error?.message || String(error) };
        }
      }

      async function tryTextTracks() {
        const video = await waitForCondition(() => document.querySelector("video"), 5000, 250);
        if (!video) return { ok: false, error: "video element not found" };

        const tracks = await waitForCondition(() => {
          const current = Array.from(video.textTracks || []);
          return current.length ? current : null;
        }, 4500, 250);

        if (!tracks?.length) return { ok: false, error: "video.textTracks empty" };

        const preferred = normalizeLang(preferredLang);
        const sorted = [...tracks].sort((a, b) => {
          const score = (track) => {
            const lang = normalizeLang(track?.language);
            let v = 0;
            if (preferred && lang === preferred) v += 220;
            if (lang === "ko") v += 80;
            else if (lang === "en") v += 40;
            return v;
          };
          return score(b) - score(a);
        });

        for (const track of sorted) {
          try {
            track.mode = "hidden";
            await waitForCondition(() => track.cues && track.cues.length > 0, 3500, 200);

            const lines = Array.from(track.cues || [])
              .map((cue) => decodeHtmlEntities(String(cue?.text || "").replace(/\n/g, " ").trim()))
              .map((line) => line.replace(/\s+/g, " ").trim())
              .filter(Boolean);

            const transcript = finalize(lines);
            if (transcript) {
              return {
                ok: true,
                data: {
                  title: readTitle(),
                  languageCode: normalizeLang(track.language) || "unknown",
                  trackName: track.label || track.language || "textTrack",
                  transcript
                }
              };
            }
          } catch {
            // ignore and try next track
          }
        }

        return { ok: false, error: "textTracks transcript not found" };
      }

      function isVisible(el) {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      }

      function normalizeDomLine(raw) {
        const line = decodeHtmlEntities(String(raw || "")).replace(/\s+/g, " ").trim();
        if (!line) return "";
        return line.replace(/^\d{1,2}:\d{2}(?::\d{2})?\s+/, "").trim();
      }

      function collectDomLines() {
        const lines = [];
        const seen = new Set();
        const pushLine = (raw) => {
          const line = normalizeDomLine(raw);
          if (!line || seen.has(line)) return;
          seen.add(line);
          lines.push(line);
        };

        const renderers = Array.from(document.querySelectorAll("ytd-transcript-segment-renderer"));
        for (const renderer of renderers) {
          const textNode =
            renderer.querySelector(".segment-text") ||
            renderer.querySelector("[class*='segment-text']") ||
            renderer.querySelector("yt-formatted-string");
          pushLine(textNode?.textContent || renderer.textContent || "");
        }

        // Modern watch pages now render transcript rows as transcript-segment-view-model
        // instead of ytd-transcript-segment-renderer.
        const modernSegments = Array.from(
          document.querySelectorAll("transcript-segment-view-model, .ytwTranscriptSegmentViewModelHost")
        );
        for (const segment of modernSegments) {
          const textNodes = Array.from(
            segment.querySelectorAll(
              [
                "[role='text']",
                ".yt-core-attributed-string",
                "yt-formatted-string"
              ].join(",")
            )
          )
            .map((node) => node.textContent || "")
            .map((text) => text.replace(/\s+/g, " ").trim())
            .filter(Boolean);

          if (textNodes.length) {
            pushLine(textNodes.join(" "));
            continue;
          }

          pushLine(segment.textContent || "");
        }

        const fallback = Array.from(
          document.querySelectorAll(
            [
              "[target-id*='engagement-panel-searchable-transcript'] .segment-text",
              "[target-id*='engagement-panel-searchable-transcript'] [class*='segment-text']",
              "[target-id*='engagement-panel-searchable-transcript'] .ytwTranscriptSegmentViewModelHost .yt-core-attributed-string",
              "[target-id*='engagement-panel-searchable-transcript'] .ytwTranscriptSegmentViewModelHost [role='text']",
              "ytd-transcript-renderer .segment-text",
              "ytd-transcript-search-panel-renderer .segment-text",
              "transcript-search-panel-renderer .ytwTranscriptSegmentViewModelHost .yt-core-attributed-string",
              "transcript-search-panel-renderer .ytwTranscriptSegmentViewModelHost [role='text']"
            ].join(",")
          )
        );
        for (const node of fallback) {
          pushLine(node.textContent || "");
        }

        return lines;
      }
      async function openTranscriptPanel() {
        const keywords = [
          "show transcript",
          "transcript",
          "open transcript",
          "\uC2A4\uD06C\uB9BD\uD2B8",
          "\uB300\uBCF8"
        ].map((value) => value.toLowerCase());

        function matchesTranscriptText(node) {
          const text = String(
            node?.textContent ||
              node?.getAttribute?.("aria-label") ||
              node?.getAttribute?.("title") ||
              ""
          )
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();
          return Boolean(text && keywords.some((keyword) => text.includes(keyword)));
        }

        function collectTranscriptCandidates() {
          return Array.from(
            document.querySelectorAll(
              [
                "button",
                "[role='button']",
                "[role='menuitem']",
                "tp-yt-paper-item",
                "ytd-menu-service-item-renderer",
                "yt-chip-cloud-chip-renderer",
                "yt-formatted-string"
              ].join(",")
            )
          ).filter((node) => isVisible(node) && matchesTranscriptText(node));
        }

        async function clickTranscriptCandidate() {
          const candidates = collectTranscriptCandidates();
          for (const node of candidates) {
            const clickable = node.closest(
              "button, [role='button'], [role='menuitem'], tp-yt-paper-item, ytd-menu-service-item-renderer"
            ) || node;
            clickable.click();
            await sleep(350);
            return true;
          }
          return false;
        }

        const expandSelectors = [
          "tp-yt-paper-button#expand",
          "button[aria-label*='more' i]",
          "button[aria-label*='\uB354\uBCF4\uAE30']",
          "ytd-text-inline-expander #expand",
          "ytd-expandable-video-description-body-renderer #expand"
        ];

        for (const selector of expandSelectors) {
          const button = document.querySelector(selector);
          if (button && isVisible(button)) {
            button.click();
            await sleep(250);
          }
        }

        const directSelectors = [
          "button[aria-label*='Show transcript' i]",
          "button[aria-label*='transcript' i]",
          "button[aria-label*='\uC2A4\uD06C\uB9BD\uD2B8']",
          "button[aria-label*='\uB300\uBCF8']",
          "ytd-video-description-transcript-section-renderer button"
        ];

        for (const selector of directSelectors) {
          const button = document.querySelector(selector);
          if (button && isVisible(button)) {
            button.click();
            await sleep(300);
            return true;
          }
        }

        if (await clickTranscriptCandidate()) {
          return true;
        }

        const menuButtons = Array.from(
          document.querySelectorAll(
            [
              "ytd-watch-metadata button[aria-label*='More actions' i]",
              "ytd-watch-metadata button[aria-label*='\uC791\uC5C5 \uB354\uBCF4\uAE30']",
              "ytd-watch-metadata button[aria-label*='\uB354\uBCF4\uAE30']",
              "ytd-watch-metadata ytd-menu-renderer yt-icon-button button"
            ].join(",")
          )
        ).filter(isVisible);

        if (menuButtons[0]) {
          menuButtons[0].click();
          await sleep(350);
        }

        return clickTranscriptCandidate();
      }

      async function tryDomTranscriptPanel() {
        const existing = finalize(collectDomLines());
        if (existing) {
          return {
            ok: true,
            data: {
              title: readTitle(),
              languageCode: normalizeLang(preferredLang) || "unknown",
              trackName: "dom-transcript-panel",
              transcript: existing
            }
          };
        }

        const opened = await openTranscriptPanel();
        if (!opened) return { ok: false, error: "transcript panel button not found" };

        const lines = await waitForCondition(() => {
          const next = collectDomLines();
          return next.length ? next : null;
        }, 8000, 250);

        const transcript = finalize(lines || []);
        if (!transcript) return { ok: false, error: "transcript panel dom empty" };

        return {
          ok: true,
          data: {
            title: readTitle(),
            languageCode: normalizeLang(preferredLang) || "unknown",
            trackName: "dom-transcript-panel",
            transcript
          }
        };
      }

      try {
        const errors = [];

        const byDom = await tryDomTranscriptPanel();
        if (byDom?.ok && byDom?.data?.transcript) return { ok: true, data: byDom.data };
        errors.push(byDom?.error || "dom transcript failed");

        const byTextTracks = await tryTextTracks();
        if (byTextTracks?.ok && byTextTracks?.data?.transcript) return { ok: true, data: byTextTracks.data };
        errors.push(byTextTracks?.error || "textTracks transcript failed");

        const byMobilePlayer = await tryMobilePlayerCaptions();
        if (byMobilePlayer?.ok && byMobilePlayer?.data?.transcript) return { ok: true, data: byMobilePlayer.data };
        errors.push(byMobilePlayer?.error || "mobile player captions failed");

        const byInnertube = await tryInnertubeTranscript();
        if (byInnertube?.ok && byInnertube?.data?.transcript) return { ok: true, data: byInnertube.data };
        errors.push(byInnertube?.error || "innertube failed");

        const byTimedText = await tryTimedText();
        if (byTimedText?.ok && byTimedText?.data?.transcript) return { ok: true, data: byTimedText.data };
        errors.push(byTimedText?.error || "timedtext failed");

        return { ok: false, error: `source tab extract failed: ${errors.slice(0, 4).join(" | ")}` };
      } catch (error) {
        return { ok: false, error: error?.message || String(error) };
      }
    }
  });

  const payload = results?.[0]?.result;
  if (!payload?.ok || !payload?.data?.transcript) {
    throw new Error(payload?.error || "source tab result empty");
  }

  return payload.data;
}
function buildPromptFromTemplate(transcriptData, templateText) {
  const template = normalizePromptTemplate(templateText, DEFAULT_SUMMARY_TEMPLATE);
  let prompt = template
    .split("{{TITLE}}")
    .join(transcriptData.title || "")
    .split("{{URL}}")
    .join(transcriptData.videoUrl || "")
    .split("{{TEXT}}")
    .join(transcriptData.transcript || "");

  if (!prompt.includes(transcriptData.transcript || "")) {
    prompt = (prompt + "\n\nTranscript:\n" + (transcriptData.transcript || "")).trim();
  }

  return prompt.trim();
}

function reflowTranscriptForReading(rawText) {
  const text = String(rawText || "").replace(/\r/g, "").trim();
  if (!text) {
    return "";
  }

  const lines = text.split("\n");
  const output = [];
  let blockLines = [];
  const timestampOnlyRegex = /^\d{1,2}:\d{2}(?::\d{2})?$/;
  const dividerRegex = /^[-=]{3,}$/;

  const flushBlock = () => {
    const normalizedLines = blockLines
      .map((entry) => String(entry || "").replace(/\s+/g, " ").trim())
      .filter(Boolean);

    if (!normalizedLines.length) {
      blockLines = [];
      return;
    }

    const semanticBlocks = splitCaptionLinesIntoSemanticBlocks(normalizedLines);
    for (const semanticBlock of semanticBlocks) {
      const blockText = semanticBlock.join(" ").replace(/\s+/g, " ").trim();
      if (!blockText) continue;
      output.push(...splitIntoReadableParagraphs(blockText));
    }

    blockLines = [];
  };

  for (const rawLine of lines) {
    const line = String(rawLine || "").replace(/\s+/g, " ").trim();
    if (!line) {
      flushBlock();
      continue;
    }

    if (timestampOnlyRegex.test(line) || dividerRegex.test(line)) {
      flushBlock();
      output.push(line);
      continue;
    }

    blockLines.push(line);
  }

  flushBlock();
  return output.join("\n").trim();
}

function splitCaptionLinesIntoSemanticBlocks(lines) {
  if (!Array.isArray(lines) || !lines.length) {
    return [];
  }

  const blocks = [];
  let current = [];
  let currentChars = 0;

  const flush = () => {
    if (!current.length) return;
    blocks.push([...current]);
    current = [];
    currentChars = 0;
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = String(lines[index] || "").trim();
    if (!line) continue;

    current.push(line);
    currentChars += line.length + 1;

    const nextLine = String(lines[index + 1] || "").trim();
    if (shouldBreakCaptionBlock(current, currentChars, nextLine)) {
      flush();
    }
  }

  flush();
  return blocks;
}

function splitIntoReadableParagraphs(blockText) {
  const sentences = splitIntoSentences(blockText);
  if (!sentences.length) {
    return [];
  }

  const paragraphs = [];
  let current = [];
  let currentChars = 0;

  const flush = () => {
    if (!current.length) return;
    paragraphs.push(current.join(" ").trim());
    current = [];
    currentChars = 0;
  };

  for (let index = 0; index < sentences.length; index += 1) {
    const sentence = sentences[index];
    current.push(sentence);
    currentChars += sentence.length + 1;

    if (current.length >= PARAGRAPH_MAX_SENTENCES) {
      flush();
      continue;
    }

    const nextSentence = sentences[index + 1] || "";
    if (shouldFlushParagraph(current, currentChars, nextSentence)) {
      flush();
    }
  }

  flush();
  return paragraphs.filter(Boolean);
}

function splitIntoSentences(blockText) {
  const words = String(blockText || "")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean);

  const sentences = [];
  let current = "";

  for (const word of words) {
    const merged = current ? `${current} ${word}` : word;
    const byBoundary = isLikelySentenceBoundary(word) && merged.length >= 18;
    const byLength = merged.length >= SENTENCE_HARD_MAX;

    if (byBoundary || byLength) {
      sentences.push(ensureSentencePunctuation(merged, true));
      current = "";
      continue;
    }

    current = merged;
  }

  if (current) {
    sentences.push(ensureSentencePunctuation(current, current.length >= 18));
  }

  return sentences.filter(Boolean);
}

function shouldFlushParagraph(currentSentences, currentChars, nextSentence) {
  if (!Array.isArray(currentSentences) || !currentSentences.length) {
    return false;
  }

  if (currentSentences.length >= PARAGRAPH_MIN_SENTENCES && currentChars >= PARAGRAPH_HARD_MAX) {
    return true;
  }

  const lastSentence = String(currentSentences[currentSentences.length - 1] || "").trim();
  const normalizedNext = String(nextSentence || "").trim();
  if (!lastSentence || !normalizedNext) {
    return false;
  }

  if (currentSentences.length >= PARAGRAPH_MIN_SENTENCES && looksLikeTopicShift(lastSentence, normalizedNext)) {
    return true;
  }

  if (currentSentences.length >= PARAGRAPH_MIN_SENTENCES && hasMeaningfulTopicBreak(currentSentences, normalizedNext)) {
    return true;
  }

  if (currentSentences.length >= PARAGRAPH_MIN_SENTENCES && endsWithQuestionOrPrompt(lastSentence)) {
    return true;
  }

  return false;
}

function shouldBreakCaptionBlock(currentLines, currentChars, nextLine) {
  if (!Array.isArray(currentLines) || !currentLines.length) {
    return false;
  }

  if (!nextLine) {
    return true;
  }

  if (currentChars >= PARAGRAPH_HARD_MAX) {
    return true;
  }

  const lastLine = String(currentLines[currentLines.length - 1] || "").trim();
  const normalizedNext = String(nextLine || "").trim();
  if (!lastLine || !normalizedNext) {
    return false;
  }

  if (currentLines.length >= 2 && endsWithQuestionOrPrompt(lastLine) && !endsWithQuestionOrPrompt(normalizedNext)) {
    return true;
  }

  if (currentLines.length >= 3 && looksLikeTopicShift(lastLine, normalizedNext)) {
    return true;
  }

  if (currentLines.length >= 3 && hasMeaningfulTopicBreak(currentLines, normalizedNext)) {
    return true;
  }

  if (currentLines.length >= 3 && startsWithSemanticShiftCue(normalizedNext) && endsWithStrongBoundary(lastLine)) {
    return true;
  }

  if (currentLines.length >= 4 && endsWithStrongBoundary(lastLine)) {
    return true;
  }

  return false;
}

function looksLikeTopicShift(lastSentence, nextSentence) {
  const next = String(nextSentence || "").toLowerCase().trim();
  if (!next) return false;

  const starters = [
    "but ",
    "however",
    "now ",
    "now,",
    "so ",
    "so,",
    "then ",
    "then,",
    "meanwhile",
    "anyway",
    "in conclusion",
    "for example",
    "for instance",
    "on the other hand",
    "that said",
    "first,",
    "second,",
    "third,",
    "finally",
    "결론적으로",
    "그런데",
    "하지만",
    "반면에",
    "즉",
    "다시 말해",
    "예를 들어",
    "그리고",
    "그래서",
    "그러면",
    "한편",
    "마지막으로",
    "첫째",
    "둘째",
    "셋째"
  ];

  if (starters.some((starter) => next.startsWith(starter))) {
    return true;
  }

  const prev = String(lastSentence || "").toLowerCase().trim();
  if (!prev) return false;

  if (endsWithQuestionOrPrompt(prev) && !endsWithQuestionOrPrompt(next)) {
    return true;
  }

  return false;
}

function hasMeaningfulTopicBreak(currentSentences, nextSentence) {
  const previousWindow = currentSentences.slice(-2).join(" ").trim();
  const previousTokens = collectMeaningTokens(previousWindow);
  const nextTokens = collectMeaningTokens(nextSentence);

  if (!previousTokens.length || !nextTokens.length) {
    return false;
  }

  const previousSet = new Set(previousTokens);
  const overlap = nextTokens.filter((token) => previousSet.has(token)).length;
  const overlapRatio = overlap / Math.max(nextTokens.length, 1);

  if (overlapRatio >= 0.34) {
    return false;
  }

  return startsWithSemanticShiftCue(nextSentence);
}

function endsWithStrongBoundary(text) {
  const value = String(text || "").trim();
  if (!value) return false;
  return /[.!?]["')\]]*$/.test(value) || /(?:니다|어요|했다|했다고|했다는|였다|입니다|죠|거든요|거예요)[”"')\]]*$/.test(value);
}

function collectMeaningTokens(text) {
  const stopWords = new Set([
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "so",
    "then",
    "now",
    "that",
    "this",
    "with",
    "from",
    "into",
    "about",
    "because",
    "have",
    "has",
    "had",
    "you",
    "your",
    "they",
    "them",
    "their",
    "there",
    "here",
    "what",
    "when",
    "where",
    "which",
    "while",
    "will",
    "would",
    "could",
    "should",
    "just",
    "really",
    "very",
    "more",
    "most",
    "also",
    "like",
    "yeah",
    "okay",
    "right",
    "것",
    "수",
    "때문",
    "정도",
    "경우",
    "부분",
    "다음",
    "지금",
    "여기",
    "저기",
    "우리",
    "여러분",
    "이제",
    "그리고",
    "그런데",
    "하지만",
    "그래서",
    "그러면",
    "또한",
    "정말",
    "진짜",
    "약간",
    "그냥",
    "바로",
    "이런",
    "저런",
    "그런",
    "대한",
    "통해",
    "관련",
    "있습니다",
    "합니다",
    "됩니다",
    "하는",
    "해서",
    "하게",
    "하면"
  ]);

  const tokens = String(text || "")
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[^0-9a-zA-Z\u3131-\u318E\uAC00-\uD7A3\s-]/g, " ")
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2 && !stopWords.has(token));

  return tokens.slice(0, 16);
}

function startsWithSemanticShiftCue(text) {
  const value = String(text || "").toLowerCase().trim();
  if (!value) return false;

  const cues = [
    "for example",
    "for instance",
    "on the other hand",
    "in contrast",
    "in conclusion",
    "to sum up",
    "more importantly",
    "the point is",
    "the problem is",
    "another thing",
    "let me explain",
    "let's move",
    "next,",
    "finally,",
    "first,",
    "second,",
    "third,",
    "예를 들어",
    "반대로",
    "반면에",
    "결론적으로",
    "정리하면",
    "요약하면",
    "핵심은",
    "문제는",
    "다음으로",
    "첫째",
    "둘째",
    "셋째",
    "마지막으로",
    "한편"
  ];

  return cues.some((cue) => value.startsWith(cue));
}

function endsWithQuestionOrPrompt(text) {
  const value = String(text || "").trim();
  if (!value) return false;
  if (/[?？]$/.test(value)) return true;

  const endings = [
    "까요.",
    "까요?",
    "일까요.",
    "일까요?",
    "인가요.",
    "인가요?",
    "겠죠.",
    "보세요.",
    "생각해보세요.",
    "remember.",
    "think about it.",
    "look at this.",
    "let's see."
  ];

  return endings.some((ending) => value.toLowerCase().endsWith(ending.toLowerCase()));
}

function isLikelySentenceBoundary(token) {
  const normalized = String(token || "")
    .trim()
    .replace(/^[("'[\s]+/, "")
    .replace(/[)"']\s]+$/, "");

  if (!normalized) return false;
  if (/[.!?????]$/.test(normalized)) return true;
  if (normalized.length < 2) return false;

  const endings = [
    "\uC2B5\uB2C8\uB2E4",
    "\uB2C8\uB2E4",
    "\uC600\uB2E4",
    "\uD588\uB2E4",
    "\uD55C\uB2E4",
    "\uD574\uC694",
    "\uD588\uC5B4\uC694",
    "\uC608\uC694",
    "\uC774\uC5D0\uC694",
    "\uAD70\uC694",
    "\uB124\uC694",
    "\uC8E0",
    "\uC9C0\uC694",
    "\uAE4C\uC694",
    "\uC77C\uAE4C\uC694",
    "\uB2E4",
    "\uC694"
  ];

  return endings.some((ending) => normalized.endsWith(ending));
}

function ensureSentencePunctuation(text, forcePeriod) {
  const value = String(text || "").trim();
  if (!value) return "";
  if (/[.!?????]$/.test(value)) return value;
  return forcePeriod ? `${value}.` : value;
}

async function copyTranscriptToClipboard(tabId, transcript) {
  const text = String(transcript || "").trim();
  if (!text) {
    throw new Error("clipboard copy failed: empty transcript");
  }

  const copied = await copyTextToClipboard(tabId, text);
  if (!copied) {
    throw new Error("clipboard copy failed");
  }
}

async function copyTextToClipboard(tabId, text) {
  const value = String(text || "").trim();
  if (!value) {
    return false;
  }

  if (typeof tabId === "number") {
    const copiedInPage = await tryCopyInPage(tabId, value);
    if (copiedInPage) {
      return true;
    }
  }

  const copiedViaHelperTab = await tryCopyViaHelperTab(value);
  if (copiedViaHelperTab) {
    return true;
  }

  const copiedOffscreen = await tryCopyViaOffscreen(value);
  if (copiedOffscreen) {
    return true;
  }

  return false;
}

async function tryCopyViaHelperTab(text) {
  let helperTabId = null;
  try {
    const helper = await chrome.tabs.create({
      url: chrome.runtime.getURL("copy_helper.html"),
      active: false
    });
    helperTabId = helper?.id;
    if (typeof helperTabId !== "number") {
      return false;
    }

    await waitForTabComplete(helperTabId, 10000);

    const results = await chrome.scripting.executeScript({
      target: { tabId: helperTabId },
      args: [text],
      func: async (value) => {
        try {
          await navigator.clipboard.writeText(value);
          return true;
        } catch {
          // fallback below
        }

        try {
          const textarea = document.createElement("textarea");
          textarea.value = value;
          textarea.setAttribute("readonly", "true");
          textarea.style.position = "fixed";
          textarea.style.opacity = "0";
          textarea.style.left = "-9999px";
          document.body.appendChild(textarea);
          textarea.focus();
          textarea.select();
          const ok = document.execCommand("copy");
          textarea.remove();
          return Boolean(ok);
        } catch {
          return false;
        }
      }
    });

    return Boolean(results?.[0]?.result);
  } catch {
    return false;
  } finally {
    if (typeof helperTabId === "number") {
      await chrome.tabs.remove(helperTabId).catch(() => {});
    }
  }
}

async function tryCopyInPage(tabId, text) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      args: [text],
      func: async (value) => {
        try {
          await navigator.clipboard.writeText(value);
          return true;
        } catch {
          // fallback below
        }

        try {
          const textarea = document.createElement("textarea");
          textarea.value = value;
          textarea.setAttribute("readonly", "true");
          textarea.style.position = "fixed";
          textarea.style.opacity = "0";
          textarea.style.left = "-9999px";
          document.body.appendChild(textarea);
          textarea.focus();
          textarea.select();
          const ok = document.execCommand("copy");
          textarea.remove();
          return Boolean(ok);
        } catch {
          return false;
        }
      }
    });
    return Boolean(results?.[0]?.result);
  } catch {
    return false;
  }
}

async function tryCopyViaOffscreen(text) {
  try {
    await ensureOffscreenClipboardDocument();
    const response = await chrome.runtime.sendMessage({
      type: "offscreen-copy",
      text
    });
    return Boolean(response?.ok);
  } catch {
    return false;
  }
}

async function ensureOffscreenClipboardDocument() {
  if (!chrome.offscreen?.createDocument || !chrome.runtime?.getContexts) {
    throw new Error("offscreen api unavailable");
  }

  const offscreenUrl = chrome.runtime.getURL("offscreen.html");
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
    documentUrls: [offscreenUrl]
  });

  if (Array.isArray(contexts) && contexts.length > 0) {
    return;
  }

  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["CLIPBOARD"],
    justification: "Copy transcript text to clipboard reliably."
  });
}

async function closeOffscreenClipboardDocument() {
  if (!chrome.offscreen?.closeDocument) {
    return;
  }
  try {
    await chrome.offscreen.closeDocument();
  } catch {
    // ignore close failure
  }
}

chrome.runtime.onSuspend?.addListener(() => {
  closeOffscreenClipboardDocument();
});

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createRetryableError(message) {
  const error = new Error(message);
  error.retryable = true;
  return error;
}

function isRetryableHttpStatus(status) {
  return status === 408 || status === 425 || status === 429 || status >= 500;
}

function isRetryableOperationError(error) {
  if (!error) return false;
  if (error.name === "AbortError") return true;
  if (Boolean(error.retryable)) return true;
  return error instanceof TypeError;
}

async function fetchWithTimeout(url, init = {}, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }
}

async function retryOperation(task, options = {}) {
  const attempts = Math.max(1, Number(options.attempts) || FETCH_RETRY_ATTEMPTS);
  const delayMs = Math.max(0, Number(options.delayMs) || FETCH_RETRY_DELAY_MS);
  const shouldRetry =
    typeof options.shouldRetry === "function"
      ? options.shouldRetry
      : isRetryableOperationError;
  let lastError = null;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await task(attempt);
    } catch (error) {
      lastError = error?.name === "AbortError" ? createRetryableError("request timeout") : error;
      if (attempt >= attempts || !shouldRetry(lastError, attempt)) {
        throw lastError;
      }
      await sleep(delayMs);
    }
  }

  throw lastError || new Error("retry operation failed");
}

chrome.runtime.onStartup?.addListener(() => {
  closeOffscreenClipboardDocument();
});

chrome.runtime.onInstalled?.addListener(() => {
  closeOffscreenClipboardDocument();
});

async function downloadTranscript(transcriptData) {
  const fileName = `${sanitizeFileName(transcriptData.title)}.txt`;
  const body = [
    `Title: ${transcriptData.title}`,
    `Video: ${transcriptData.videoUrl}`,
    `Language: ${transcriptData.languageCode} (${transcriptData.trackName})`,
    `FetchedAt: ${transcriptData.fetchedAt}`,
    "",
    transcriptData.transcript
  ].join("\n");

  const urls = [];
  let blobUrl = "";

  // First try Blob URL (fast path).
  try {
    if (typeof URL?.createObjectURL === "function") {
      const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
      blobUrl = URL.createObjectURL(blob);
      urls.push(blobUrl);
    }
  } catch {
    // ignore and fall back to data URL
  }

  // Fallback: data URL for environments where createObjectURL is unavailable.
  urls.push(buildTextDataUrl(body));

  let lastError = null;
  try {
    for (const url of urls) {
      try {
        const id = await chrome.downloads.download({
          url,
          filename: fileName,
          saveAs: false
        });
        if (typeof id === "number") {
          return;
        }
      } catch (error) {
        lastError = error;
      }
    }
  } finally {
    if (blobUrl) {
      try {
        URL.revokeObjectURL(blobUrl);
      } catch {
        // ignore revoke failure
      }
    }
  }

  throw new Error(
    `download failed: ${lastError?.message || "chrome.downloads.download returned no id"}`
  );
}

function buildTextDataUrl(text) {
  const bytes = new TextEncoder().encode(String(text || ""));
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  const base64 = btoa(binary);
  return `data:text/plain;charset=utf-8;base64,${base64}`;
}

function sanitizeFileName(name) {
  return (name || "youtube-transcript")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 100);
}

function normalizePromptTemplate(raw, fallbackTemplate = DEFAULT_SUMMARY_TEMPLATE) {
  const text = String(raw || "").trim();
  return text || fallbackTemplate;
}

function normalizeAiModel(value) {
  const key = String(value || "").trim().toLowerCase();
  return AI_TARGETS[key] ? key : "chatgpt";
}

function resolveAiTargetUrl(aiModel, customUrl, options = {}) {
  if (aiModel === "custom") {
    return normalizeGptSiteUrl(customUrl);
  }
  const base = AI_TARGETS[aiModel] || AI_TARGETS.chatgpt;
  if (!isChatGptFamilyModel(aiModel) || !options?.temporaryChat) {
    return base;
  }

  try {
    const url = new URL(base);
    url.searchParams.set("temporary-chat", "true");
    return url.toString();
  } catch {
    return base;
  }
}
function normalizeGptSiteUrl(rawUrl) {
  try {
    const parsed = new URL(String(rawUrl || "").trim());
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    // ignore invalid URL
  }
  return DEFAULT_SETTINGS.gptSiteUrl;
}

function isChatGptFamilyModel(aiModel) {
  return [
    "chatgpt",
    "gpt5_2",
    "gpt5_2_instant",
    "gpt5_2_thinking",
    "gpt5_1_instant",
    "gpt5_1_thinking",
    "gpt4o"
  ].includes(String(aiModel || "").trim().toLowerCase());
}




