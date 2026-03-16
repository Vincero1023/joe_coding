const titleEl = document.getElementById("doc-title");
const urlEl = document.getElementById("doc-url");
const statusEl = document.getElementById("status");
const contentEl = document.getElementById("content");
const downloadHtmlBtn = document.getElementById("download-html-btn");
const downloadTxtBtn = document.getElementById("download-txt-btn");
const copyHtmlBtn = document.getElementById("copy-html-btn");
const copyMdBtn = document.getElementById("copy-md-btn");

let currentHtmlForCopy = "";
let currentDocumentHtmlForDownload = "";
let markdownSourceRoot = null;

downloadHtmlBtn.addEventListener("click", () => {
  try {
    downloadHtmlFile(currentDocumentHtmlForDownload.trim(), titleEl.textContent || "capture");
    showStatus("HTML file downloaded");
  } catch (error) {
    showStatus(`Download failed: ${error.message}`);
  }
});

downloadTxtBtn.addEventListener("click", () => {
  try {
    const text = buildPlainTextFromCurrentSource();
    downloadTextFile(text, titleEl.textContent || "capture");
    showStatus("TXT file downloaded");
  } catch (error) {
    showStatus(`Download failed: ${error.message}`);
  }
});

copyHtmlBtn.addEventListener("click", async () => {
  await copyToClipboard(currentHtmlForCopy.trim());
  showStatus("HTML copied");
});

copyMdBtn.addEventListener("click", async () => {
  const markdown = buildMarkdownFromCurrentSource();
  await copyToClipboard(markdown.trim());
  showStatus("Markdown copied");
});

init().catch((error) => {
  showStatus(`Failed: ${error.message}`);
  console.error("[Text Copy Helper]", error);
});

async function init() {
  const params = new URL(location.href).searchParams;
  const captureId = params.get("id");
  const errorMessage = params.get("error");
  const sourceUrl = params.get("url") || "";

  if (sourceUrl) {
    urlEl.textContent = sourceUrl;
    urlEl.href = sourceUrl;
  }

  if (errorMessage) {
    titleEl.textContent = "Capture Failed";
    contentEl.textContent = errorMessage;
    downloadHtmlBtn.disabled = true;
    downloadTxtBtn.disabled = true;
    copyHtmlBtn.disabled = true;
    copyMdBtn.disabled = true;
    showStatus("Capture failed. Check page permissions or URL restrictions.");
    return;
  }

  if (!captureId) {
    throw new Error("Missing capture id");
  }

  const storageKey = `capture:${captureId}`;
  const payload = (await chrome.storage.local.get(storageKey))[storageKey];
  if (!payload) {
    throw new Error("Capture data was not found");
  }
  try {
    await chrome.storage.local.remove(storageKey);
  } catch {
    // Ignore cleanup failure and continue rendering the captured payload.
  }

  titleEl.textContent = payload.title || "Untitled";
  urlEl.textContent = payload.url || sourceUrl || "";
  urlEl.href = payload.url || sourceUrl || "#";

  if (payload.fullDocumentHtml && payload.renderMode === "visual") {
    document.body.classList.add("visual-mode");
    await renderVisualSnapshot(payload);
    showStatus("Visual snapshot captured");
    return;
  }

  renderCleanFragment(payload.html || "");
  showStatus(payload.selectionUsed ? "Captured from selection" : "Captured from page");
}

async function renderVisualSnapshot(payload) {
  const srcdoc = payload.fullDocumentHtml || buildFallbackDocument(payload.html || "", payload.url || "");
  currentHtmlForCopy = srcdoc;
  currentDocumentHtmlForDownload = srcdoc;

  const frame = document.createElement("iframe");
  frame.id = "visual-frame";
  frame.setAttribute(
    "sandbox",
    "allow-same-origin allow-top-navigation-by-user-activation allow-popups allow-popups-to-escape-sandbox"
  );
  frame.referrerPolicy = "strict-origin-when-cross-origin";
  frame.srcdoc = srcdoc;
  contentEl.replaceChildren(frame);

  await waitForFrameLoad(frame, 3500);

  const frameDoc = frame.contentDocument;
  if (frameDoc && frameDoc.body) {
    forceLinksToNewTab(frameDoc);
    markdownSourceRoot = frameDoc.body;
  } else {
    markdownSourceRoot = parseHtmlToBody(srcdoc);
  }
}

