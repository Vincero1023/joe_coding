const DEFAULT_SETTINGS = {
  preferredLanguage: "",
  gptSiteUrl: "https://chatgpt.com/",
  aiModel: "chatgpt",
  autoSubmit: true,
  chatgptTemporaryChat: true,
  summaryTemplate: "",
  summaryPreset: "default",
  manualTemplate: "",
  manualPreset: "default"
};

const BUILD_LABEL = "1.5.4-direct-llm-stability";

const SUMMARY_PRESETS = {
  default:
    "Analyze the following YouTube transcript and organize it in a 2-layer output.\n\n[Layer 1: Structure For Understanding]\n- One-sentence core claim of the video\n- Organize into 5-10 thought blocks\n- Compress each block into 2-3 sentences\n- Keep the logical flow explicit\n\n[Layer 2: Reusable Material Extraction]\nExtract and present as a table:\n- Quotes / notable lines\n- Statistics / data / experiment results\n- Cases / examples\n- References / books / papers\nFor each item include:\n- Short summary\n- Where it can be reused (sermon/lecture/blog/etc)\n- Category\n- 3-5 hashtags\n\nFocus on thought-structure decomposition and material extraction, not generic summarization.\n\nTitle: {{TITLE}}\nURL: {{URL}}\n\nTranscript:\n{{TEXT}}",
  sermon:
    "Read the following YouTube transcript and turn it into sermon-ready material.\n\nOutput:\n- Core biblical or spiritual thesis in one sentence\n- 3-5 sermon movements with clear progression\n- Key illustrations, stories, and memorable lines\n- Practical application points for listeners\n- Closing challenge or response prompt\n\nKeep the tone faithful to the source, but restructure for preaching clarity.\n\nTitle: {{TITLE}}\nURL: {{URL}}\n\nTranscript:\n{{TEXT}}",
  lecture:
    "Analyze the following transcript as lecture material.\n\nOutput:\n- Main thesis\n- Section-by-section outline\n- Definitions, key concepts, and frameworks\n- Important examples or supporting evidence\n- Potential discussion questions\n- Concise review summary for students\n\nPrefer clarity, structure, and educational usefulness over general summarization.\n\nTitle: {{TITLE}}\nURL: {{URL}}\n\nTranscript:\n{{TEXT}}",
  blog:
    "Transform the following transcript into blog-ready material.\n\nOutput:\n- Proposed article title options\n- Strong opening hook\n- 4-7 section outline with section summaries\n- Quotable lines worth preserving\n- Practical takeaways for readers\n- Suggested closing paragraph idea\n\nKeep the structure scannable and publication-friendly.\n\nTitle: {{TITLE}}\nURL: {{URL}}\n\nTranscript:\n{{TEXT}}",
  study:
    "Turn the following transcript into study notes.\n\nOutput:\n- Main argument in one sentence\n- Hierarchical outline\n- Key facts, claims, and evidence\n- Important terms and short definitions\n- Questions worth reviewing later\n- Brief recap section for revision\n\nOptimize for learning, review, and note-taking.\n\nTitle: {{TITLE}}\nURL: {{URL}}\n\nTranscript:\n{{TEXT}}"
};

const MANUAL_PRESETS = {
  default:
    "Turn the following YouTube transcript into a detailed practical manual in Markdown.\n\nContext:\n- The source is usually an information video, explainer, tutorial, walkthrough, review, or process guide.\n- Reconstruct the content into a usable manual even if the speaker is conversational or repetitive.\n- Remove filler, repetition, sponsor talk, greetings, and off-topic remarks.\n\nOutput requirements:\n- Return valid Markdown only\n- Start with `# {{TITLE}} Manual`\n- Then include these sections in order:\n  1. `## Overview`\n  2. `## Who This Is For`\n  3. `## What You Need Before Starting`\n  4. `## Key Concepts`\n  5. `## Step-by-Step Instructions`\n  6. `## Important Tips and Warnings`\n  7. `## Common Mistakes / Troubleshooting`\n  8. `## Quick Checklist`\n  9. `## Source Notes`\n- In `Step-by-Step Instructions`, create numbered steps and add sub-bullets for details, conditions, examples, and decision points.\n- If the video implies missing assumptions, state them explicitly as `Assumption:` instead of inventing facts.\n- If there are multiple methods, split them into separate subsections and explain when to use each.\n- Keep technical details concrete and operational.\n- Preserve important terminology from the source.\n- End `Source Notes` with:\n  - `Video Title: {{TITLE}}`\n  - `Video URL: {{URL}}`\n\nTranscript:\n{{TEXT}}",
  tutorial:
    "Convert the following YouTube transcript into a task-oriented tutorial in Markdown.\n\nOutput rules:\n- Return Markdown only\n- Start with `# {{TITLE}} Tutorial`\n- Organize the result as:\n  - `## Goal`\n  - `## Prerequisites`\n  - `## Steps`\n  - `## Verification`\n  - `## Troubleshooting`\n  - `## Recap`\n- Under `## Steps`, write numbered actions with clear expected result after each major step.\n- Convert spoken explanations into precise action language.\n- Highlight optional branches with `Optional:` and risk points with `Warning:`.\n- If the speaker compares alternatives, summarize them in a Markdown table.\n- Keep the final result concise but detailed enough for someone to follow without the video.\n\nVideo Title: {{TITLE}}\nVideo URL: {{URL}}\n\nTranscript:\n{{TEXT}}",
  reference:
    "Analyze the following YouTube transcript and turn it into a structured reference guide in Markdown.\n\nOutput rules:\n- Return Markdown only\n- Start with `# {{TITLE}} Reference Guide`\n- Include these sections:\n  - `## Summary`\n  - `## Terms and Definitions`\n  - `## Core Process`\n  - `## Rules / Constraints`\n  - `## Decision Criteria`\n  - `## Examples`\n  - `## FAQ`\n  - `## Action Checklist`\n- Prefer scannable bullets, short paragraphs, and tables where useful.\n- Distill the information into reusable reference material rather than a transcript summary.\n- If the source is ambiguous, mark uncertain items as `Needs verification`.\n\nVideo Title: {{TITLE}}\nVideo URL: {{URL}}\n\nTranscript:\n{{TEXT}}"
};

