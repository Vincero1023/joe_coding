import { normalizeSiteUrl, toOriginPattern } from "./collector.js";
import { runSiteBenchmark } from "./analyzer.js";

const siteUrlInput = document.querySelector("#siteUrl");
const analysisLimitSelect = document.querySelector("#analysisLimit");
const collectButton = document.querySelector("#collectButton");
const useCurrentTabButton = document.querySelector("#useCurrentTab");
const copyButton = document.querySelector("#copyButton");
const downloadButton = document.querySelector("#downloadButton");
const jsonButton = document.querySelector("#jsonButton");
const statusNode = document.querySelector("#status");
const countBadge = document.querySelector("#countBadge");
const sourceList = document.querySelector("#sourceList");
const noteList = document.querySelector("#noteList");
const resultBox = document.querySelector("#resultBox");

const metricCoverage = document.querySelector("#metricCoverage");
const metricCommercial = document.querySelector("#metricCommercial");
const metricMoneyPages = document.querySelector("#metricMoneyPages");
const metricFormula = document.querySelector("#metricFormula");

const commercialKeywordList = document.querySelector("#commercialKeywordList");
const categoryList = document.querySelector("#categoryList");
const moneyPageList = document.querySelector("#moneyPageList");
const formulaList = document.querySelector("#formulaList");
const patternList = document.querySelector("#patternList");
const opportunityScoreList = document.querySelector("#opportunityScoreList");
const opportunityList = document.querySelector("#opportunityList");

const tabButtons = [...document.querySelectorAll(".tab-button")];
const tabPanels = [...document.querySelectorAll(".tab-panel")];

let lastResult = null;

hydrateFromStorage();
wireEvents();
activateTab("keywords");

async function hydrateFromStorage() {
  const storage = await chrome.storage.local.get(["lastSiteUrl", "analysisLimit"]);
  if (storage.lastSiteUrl) {
    siteUrlInput.value = storage.lastSiteUrl;
  }
  if (storage.analysisLimit) {
    analysisLimitSelect.value = String(storage.analysisLimit);
  }
}

function wireEvents() {
  useCurrentTabButton.addEventListener("click", useCurrentTab);
  collectButton.addEventListener("click", handleCollect);
  copyButton.addEventListener("click", handleCopy);
  downloadButton.addEventListener("click", handleDownloadText);
  jsonButton.addEventListener("click", handleDownloadJson);
  tabButtons.forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.tab)));
}

async function useCurrentTab() {
  setStatus("현재 탭 URL 확인 중...");

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url || !/^https?:/i.test(tab.url)) {
      throw new Error("현재 탭이 http/https 페이지가 아닙니다.");
    }

    siteUrlInput.value = normalizeSiteUrl(tab.url);
    setStatus("현재 탭 URL을 입력했습니다.", true);
  } catch (error) {
    setStatus(error.message || "현재 탭 URL을 가져오지 못했습니다.");
  }
}

async function handleCollect() {
  toggleBusy(true);
  resetResults();

  try {
    const siteUrl = normalizeSiteUrl(siteUrlInput.value);
    const analysisLimit = Number(analysisLimitSelect.value || "80");

    siteUrlInput.value = siteUrl;
    await chrome.storage.local.set({ lastSiteUrl: siteUrl, analysisLimit });
    await ensureHostPermission(siteUrl);

    const result = await runSiteBenchmark(siteUrl, { analysisLimit }, (message) => setStatus(message));
    lastResult = result;

    renderSummary(result);
    renderAnalytics(result);
    resultBox.value = result.exportText;
    activateTab("keywords");
    setStatus(`분석 완료: ${result.analyzedUrlCount}/${result.collectedUrlCount}개 페이지 분석`, true);
    copyButton.disabled = false;
    downloadButton.disabled = false;
    jsonButton.disabled = false;
  } catch (error) {
    setStatus(error.message || "분석에 실패했습니다.");
  } finally {
    toggleBusy(false);
  }
}

async function ensureHostPermission(siteUrl) {
  const originPattern = toOriginPattern(siteUrl);
  const alreadyGranted = await chrome.permissions.contains({ origins: [originPattern] });

  if (alreadyGranted) {
    return;
  }

  const granted = await chrome.permissions.request({ origins: [originPattern] });
  if (!granted) {
    throw new Error("사이트 접근 권한이 필요합니다.");
  }
}

async function handleCopy() {
  if (!resultBox.value) {
    return;
  }

  try {
    await navigator.clipboard.writeText(resultBox.value);
    setStatus("표 형식 결과를 클립보드에 복사했습니다.", true);
  } catch (error) {
    setStatus("복사에 실패했습니다.");
  }
}

function handleDownloadText() {
  if (!lastResult?.exportText) {
    return;
  }

  const siteHost = new URL(lastResult.siteUrl).host.replace(/[^\w.-]+/g, "_");
  triggerDownload(`${siteHost}_benchmark.tsv`, lastResult.exportText, "text/tab-separated-values;charset=utf-8");
  setStatus("TSV 파일을 저장했습니다.", true);
}

function handleDownloadJson() {
  if (!lastResult?.exportJson) {
    return;
  }

  const siteHost = new URL(lastResult.siteUrl).host.replace(/[^\w.-]+/g, "_");
  triggerDownload(`${siteHost}_benchmark.json`, JSON.stringify(lastResult.exportJson, null, 2), "application/json;charset=utf-8");
  setStatus("JSON 파일을 저장했습니다.", true);
}