function renderCleanFragment(html) {
  const safeFragment = sanitizeHtml(html);
  contentEl.replaceChildren(safeFragment);
  currentHtmlForCopy = contentEl.innerHTML.trim();
  currentDocumentHtmlForDownload = buildFallbackDocument(currentHtmlForCopy, urlEl.href || location.href);
  markdownSourceRoot = contentEl;
}

function buildFallbackDocument(bodyHtml, baseUrl) {
  const escapedBase = escapeAttribute(baseUrl || location.href);
  return [
    "<!doctype html><html><head>",
    '<meta charset="utf-8">',
    `<base href="${escapedBase}">`,
    "</head><body>",
    bodyHtml,
    "</body></html>"
  ].join("");
}

function escapeAttribute(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function forceLinksToNewTab(doc) {
  doc.querySelectorAll("a[href]").forEach((link) => {
    if (String(link.getAttribute("href")).trim().startsWith("javascript:")) {
      link.removeAttribute("href");
      return;
    }
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer");
  });
}

function waitForFrameLoad(frame, timeoutMs) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) {
        return;
      }
      done = true;
      resolve();
    };

    frame.addEventListener("load", finish, { once: true });
    setTimeout(finish, timeoutMs);
  });
}

function parseHtmlToBody(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body;
}

function sanitizeHtml(html) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div id="root">${html}</div>`, "text/html");
  const root = doc.getElementById("root");
  if (!root) {
    return document.createDocumentFragment();
  }

  root
    .querySelectorAll(
      "script, iframe, object, embed, link, style, meta, form, input, button, textarea, select, canvas"
    )
    .forEach((el) => el.remove());

  for (const el of [root, ...Array.from(root.querySelectorAll("*"))]) {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();
      const value = attr.value || "";
      if (name.startsWith("on")) {
        el.removeAttribute(attr.name);
      }
      if (["src", "href", "poster"].includes(name) && value.startsWith("javascript:")) {
        el.removeAttribute(attr.name);
      }
    }
  }

  const fragment = document.createDocumentFragment();
  while (root.firstChild) {
    fragment.appendChild(root.firstChild);
  }
  return fragment;
}

function buildMarkdownFromCurrentSource() {
  if (!markdownSourceRoot) {
    throw new Error("Nothing to convert");
  }
  return htmlToMarkdown(markdownSourceRoot).trim();
}

function buildPlainTextFromCurrentSource() {
  if (!markdownSourceRoot) {
    throw new Error("Nothing to export");
  }

  const text = (markdownSourceRoot.innerText || markdownSourceRoot.textContent || "").trim();
  if (!text) {
    throw new Error("Nothing to export");
  }
  return text;
}

function downloadHtmlFile(html, rawTitle) {
  if (!html) {
    throw new Error("Nothing to download");
  }

  const filename = buildHtmlFileName(rawTitle);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const blobUrl = URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  setTimeout(() => {
    URL.revokeObjectURL(blobUrl);
  }, 1000);
}

function downloadTextFile(text, rawTitle) {
  if (!text) {
    throw new Error("Nothing to download");
  }

  const filename = buildTextFileName(rawTitle);
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const blobUrl = URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  setTimeout(() => {
    URL.revokeObjectURL(blobUrl);
  }, 1000);
}

function buildHtmlFileName(rawTitle) {
  const safeTitle = String(rawTitle || "capture")
    .replace(/[\\/:*?"<>|]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80) || "capture";

  const stamp = new Date()
    .toISOString()
    .replace(/[:]/g, "-")
    .replace(/\..+$/, "");

  return `${safeTitle}-${stamp}.html`;
}

function buildTextFileName(rawTitle) {
  const safeTitle = String(rawTitle || "capture")
    .replace(/[\\/:*?"<>|]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80) || "capture";

  const stamp = new Date()
    .toISOString()
    .replace(/[:]/g, "-")
    .replace(/\..+$/, "");

  return `${safeTitle}-${stamp}.txt`;
}

async function copyToClipboard(text) {
  if (!text) {
    throw new Error("Nothing to copy");
  }

  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    document.execCommand("copy");
    textArea.remove();
  }
}

function showStatus(message) {
  statusEl.textContent = message;
}

function htmlToMarkdown(root) {
  const lines = convertChildren(root, { inPre: false }).trim();
  return normalizeMarkdown(lines);
}

function convertChildren(node, context) {
  return Array.from(node.childNodes)
    .map((child) => convertNode(child, context))
    .join("");
}

function convertNode(node, context) {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent || "";
    if (context.inPre) {
      return text;
    }
    return collapseWhitespace(text);
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }

  const el = node;
  const tag = el.tagName.toLowerCase();
  const inner = convertChildren(el, context);

  switch (tag) {
    case "h1":
    case "h2":
    case "h3":
    case "h4":
    case "h5":
    case "h6": {
      const depth = Number(tag.slice(1));
      return `\n\n${"#".repeat(depth)} ${inlineText(el)}\n\n`;
    }
    case "p":
      return `\n\n${inner.trim()}\n\n`;
    case "br":
      return "  \n";
    case "hr":
      return "\n\n---\n\n";
    case "strong":
    case "b":
      return `**${inner.trim() || inlineText(el)}**`;
    case "em":
    case "i":
      return `*${inner.trim() || inlineText(el)}*`;
    case "code":
      if (el.parentElement && el.parentElement.tagName.toLowerCase() === "pre") {
        return inner;
      }
      return `\`${(el.textContent || "").replace(/`/g, "\\`")}\``;
    case "pre": {
      const code = (el.textContent || "").replace(/\n+$/, "");
      return `\n\n\`\`\`\n${code}\n\`\`\`\n\n`;
    }
    case "blockquote": {
      const text = normalizeMarkdown(inner).trim();
      if (!text) {
        return "";
      }
      const quoted = text
        .split("\n")
        .map((line) => `> ${line}`)
        .join("\n");
      return `\n\n${quoted}\n\n`;
    }
    case "a": {
      const text = inlineText(el) || "link";
      const href = el.getAttribute("href");
      return href ? `[${text}](${href})` : text;
    }
    case "img": {
      const alt = el.getAttribute("alt") || "";
      const src = el.getAttribute("src") || "";
      if (!src) {
        return "";
      }
      return `![${alt}](${src})`;
    }
    case "ul":
      return renderList(el, false);
    case "ol":
      return renderList(el, true);
    case "table":
      return renderTable(el);
    case "thead":
    case "tbody":
    case "tfoot":
      return inner;
    case "tr":
    case "th":
    case "td":
      return inner;
    case "div":
    case "section":
    case "article":
    case "main":
    case "figure":
    case "figcaption":
      return `\n\n${inner}\n\n`;
    case "span":
    case "small":
    case "sup":
    case "sub":
      return inner;
    default:
      return inner;
  }
}