const elements = {
  status: document.getElementById("status"),
  customAiUrl: document.getElementById("customAiUrl"),
  language: document.getElementById("language"),
  autoSubmit: document.getElementById("autoSubmit"),
  chatgptTemporaryChat: document.getElementById("chatgptTemporaryChat"),
  summaryPreset: document.getElementById("summaryPreset"),
  applyPreset: document.getElementById("applyPreset"),
  summaryTemplate: document.getElementById("summaryTemplate"),
  manualPreset: document.getElementById("manualPreset"),
  applyManualPreset: document.getElementById("applyManualPreset"),
  manualTemplate: document.getElementById("manualTemplate"),
  modelButtons: Array.from(document.querySelectorAll(".model-btn")),
  saveButton: document.getElementById("saveSettings"),
  actionButtons: Array.from(document.querySelectorAll("[data-action]")),
  buildInfo: document.getElementById("buildInfo"),
  debugInfo: document.getElementById("debugInfo")
};

let selectedModel = DEFAULT_SETTINGS.aiModel;

initialize().catch((error) => setStatus(error.message, true));

async function initialize() {
  const response = await sendMessage({ type: "get-settings" });
  if (!response.ok) {
    throw new Error(await formatUiError(response, "Failed to load settings."));
  }

  const settings = { ...DEFAULT_SETTINGS, ...(response.settings || {}) };
  selectedModel = String(settings.aiModel || DEFAULT_SETTINGS.aiModel);
  elements.customAiUrl.value = settings.gptSiteUrl || DEFAULT_SETTINGS.gptSiteUrl;
  elements.language.value = settings.preferredLanguage || "";
  elements.autoSubmit.checked = Boolean(settings.autoSubmit);
  elements.chatgptTemporaryChat.checked = Boolean(settings.chatgptTemporaryChat);
  elements.summaryPreset.value = SUMMARY_PRESETS[String(settings.summaryPreset || "default")]
    ? String(settings.summaryPreset || "default")
    : "default";
  elements.summaryTemplate.value = settings.summaryTemplate || "";
  elements.manualPreset.value = MANUAL_PRESETS[String(settings.manualPreset || "default")]
    ? String(settings.manualPreset || "default")
    : "default";
  elements.manualTemplate.value = settings.manualTemplate || "";
  renderModelSelection();
  await renderDebugInfo();

  const manifest = chrome.runtime.getManifest();
  elements.buildInfo.textContent = `Version ${manifest.version} (${BUILD_LABEL})`;

  elements.saveButton.addEventListener("click", onSaveSettings);
  elements.modelButtons.forEach((button) => {
    button.addEventListener("click", () => {
      selectedModel = button.dataset.model || "chatgpt";
      renderModelSelection();
    });
  });
  elements.applyPreset.addEventListener("click", applySelectedPreset);
  elements.applyManualPreset.addEventListener("click", applySelectedManualPreset);
  elements.actionButtons.forEach((button) => {
    button.addEventListener("click", () => runAction(button.dataset.action));
  });
}

function collectSettingsPayload() {
  return {
    aiModel: selectedModel,
    gptSiteUrl: elements.customAiUrl.value.trim() || DEFAULT_SETTINGS.gptSiteUrl,
    preferredLanguage: elements.language.value.trim(),
    autoSubmit: elements.autoSubmit.checked,
    chatgptTemporaryChat: elements.chatgptTemporaryChat.checked,
    summaryPreset: elements.summaryPreset.value,
    summaryTemplate: elements.summaryTemplate.value.trim(),
    manualPreset: elements.manualPreset.value,
    manualTemplate: elements.manualTemplate.value.trim()
  };
}

function renderModelSelection() {
  elements.modelButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.model === selectedModel);
  });
  elements.customAiUrl.disabled = selectedModel !== "custom";
}

async function onSaveSettings() {
  toggleBusy(true);
  try {
    const response = await sendMessage({
      type: "save-settings",
      settings: collectSettingsPayload()
    });

    if (!response.ok) {
      throw new Error(await formatUiError(response, "Failed to save settings."));
    }

    setStatus("Settings saved.");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    toggleBusy(false);
  }
}

