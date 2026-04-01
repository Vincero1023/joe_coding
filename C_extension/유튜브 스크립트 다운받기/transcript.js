const STORAGE_KEY = "lastResult";

const elements = {
  title: document.getElementById("title"),
  meta: document.getElementById("meta"),
  videoLink: document.getElementById("videoLink"),
  promptSection: document.getElementById("promptSection"),
  promptHeading: document.getElementById("promptHeading"),
  promptText: document.getElementById("promptText"),
  transcriptText: document.getElementById("transcriptText"),
  copyPrompt: document.getElementById("copyPrompt"),
  openGptSite: document.getElementById("openGptSite"),
  copyTranscript: document.getElementById("copyTranscript"),
  downloadTranscript: document.getElementById("downloadTranscript"),
  downloadMarkdown: document.getElementById("downloadMarkdown"),
  debugSection: document.getElementById("debugSection"),
  debugText: document.getElementById("debugText"),
  status: document.getElementById("status")
};

let currentData = null;

initialize().catch((error) => setStatus(error.message, true));

async function initialize() {
  const data = await chrome.storage.local.get(STORAGE_KEY);
  currentData = data?.[STORAGE_KEY];

  if (!currentData) {
    throw new Error("No result data found. Run an action from popup first.");
  }

  render(currentData);
  bindEvents();
}

function bindEvents() {
  elements.copyTranscript.addEventListener("click", async () => {
    await copyText(currentData.transcript);
    setStatus("Transcript copied.");
  });

  elements.copyPrompt.addEventListener("click", async () => {
    await copyText(getPromptText(currentData));
    setStatus("Prompt copied.");
  });

  elements.openGptSite.addEventListener("click", () => {
    const url = normalizeUrl(currentData.gptSiteUrl || "https://chatgpt.com/");
    window.open(url, "_blank", "noopener,noreferrer");
    setStatus("Opened GPT site.");
  });

  elements.downloadTranscript.addEventListener("click", () => {
    downloadTextFile(
      `${sanitizeFileName(currentData.title)}.txt`,
      currentData.transcript,
      "text/plain;charset=utf-8"
    );
    setStatus("Transcript downloaded.");
  });

  elements.downloadMarkdown.addEventListener("click", () => {
    downloadTextFile(
      `${sanitizeFileName(currentData.title)}.md`,
      buildMarkdown(currentData),
      "text/markdown;charset=utf-8"
    );
    setStatus("Markdown downloaded.");
  });
}

function render(data) {
  elements.title.textContent = data.title || "YouTube Transcript";
  elements.meta.textContent = `Language: ${data.languageCode} (${data.trackName}) | Fetched: ${formatDate(
    data.fetchedAt
  )}`;
  elements.videoLink.href = data.videoUrl || "#";
  elements.transcriptText.textContent = data.transcript || "";

  const promptText = getPromptText(data);
  if (promptText) {
    elements.promptSection.classList.remove("hidden");
    elements.promptHeading.textContent = getPromptTitle(data);
    elements.promptText.textContent = promptText;
  } else {
    elements.promptSection.classList.add("hidden");
  }

  if (data.debugInfo) {
    elements.debugSection.classList.remove("hidden");
    elements.debugText.textContent = formatDebugInfo(data.debugInfo);
  } else {
    elements.debugSection.classList.add("hidden");
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text || "");
  } catch {
    throw new Error("Clipboard copy failed.");
  }
}

function downloadTextFile(fileName, content, mimeType = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

function sanitizeFileName(name) {
  return (name || "youtube-transcript")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 100);
}

function formatDate(iso) {
  if (!iso) return "-";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "-" : date.toLocaleString();
}

function normalizeUrl(raw) {
  try {
    const parsed = new URL(raw);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    // ignore invalid URL
  }
  return "https://chatgpt.com/";
}