function renderList(listEl, ordered) {
  const items = Array.from(listEl.children).filter(
    (child) => child.tagName.toLowerCase() === "li"
  );
  if (items.length === 0) {
    return "";
  }

  let index = 1;
  const lines = items.map((item) => {
    const prefix = ordered ? `${index}. ` : "- ";
    index += 1;
    const content = normalizeMarkdown(convertChildren(item, { inPre: false })).trim();
    if (!content) {
      return `${prefix.trim()}`;
    }
    const normalized = content.replace(/\n/g, "\n  ");
    return `${prefix}${normalized}`;
  });

  return `\n\n${lines.join("\n")}\n\n`;
}

function renderTable(tableEl) {
  const rows = Array.from(tableEl.querySelectorAll("tr")).map((row) =>
    Array.from(row.children)
      .filter((cell) => ["th", "td"].includes(cell.tagName.toLowerCase()))
      .map((cell) => normalizeCellText(convertChildren(cell, { inPre: false })))
  );

  const nonEmptyRows = rows.filter((row) => row.length > 0);
  if (nonEmptyRows.length === 0) {
    return "";
  }

  const columnCount = Math.max(...nonEmptyRows.map((row) => row.length));
  const paddedRows = nonEmptyRows.map((row) => {
    const padded = row.slice();
    while (padded.length < columnCount) {
      padded.push("");
    }
    return padded;
  });

  const header = paddedRows[0];
  const separator = new Array(columnCount).fill("---");
  const body = paddedRows.slice(1);

  const lines = [
    `| ${header.join(" | ")} |`,
    `| ${separator.join(" | ")} |`,
    ...body.map((row) => `| ${row.join(" | ")} |`)
  ];

  return `\n\n${lines.join("\n")}\n\n`;
}

function inlineText(node) {
  return collapseWhitespace(node.textContent || "").trim();
}

function collapseWhitespace(text) {
  return text.replace(/\s+/g, " ");
}

function normalizeCellText(text) {
  return text.replace(/\|/g, "\\|").replace(/\n+/g, " ").trim();
}

function normalizeMarkdown(text) {
  return (
    text
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/[ \t]{2,}/g, " ")
      .trim() + "\n"
  );
}