function triggerDownload(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 500);
}

function activateTab(tabName) {
  tabButtons.forEach((button) => {
    const isActive = button.dataset.tab === tabName;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  tabPanels.forEach((panel) => {
    const isActive = panel.dataset.panel === tabName;
    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
  });
}

function resetResults() {
  lastResult = null;
  resultBox.value = "";
  sourceList.innerHTML = "";
  noteList.innerHTML = "";
  commercialKeywordList.innerHTML = "";
  categoryList.innerHTML = "";
  moneyPageList.innerHTML = "";
  formulaList.innerHTML = "";
  patternList.innerHTML = "";
  opportunityScoreList.innerHTML = "";
  opportunityList.innerHTML = "";
  countBadge.textContent = "0 / 0";
  metricCoverage.textContent = "0 / 0";
  metricCommercial.textContent = "-";
  metricMoneyPages.textContent = "0";
  metricFormula.textContent = "-";
  copyButton.disabled = true;
  downloadButton.disabled = true;
  jsonButton.disabled = true;
}

function renderSummary(result) {
  countBadge.textContent = `${result.analyzedUrlCount} / ${result.collectedUrlCount}`;
  sourceList.innerHTML = "";
  noteList.innerHTML = "";

  for (const source of result.collection.sourceStats) {
    const item = document.createElement("li");
    item.textContent = `${source.label}: ${source.count}개`;
    sourceList.append(item);
  }

  for (const note of [...result.notes, ...result.errors]) {
    const item = document.createElement("li");
    item.textContent = note;
    noteList.append(item);
  }
}

function renderAnalytics(result) {
  const {
    summary,
    commercialKeywords,
    categoryFrequency,
    moneyPages,
    titleFormulas,
    titlePatterns,
    opportunityScores,
    opportunities
  } = result.analytics;

  metricCoverage.textContent = `${summary.collectedUrlCount} / ${summary.analyzedUrlCount}`;
  metricCommercial.textContent = commercialKeywords[0]?.label || "-";
  metricMoneyPages.textContent = String(summary.moneyPageCount);
  metricFormula.textContent = titleFormulas[0]?.label || "-";

  renderSimpleList(commercialKeywordList, commercialKeywords, (item) => `${item.label} · 점수 ${item.score} · ${item.count}개`);
  renderSimpleList(categoryList, categoryFrequency, (item) => `${item.label} (${item.count})`);
  renderMoneyPages(moneyPages);
  renderFormulas(titleFormulas);
  renderSimpleList(patternList, titlePatterns, (item) => `${item.label} (${item.count})`);
  renderOpportunityScores(opportunityScores);
  renderSimpleList(opportunityList, opportunities, (item) => item);
}

function renderMoneyPages(items) {
  moneyPageList.innerHTML = "";

  for (const item of items) {
    const node = document.createElement("li");
    node.className = "ranked-item";

    const titleNode = document.createElement("div");
    titleNode.className = "ranked-title";
    titleNode.textContent = item.title;

    const metaNode = document.createElement("div");
    metaNode.className = "ranked-meta";
    metaNode.textContent = `${item.moneyPageType} · 머니 ${item.moneyPageScore} · 수익 ${item.monetizationScore} · 상업 ${item.commercialKeywordScore}`;

    const urlNode = document.createElement("div");
    urlNode.className = "ranked-url";
    urlNode.textContent = item.url;

    const reasonNode = document.createElement("div");
    reasonNode.className = "ranked-reasons";
    reasonNode.textContent = item.reasons.join(" · ");

    node.append(titleNode, metaNode, urlNode, reasonNode);
    moneyPageList.append(node);
  }
}

function renderFormulas(items) {
  formulaList.innerHTML = "";

  for (const item of items) {
    const node = document.createElement("li");
    node.className = "ranked-item";

    const titleNode = document.createElement("div");
    titleNode.className = "ranked-title";
    titleNode.textContent = `${item.label} · 점수 ${item.score} · ${item.count}개`;

    const templateNode = document.createElement("div");
    templateNode.className = "ranked-template";
    templateNode.textContent = item.template;

    const exampleNode = document.createElement("div");
    exampleNode.className = "ranked-reasons";
    exampleNode.textContent = item.examples.join(" | ");

    node.append(titleNode, templateNode, exampleNode);
    formulaList.append(node);
  }
}

function renderOpportunityScores(items) {
  opportunityScoreList.innerHTML = "";

  for (const item of items) {
    const node = document.createElement("li");
    node.className = "ranked-item";

    const titleNode = document.createElement("div");
    titleNode.className = "ranked-title";
    titleNode.textContent = `${item.label} · 기회 ${item.score}`;

    const metaNode = document.createElement("div");
    metaNode.className = "ranked-reasons";
    metaNode.textContent = item.rationale;

    node.append(titleNode, metaNode);
    opportunityScoreList.append(node);
  }
}

function renderSimpleList(container, items, formatter) {
  container.innerHTML = "";
  for (const item of items) {
    const node = document.createElement("li");
    node.textContent = formatter(item);
    container.append(node);
  }
}

function toggleBusy(isBusy) {
  collectButton.disabled = isBusy;
  useCurrentTabButton.disabled = isBusy;
  siteUrlInput.disabled = isBusy;
  analysisLimitSelect.disabled = isBusy;
}

function setStatus(message, isGood = false) {
  statusNode.textContent = message;
  statusNode.classList.toggle("good", isGood);
}