function buildMarkdown(data) {
  const title = String(data.title || "YouTube Transcript").trim();
  const videoUrl = String(data.videoUrl || "").trim();
  const languageCode = String(data.languageCode || "-").trim();
  const trackName = String(data.trackName || "-").trim();
  const fetchedAt = formatDate(data.fetchedAt);
  const promptTitle = getPromptTitle(data);
  const promptText = getPromptText(data);
  const transcript = normalizeMarkdownBody(data.transcript || "");
  const frontmatter = [
    "---",
    `title: ${toYamlScalar(title)}`,
    `video_url: ${toYamlScalar(videoUrl || "-")}`,
    `language: ${toYamlScalar(languageCode)}`,
    `track: ${toYamlScalar(trackName)}`,
    `fetched_at: ${toYamlScalar(fetchedAt)}`,
    `prompt_kind: ${toYamlScalar(String(data.promptKind || "").trim() || "-")}`,
    "---",
    ""
  ];

  const lines = [
    ...frontmatter,
    `# ${title}`,
    "",
    "## Source",
    "",
    `- Video: ${videoUrl || "-"}`,
    `- Language: ${languageCode}`,
    `- Track: ${trackName}`,
    `- Fetched: ${fetchedAt}`,
    ""
  ];

  if (promptText) {
    lines.push(`## ${promptTitle}`);
    lines.push("");
    lines.push("```text");
    lines.push(promptText);
    lines.push("```");
    lines.push("");
  }

  lines.push("## Transcript");
  lines.push("");
  lines.push(transcript || "_Transcript is empty._");

  if (data.debugInfo) {
    lines.push("");
    lines.push("## Debug");
    lines.push("");
    lines.push(...buildDebugMarkdown(data.debugInfo));
  }

  return lines.join("\n").trim() + "\n";
}

function buildDebugMarkdown(debugInfo) {
  const lines = [
    `- Success Path: ${debugInfo.successPath || "-"}`,
    `- Build: ${debugInfo.buildId || "-"}`
  ];

  if (debugInfo.failed) {
    lines.push("- Result: FAIL");
  }
  if (Array.isArray(debugInfo.strategyOrder) && debugInfo.strategyOrder.length) {
    lines.push(`- Order: ${debugInfo.strategyOrder.join(" -> ")}`);
  }

  if (Array.isArray(debugInfo.attempts) && debugInfo.attempts.length) {
    lines.push("- Attempts:");
    for (const item of debugInfo.attempts) {
      lines.push(`  - ${item.step}: ${item.ok ? "OK" : "FAIL"} | ${item.message || ""}`);
    }
  }

  return lines;
}

function formatDebugInfo(debugInfo) {
  const lines = [
    `Success Path: ${debugInfo.successPath || "-"}`,
    `Build: ${debugInfo.buildId || "-"}`
  ];

  if (debugInfo.failed) {
    lines.push("Result: FAIL");
  }
  if (Array.isArray(debugInfo.strategyOrder) && debugInfo.strategyOrder.length) {
    lines.push(`Order: ${debugInfo.strategyOrder.join(" -> ")}`);
  }

  if (Array.isArray(debugInfo.attempts) && debugInfo.attempts.length) {
    lines.push("Attempts:");
    for (const item of debugInfo.attempts) {
      lines.push(`- ${item.step}: ${item.ok ? "OK" : "FAIL"} | ${item.message || ""}`);
    }
  }

  return lines.join("\n");
}

function getPromptText(data) {
  return String(data?.promptText || data?.summaryPrompt || "").trim();
}

function getPromptTitle(data) {
  const explicit = String(data?.promptTitle || "").trim();
  if (explicit) {
    return explicit;
  }

  const kind = String(data?.promptKind || "").trim().toLowerCase();
  if (kind === "manual") {
    return "AI Manual Prompt";
  }
  return "AI Summary Prompt";
}

function normalizeMarkdownBody(text) {
  return String(text || "")
    .replace(/\r/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function toYamlScalar(value) {
  return JSON.stringify(String(value || ""));
}

function setStatus(message, isError = false) {
  elements.status.textContent = message;
  elements.status.classList.toggle("error", Boolean(isError));
}