async function runAction(action) {
  toggleBusy(true);
  setStatus("Working...");
  try {
    // Use latest UI settings immediately.
    const saveResponse = await sendMessage({
      type: "save-settings",
      settings: collectSettingsPayload()
    });
    if (!saveResponse.ok) {
      throw new Error(await formatUiError(saveResponse, "Failed to apply settings."));
    }

    const response = await sendMessage({
      type: "run-action",
      action
    });

    if (!response.ok) {
      throw new Error(await formatUiError(response, "Action failed."));
    }

    setStatus(response.result || "Done.");
    await renderDebugInfo();
  } catch (error) {
    setStatus(error.message, true);
    await renderDebugInfo();
  } finally {
    toggleBusy(false);
  }
}

function applySelectedPreset() {
  const preset = String(elements.summaryPreset.value || "default");
  elements.summaryTemplate.value = SUMMARY_PRESETS[preset] || SUMMARY_PRESETS.default;
  setStatus(`Applied preset: ${preset}.`);
}

function applySelectedManualPreset() {
  const preset = String(elements.manualPreset.value || "default");
  elements.manualTemplate.value = MANUAL_PRESETS[preset] || MANUAL_PRESETS.default;
  setStatus(`Applied manual preset: ${preset}.`);
}

function toggleBusy(isBusy) {
  elements.actionButtons.forEach((button) => {
    button.disabled = isBusy;
  });
  elements.modelButtons.forEach((button) => {
    button.disabled = isBusy;
  });
  elements.saveButton.disabled = isBusy;
}

function setStatus(message, isError = false) {
  elements.status.textContent = message;
  elements.status.classList.toggle("error", Boolean(isError));
}

function sendMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, error: chrome.runtime.lastError.message });
        return;
      }
      resolve(response || { ok: false, error: "Empty response." });
    });
  });
}

async function formatUiError(response, fallback) {
  const message = String(response?.error || "").trim();
  if (message) {
    return message;
  }

  const code = String(response?.errorCode || "").trim();
  if (code) {
    const latest = await sendMessage({ type: "get-error-log", errorCode: code });
    const logMessage = String(latest?.log?.message || "").trim();
    if (logMessage) {
      return `Error. ${logMessage} (${code})`;
    }
    return `Error. Code: ${code}`;
  }
  return fallback;
}

async function renderDebugInfo() {
  const [debugResponse, errorResponse] = await Promise.all([
    sendMessage({ type: "get-debug-state" }),
    sendMessage({ type: "get-latest-error-log" })
  ]);

  const debugState = debugResponse?.settings || debugResponse?.data || {};
  const lastFetch = debugState?.lastFetch;
  const lastError = errorResponse?.log || debugState?.lastError || null;
  const pathHealth = debugState?.pathHealth || null;

  const lines = [];

  if (lastFetch) {
    lines.push(`Last fetch path: ${lastFetch.successPath || "-"}`);
    lines.push(`Build: ${lastFetch.buildId || "-"}`);
    if (lastFetch.failed) {
      lines.push("Last fetch result: FAIL");
    }
    if (Array.isArray(lastFetch.strategyOrder) && lastFetch.strategyOrder.length) {
      lines.push(`Order: ${lastFetch.strategyOrder.join(" -> ")}`);
    }
    if (Array.isArray(lastFetch.attempts) && lastFetch.attempts.length) {
      lines.push("Attempts:");
      for (const item of lastFetch.attempts) {
        lines.push(`- ${item.step}: ${item.ok ? "OK" : "FAIL"} | ${item.message || ""}`);
      }
    }
  } else {
    lines.push("Last fetch path: -");
  }

  if (lastError) {
    lines.push("");
    lines.push(`Last error: ${lastError.message || "-"}`);
    if (lastError.code) {
      lines.push(`Error code: ${lastError.code}`);
    }
  }

  const strategyNames = ["current-page", "source-tab", "watch-html", "temporary-watch-tab"];
  const strategyStats =
    pathHealth?.strategies && typeof pathHealth.strategies === "object" ? pathHealth.strategies : null;

  if (strategyStats) {
    const healthLines = [];
    for (const step of strategyNames) {
      const stat = strategyStats[step];
      if (!stat) continue;
      const summary = [
        `${step}: ${Number(stat.successCount || 0)} ok / ${Number(stat.failureCount || 0)} fail`,
        `last=${stat.lastResult || "-"}`,
        `streak=${Number(stat.consecutiveFailures || 0)}`
      ];
      const message = String(stat.lastMessage || "").trim();
      if (message) {
        summary.push(message.slice(0, 90));
      }
      healthLines.push(`- ${summary.join(" | ")}`);
    }

    if (healthLines.length) {
      lines.push("");
      lines.push(`Preferred path: ${pathHealth.lastSuccessfulPath || "-"}`);
      lines.push("Path health:");
      lines.push(...healthLines);
    }
  }

  elements.debugInfo.textContent = lines.join("\n").trim() || "No debug data yet.";
}
