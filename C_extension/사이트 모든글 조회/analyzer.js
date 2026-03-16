import {
  collectPublicUrls,
  fetchTextWithTimeout,
  isLikelyContentUrl,
  isSameSite,
  normalizeSameSiteUrl,
  normalizeSiteUrl
} from "./collector.js";

const PAGE_ANALYSIS_DELAY_MS = 200;
const DEFAULT_ANALYSIS_LIMIT = 80;
const MAX_TOP_ITEMS = 12;
const MONEY_PAGE_THRESHOLD = 12;

const TITLE_STOP_WORDS = new Set([
  "the", "and", "for", "with", "from", "into", "that", "this", "your", "about",
  "after", "before", "best", "more", "most", "guide", "tips", "tip", "blog", "post",
  "word", "press", "워드프레스", "블로그", "가이드", "정리", "방법", "사용", "추천", "리뷰",
  "후기", "소개", "완벽", "최신", "초보", "실전"
]);

const CTA_PATTERNS = [
  /buy now/i, /shop now/i, /learn more/i, /start now/i, /get started/i, /try now/i,
  /sign up/i, /subscribe/i, /compare/i, /check price/i, /download/i, /무료/i, /지금/i,
  /바로/i, /확인/i, /신청/i, /구매/i, /비교/i, /할인/i, /추천/i, /상담/i, /체험/i
];

const TITLE_PATTERN_DEFS = [
  { key: "listicle", label: "숫자형", test: (title) => /\d/.test(title) },
  { key: "howTo", label: "방법형", test: (title) => /(how|guide|tips?|방법|가이드|노하우|전략|정리)/i.test(title) },
  { key: "comparison", label: "비교형", test: (title) => /(vs|versus|compare|comparison|비교|차이|장단점)/i.test(title) },
  { key: "review", label: "후기형", test: (title) => /(review|리뷰|후기|사용기|경험)/i.test(title) },
  { key: "recommendation", label: "추천형", test: (title) => /(best|top|추천|선정|랭킹|순위)/i.test(title) },
  { key: "question", label: "질문형", test: (title) => /(\?|왜|어떻게|무엇|what|why|how)/i.test(title) },
  { key: "problemSolving", label: "문제해결형", test: (title) => /(fix|solve|mistake|error|해결|오류|실수|주의|피하는)/i.test(title) },
  { key: "urgency", label: "즉시성형", test: (title) => /(now|today|202\d|즉시|지금|오늘|최신)/i.test(title) }
];

const COMMERCIAL_KEYWORD_RULES = [
  { label: "추천", weight: 3.4, pattern: /(추천|best|top pick|editor'?s pick)/i },
  { label: "비교", weight: 3.4, pattern: /(비교|vs|versus|compare|comparison)/i },
  { label: "후기", weight: 3.0, pattern: /(후기|리뷰|review|사용기|experience)/i },
  { label: "순위", weight: 2.8, pattern: /(순위|랭킹|top \d+|best \d+)/i },
  { label: "가격", weight: 3.2, pattern: /(가격|price|pricing|cost|요금)/i },
  { label: "할인", weight: 3.2, pattern: /(할인|coupon|쿠폰|deal|promo|sale)/i },
  { label: "가성비", weight: 3.0, pattern: /(가성비|value|budget|worth it)/i },
  { label: "장단점", weight: 2.7, pattern: /(장단점|pros and cons|advantages|disadvantages)/i },
  { label: "대안", weight: 2.6, pattern: /(대안|alternative|vs competitor|competitor)/i },
  { label: "초보 가이드", weight: 1.9, pattern: /(초보|beginner|starter|입문)/i },
  { label: "구매", weight: 3.3, pattern: /(구매|buy|shop|order)/i }
];

const TITLE_FORMULA_LIBRARY = [
  {
    key: "ranked_recommendation",
    label: "숫자 + 추천",
    template: "[숫자]개의 [대상] 추천: 고르는 기준까지",
    test: (patterns) => hasPattern(patterns, "listicle") && hasPattern(patterns, "recommendation")
  },
  {
    key: "comparison_decision",
    label: "비교 + 결론",
    template: "[대상 A] vs [대상 B]: 차이점과 추천 선택",
    test: (patterns) => hasPattern(patterns, "comparison")
  },
  {
    key: "review_pros_cons",
    label: "후기 + 장단점",
    template: "[제품/서비스] 후기: 장점, 단점, 추천 대상",
    test: (patterns) => hasPattern(patterns, "review")
  },
  {
    key: "howto_checklist",
    label: "방법 + 체크리스트",
    template: "[목표] 하는 방법: 단계별 체크리스트",
    test: (patterns) => hasPattern(patterns, "howTo")
  },
  {
    key: "problem_fix",
    label: "문제 + 해결",
    template: "[문제] 해결 방법과 피해야 할 실수",
    test: (patterns) => hasPattern(patterns, "problemSolving")
  },
  {
    key: "question_answer",
    label: "질문 + 답변",
    template: "[질문]에 대한 답: 바로 결론부터",
    test: (patterns) => hasPattern(patterns, "question")
  },
  {
    key: "urgent_update",
    label: "최신 + 요약",
    template: "[연도/최신] [주제] 핵심 요약",
    test: (patterns) => hasPattern(patterns, "urgency")
  },
  {
    key: "recommendation_basic",
    label: "추천 + 기준",
    template: "[대상] 추천: 선택 기준과 추천 순서",
    test: (patterns) => hasPattern(patterns, "recommendation")
  }
];

const AFFILIATE_HOST_PATTERNS = [
  /amzn\.to$/i, /amazon\./i, /coupang\.com$/i, /coupangpartners\.com$/i, /rakuten/i,
  /clickbank/i, /impact\.com$/i, /shareasale/i, /awin/i, /partnerize/i, /digistore24/i,
  /commission-junction/i, /linksynergy/i, /refersion/i
];

const AFFILIATE_QUERY_KEYS = [
  "ref", "aff", "affiliate", "aff_id", "utm_affiliate", "partner", "tag", "subid", "clickid"
];

const AD_HINTS = [
  { label: "Google AdSense", test: (text) => /adsbygoogle|pagead2\.googlesyndication/i.test(text) },
  { label: "DoubleClick", test: (text) => /doubleclick|googletagmanager|googleadservices/i.test(text) },
  { label: "Taboola", test: (text) => /taboola/i.test(text) },
  { label: "Outbrain", test: (text) => /outbrain/i.test(text) },
  { label: "Mediavine", test: (text) => /mediavine/i.test(text) },
  { label: "AdThrive", test: (text) => /adthrive|raptive/i.test(text) }
];

export async function runSiteBenchmark(siteUrl, options = {}, onProgress = () => {}) {
  const normalizedSiteUrl = normalizeSiteUrl(siteUrl);
  const collection = await collectPublicUrls(normalizedSiteUrl, onProgress);
  const collectedUrls = collection.urls;
  const analysisLimit = Math.max(1, Math.min(Number(options.analysisLimit) || DEFAULT_ANALYSIS_LIMIT, collectedUrls.length || DEFAULT_ANALYSIS_LIMIT));
  const prioritizedUrls = prioritizeUrls(collectedUrls, collection).slice(0, analysisLimit);
  const analyzedPosts = [];
  const errors = [...collection.errors];
  const notes = [...collection.notes];
  const collectedUrlSet = new Set(collectedUrls);

  if (collectedUrls.length > analysisLimit) {
    notes.push(`페이지 본문 분석은 상위 ${analysisLimit}개 URL만 수행했습니다. 전체 URL 목록은 계속 수집됩니다.`);
  }

  for (let index = 0; index < prioritizedUrls.length; index += 1) {
    const url = prioritizedUrls[index];
    onProgress(`페이지 분석 ${index + 1}/${prioritizedUrls.length}: ${url}`);

    try {
      const post = await analyzePostPage(url, normalizedSiteUrl, collectedUrlSet, collection);
      analyzedPosts.push(post);
    } catch (error) {
      errors.push(`${url}: ${error.message}`);
    }

    await delay(PAGE_ANALYSIS_DELAY_MS);
  }

  const inboundLinks = buildInboundLinkCounts(analyzedPosts);
  for (const post of analyzedPosts) {
    post.inboundInternalLinks = inboundLinks[post.url] || 0;
    post.popularityScore = computePopularityScore(post, collection);
    post.monetizationScore = computeMonetizationScore(post);
    post.moneyPageScore = computeMoneyPageScore(post);
    post.moneyPageType = classifyMoneyPageType(post);
    post.isMoneyPage = post.moneyPageScore >= MONEY_PAGE_THRESHOLD;
    post.moneyPageReasons = buildMoneyPageReasons(post);
  }

  const analytics = buildAnalytics(analyzedPosts, collection);

  return {
    siteUrl: normalizedSiteUrl,
    collection,
    posts: analyzedPosts,
    analytics,
    notes,
    errors,
    analyzedUrlCount: analyzedPosts.length,
    collectedUrlCount: collectedUrls.length,
    exportText: buildExportText(analyzedPosts),
    exportJson: buildExportJson(normalizedSiteUrl, analyzedPosts, collection, analytics, notes, errors)
  };
}

async function analyzePostPage(url, siteUrl, collectedUrlSet, collection) {
  const htmlText = await fetchTextWithTimeout(url, "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");
  const document = new DOMParser().parseFromString(htmlText, "text/html");
  const title = extractTitle(document);
  const description = extractDescription(document);
  const categories = extractTermTexts(document, ['a[rel~="category"]', ".cat-links a", ".post-categories a", '[property="article:section"]']);
  const tags = extractTermTexts(document, ['a[rel~="tag"]', ".tags-links a", ".post-tags a", ".entry-tags a"]);
  const titlePatterns = detectTitlePatterns(title);
  const monetizationSignals = detectMonetizationSignals(document, siteUrl);
  const outboundInternalUrls = extractCollectedInternalUrls(document, siteUrl, collectedUrlSet);
  const sourceSignals = collection.archiveSignals[url] || {};
  const sourceList = collection.urlSourceMap[url] || [];
  const commercialSignals = detectCommercialSignals(title, description, categories, tags);
  const titleFormula = detectTitleFormula(titlePatterns);

  return {
    url,
    title,
    titleLength: title.length,
    publishedAt: extractPublishedAt(document),
    description,
    categories,
    tags,
    titlePatterns,
    titleFormula,
    commercialKeywords: commercialSignals.keywords,
    commercialKeywordScore: commercialSignals.score,
    wordCount: countWords(getBodyText(document)),
    headingCount: document.querySelectorAll("h2, h3").length,
    listCount: document.querySelectorAll("ul, ol").length,
    tableCount: document.querySelectorAll("table").length,
    imageCount: document.querySelectorAll("img").length,
    outboundLinkCount: countOutboundLinks(document, siteUrl),
    outboundInternalUrls,
    internalLinkCount: outboundInternalUrls.length,
    sourceList,
    sourceCoverage: sourceList.length,
    archiveReferences: sourceSignals.references || 0,
    archiveRootReferences: sourceSignals.rootReferences || 0,
    popularWidgetHits: sourceSignals.popularityHints || 0,
    featuredHits: sourceSignals.featureHints || 0,
    affiliateLinkCount: monetizationSignals.affiliateLinkCount,
    affiliateHosts: monetizationSignals.affiliateHosts,
    ctaCount: monetizationSignals.ctaCount,
    adSignals: monetizationSignals.adSignals,
    newsletterSignals: monetizationSignals.newsletterSignals,
    leadMagnetSignals: monetizationSignals.leadMagnetSignals,
    monetizationLabels: monetizationSignals.labels
  };
}

function buildAnalytics(posts, collection) {
  const keywords = rankEntries(buildKeywordFrequency(posts), MAX_TOP_ITEMS);
  const commercialKeywords = buildCommercialKeywordRanking(posts);
  const categoryFrequency = rankEntries(buildFrequency(posts.flatMap((post) => post.categories)), MAX_TOP_ITEMS);
  const titlePatterns = buildTitlePatterns(posts);
  const titleFormulas = buildTitleFormulaLibrary(posts);
  const monetizationSummary = buildMonetizationSummary(posts);
  const moneyPages = buildMoneyPageList(posts);
  const opportunityScores = buildOpportunityScores(posts);
  const totalMoneyPageCount = posts.filter((post) => post.isMoneyPage).length;
  const summary = buildSummary(posts, collection, commercialKeywords, totalMoneyPageCount);
  const opportunities = buildOpportunities(summary, commercialKeywords, titleFormulas, monetizationSummary, opportunityScores);

  return {
    summary,
    keywords,
    commercialKeywords,
    categoryFrequency,
    titlePatterns,
    titleFormulas,
    monetizationSummary,
    moneyPages,
    opportunityScores,
    opportunities
  };
}

function buildSummary(posts, collection, commercialKeywords, totalMoneyPageCount) {
  const totalWords = posts.reduce((sum, post) => sum + post.wordCount, 0);
  return {
    collectedUrlCount: collection.urls.length,
    analyzedUrlCount: posts.length,
    avgWordCount: posts.length ? Math.round(totalWords / posts.length) : 0,
    affiliatePosts: posts.filter((post) => post.affiliateLinkCount > 0).length,
    adPosts: posts.filter((post) => post.adSignals.length > 0).length,
    ctaPosts: posts.filter((post) => post.ctaCount > 0).length,
    newsletterPosts: posts.filter((post) => post.newsletterSignals.length > 0).length,
    tableHeavyPosts: posts.filter((post) => post.tableCount > 0).length,
    moneyPageCount: totalMoneyPageCount,
    topCommercialKeyword: commercialKeywords[0]?.label || "",
    topCommercialKeywordScore: commercialKeywords[0]?.score || 0
  };
}

function buildKeywordFrequency(posts) {
  const counts = new Map();
  for (const post of posts) {
    for (const token of extractTitleTokens(post.title)) {
      counts.set(token, (counts.get(token) || 0) + 1);
    }
  }
  return counts;
}

function buildCommercialKeywordRanking(posts) {
  const aggregate = new Map();
  for (const post of posts) {
    for (const keyword of post.commercialKeywords) {
      const entry = aggregate.get(keyword.label) || { label: keyword.label, count: 0, weightedScore: 0, avgMoneySignals: 0 };
      entry.count += 1;
      entry.weightedScore += keyword.weight;
      entry.avgMoneySignals += post.monetizationScore;
      aggregate.set(keyword.label, entry);
    }
  }

  return [...aggregate.values()]
    .map((entry) => ({
      label: entry.label,
      count: entry.count,
      score: round((entry.weightedScore * 1.3) + (entry.avgMoneySignals / Math.max(entry.count, 1)))
    }))
    .sort((left, right) => right.score - left.score || right.count - left.count)
    .slice(0, MAX_TOP_ITEMS);
}

function buildTitlePatterns(posts) {
  const counts = new Map(TITLE_PATTERN_DEFS.map((definition) => [definition.label, 0]));
  for (const post of posts) {
    for (const pattern of post.titlePatterns) {
      counts.set(pattern.label, (counts.get(pattern.label) || 0) + 1);
    }
  }
  return rankEntries(counts, TITLE_PATTERN_DEFS.length);
}

function buildTitleFormulaLibrary(posts) {
  const library = new Map();

  for (const post of posts) {
    const formula = post.titleFormula;
    const entry = library.get(formula.key) || {
      key: formula.key,
      label: formula.label,
      template: formula.template,
      count: 0,
      avgMoneyPageScore: 0,
      examples: []
    };

    entry.count += 1;
    entry.avgMoneyPageScore += post.moneyPageScore || 0;
    if (entry.examples.length < 2) {
      entry.examples.push(post.title);
    }
    library.set(formula.key, entry);
  }

  return [...library.values()]
    .map((entry) => ({
      key: entry.key,
      label: entry.label,
      template: entry.template,
      count: entry.count,
      score: round((entry.avgMoneyPageScore / Math.max(entry.count, 1)) + entry.count),
      examples: entry.examples
    }))
    .sort((left, right) => right.score - left.score || right.count - left.count)
    .slice(0, MAX_TOP_ITEMS);
}

function buildMonetizationSummary(posts) {
  const counts = new Map();
  for (const post of posts) {
    for (const label of post.monetizationLabels) {
      counts.set(label, (counts.get(label) || 0) + 1);
    }
  }

  return {
    tactics: rankEntries(counts, MAX_TOP_ITEMS),
    topMoneyPages: posts
      .filter((post) => post.isMoneyPage)
      .slice()
      .sort((left, right) => right.moneyPageScore - left.moneyPageScore)
      .slice(0, MAX_TOP_ITEMS)
      .map((post) => ({
        title: post.title,
        url: post.url,
        moneyPageScore: round(post.moneyPageScore),
        labels: post.monetizationLabels
      }))
  };
}

function buildMoneyPageList(posts) {
  return posts
    .filter((post) => post.isMoneyPage)
    .slice()
    .sort((left, right) => right.moneyPageScore - left.moneyPageScore || right.popularityScore - left.popularityScore)
    .slice(0, MAX_TOP_ITEMS)
    .map((post) => ({
      title: post.title,
      url: post.url,
      moneyPageScore: round(post.moneyPageScore),
      moneyPageType: post.moneyPageType,
      commercialKeywordScore: round(post.commercialKeywordScore),
      monetizationScore: round(post.monetizationScore),
      reasons: post.moneyPageReasons
    }));
}

function buildOpportunityScores(posts) {
  const themes = new Map();

  for (const post of posts) {
    const labels = post.commercialKeywords.length > 0
      ? post.commercialKeywords.map((keyword) => keyword.label)
      : post.categories.slice(0, 1);

    for (const label of labels) {
      if (!label) {
        continue;
      }

      const entry = themes.get(label) || {
        label,
        count: 0,
        popularity: 0,
        monetization: 0,
        moneyPageScore: 0
      };

      entry.count += 1;
      entry.popularity += post.popularityScore;
      entry.monetization += post.monetizationScore;
      entry.moneyPageScore += post.moneyPageScore;
      themes.set(label, entry);
    }
  }

  return [...themes.values()]
    .map((entry) => {
      const avgPopularity = entry.popularity / Math.max(entry.count, 1);
      const avgMonetization = entry.monetization / Math.max(entry.count, 1);
      const avgMoneyPage = entry.moneyPageScore / Math.max(entry.count, 1);
      const scarcityBonus = Math.max(0, 4 - entry.count);

      return {
        label: entry.label,
        count: entry.count,
        score: round((avgMonetization * 1.8) + (avgMoneyPage * 1.3) + (avgPopularity * 0.8) + scarcityBonus),
        rationale: `노출 ${entry.count}개 · 평균 수익화 ${round(avgMonetization)} · 희소 보너스 ${scarcityBonus}`
      };
    })
    .sort((left, right) => right.score - left.score || left.count - right.count)
    .slice(0, MAX_TOP_ITEMS);
}

function buildOpportunities(summary, commercialKeywords, titleFormulas, monetizationSummary, opportunityScores) {
  const opportunities = [];

  if (commercialKeywords[0]) {
    opportunities.push(`상업성 키워드는 "${commercialKeywords[0].label}"가 가장 강합니다. 먼저 이 키워드가 붙은 글 구조와 CTA 위치를 벤치마킹하는 편이 좋습니다.`);
  }

  if (titleFormulas[0]) {
    opportunities.push(`제목 공식은 "${titleFormulas[0].label}"이 가장 유효합니다. 템플릿 "${titleFormulas[0].template}"를 기본 골격으로 쓰기 좋습니다.`);
  }

  if (monetizationSummary.tactics[0]) {
    opportunities.push(`가장 반복되는 수익화 장치는 "${monetizationSummary.tactics[0].label}"입니다. 같은 키워드라도 이 장치와 결합된 글이 전환형일 가능성이 높습니다.`);
  }

  if (opportunityScores[0]) {
    opportunities.push(`기회 점수 1위는 "${opportunityScores[0].label}"입니다. 노출 수는 적지만 수익 신호가 강해 우선 분석 대상으로 적합합니다.`);
  }

  if (summary.moneyPageCount > 0) {
    opportunities.push(`전체 분석 글 중 ${summary.moneyPageCount}개가 머니페이지 후보입니다. 이 집합의 공통 제목 패턴과 링크 구조를 먼저 따라가는 게 효율적입니다.`);
  }

  return opportunities.slice(0, 6);
}

function detectCommercialSignals(title, description, categories, tags) {
  const haystack = [title, description, ...categories, ...tags].filter(Boolean).join(" ");
  const keywords = [];
  let score = 0;

  for (const rule of COMMERCIAL_KEYWORD_RULES) {
    if (rule.pattern.test(haystack)) {
      keywords.push({ label: rule.label, weight: rule.weight });
      score += rule.weight;
    }
  }

  return {
    keywords,
    score: round(score)
  };
}

function detectTitlePatterns(title) {
  return TITLE_PATTERN_DEFS.filter((definition) => definition.test(title)).map((definition) => ({
    key: definition.key,
    label: definition.label
  }));
}

function detectTitleFormula(patterns) {
  for (const formula of TITLE_FORMULA_LIBRARY) {
    if (formula.test(patterns)) {
      return formula;
    }
  }

  return {
    key: "general_summary",
    label: "핵심 요약형",
    template: "[핵심 키워드] 완전 정리"
  };
}

function hasPattern(patterns, key) {
  return patterns.some((pattern) => pattern.key === key);
}

function buildPopularityReasons(post) {
  const reasons = [];

  if (post.popularWidgetHits > 0) {
    reasons.push(`인기 위젯 노출 ${post.popularWidgetHits}`);
  }
  if (post.archiveReferences > 1) {
    reasons.push(`목록 반복 노출 ${post.archiveReferences}`);
  }
  if (post.inboundInternalLinks > 0) {
    reasons.push(`내부 링크 유입 ${post.inboundInternalLinks}`);
  }
  if (post.sourceCoverage > 1) {
    reasons.push(`다중 소스 노출 ${post.sourceCoverage}`);
  }

  return reasons.length > 0 ? reasons : ["공개 노출 신호 제한적"];
}

function buildMoneyPageReasons(post) {
  const reasons = [];

  if (post.affiliateLinkCount > 0) {
    reasons.push(`제휴 링크 ${post.affiliateLinkCount}`);
  }
  if (post.ctaCount > 0) {
    reasons.push(`CTA ${post.ctaCount}`);
  }
  if (post.tableCount > 0) {
    reasons.push(`비교 표 ${post.tableCount}`);
  }
  if (post.commercialKeywords.length > 0) {
    reasons.push(`상업 키워드 ${post.commercialKeywords.map((keyword) => keyword.label).join(", ")}`);
  }
  if (post.moneyPageType) {
    reasons.push(post.moneyPageType);
  }

  return reasons;
}

function prioritizeUrls(urls, collection) {
  return urls.slice().sort((left, right) => scoreUrlPriority(right, collection) - scoreUrlPriority(left, collection));
}

function scoreUrlPriority(url, collection) {
  const archiveSignal = collection.archiveSignals[url] || {};
  const sourceCount = (collection.urlSourceMap[url] || []).length;

  return (
    (archiveSignal.references || 0) * 1.5 +
    (archiveSignal.rootReferences || 0) * 2 +
    (archiveSignal.popularityHints || 0) * 5 +
    (archiveSignal.featureHints || 0) * 3 +
    sourceCount * 2
  );
}

function computePopularityScore(post, collection) {
  const archiveSignal = collection.archiveSignals[post.url] || {};

  return (
    post.sourceCoverage * 2 +
    (archiveSignal.references || 0) * 1.5 +
    (archiveSignal.rootReferences || 0) * 2 +
    (archiveSignal.popularityHints || 0) * 6 +
    (archiveSignal.featureHints || 0) * 3 +
    (post.inboundInternalLinks || 0) * 1.25
  );
}

function computeMonetizationScore(post) {
  return (
    post.affiliateLinkCount * 3 +
    post.ctaCount * 1.5 +
    post.adSignals.length * 2 +
    post.newsletterSignals.length * 2 +
    post.tableCount
  );
}

function computeMoneyPageScore(post) {
  const comparisonBoost = hasPattern(post.titlePatterns, "comparison") ? 2.2 : 0;
  const reviewBoost = hasPattern(post.titlePatterns, "review") ? 1.8 : 0;
  const recommendationBoost = hasPattern(post.titlePatterns, "recommendation") ? 1.8 : 0;

  return (
    post.monetizationScore * 1.9 +
    post.commercialKeywordScore * 1.6 +
    comparisonBoost +
    reviewBoost +
    recommendationBoost +
    (post.tableCount > 0 ? 1.5 : 0) +
    (post.outboundLinkCount > 3 ? 1 : 0)
  );
}

function classifyMoneyPageType(post) {
  if (hasPattern(post.titlePatterns, "comparison")) {
    return "비교형 머니페이지";
  }
  if (hasPattern(post.titlePatterns, "review")) {
    return "후기형 머니페이지";
  }
  if (hasPattern(post.titlePatterns, "recommendation")) {
    return "추천형 머니페이지";
  }
  if (post.newsletterSignals.length > 0 || post.leadMagnetSignals.length > 0) {
    return "리드수집형 페이지";
  }
  if (post.adSignals.length > 0) {
    return "광고형 페이지";
  }

  return "전환형 콘텐츠";
}

function buildInboundLinkCounts(posts) {
  const counts = {};
  for (const post of posts) {
    for (const target of post.outboundInternalUrls) {
      counts[target] = (counts[target] || 0) + 1;
    }
  }
  return counts;
}

function buildExportText(posts) {
  const header = ["Popularity", "Monetization", "Commercial", "MoneyPage", "Type", "Title", "URL", "Categories", "Commercial Keywords"].join("\t");
  const rows = posts
    .slice()
    .sort((left, right) => right.moneyPageScore - left.moneyPageScore || right.popularityScore - left.popularityScore)
    .map((post) => [
      round(post.popularityScore),
      round(post.monetizationScore),
      round(post.commercialKeywordScore),
      round(post.moneyPageScore),
      sanitizeCell(post.moneyPageType),
      sanitizeCell(post.title),
      post.url,
      sanitizeCell(post.categories.join(", ")),
      sanitizeCell(post.commercialKeywords.map((keyword) => keyword.label).join(", "))
    ].join("\t"));

  return [header, ...rows].join("\n");
}

function buildExportJson(siteUrl, posts, collection, analytics, notes, errors) {
  return {
    siteUrl,
    createdAt: new Date().toISOString(),
    collectedUrlCount: collection.urls.length,
    analyzedUrlCount: posts.length,
    analytics,
    posts,
    notes,
    errors
  };
}

function detectMonetizationSignals(document, siteUrl) {
  const affiliateHosts = new Set();
  let affiliateLinkCount = 0;
  let ctaCount = 0;
  const adSignals = new Set();
  const newsletterSignals = new Set();
  const leadMagnetSignals = new Set();
  const labels = new Set();

  for (const anchor of document.querySelectorAll("a[href]")) {
    const href = anchor.getAttribute("href");
    let absoluteUrl;

    try {
      absoluteUrl = new URL(href, siteUrl);
    } catch (error) {
      continue;
    }

    if (!["http:", "https:"].includes(absoluteUrl.protocol)) {
      continue;
    }

    const isAffiliateHost = AFFILIATE_HOST_PATTERNS.some((pattern) => pattern.test(absoluteUrl.hostname));
    const hasAffiliateQuery = AFFILIATE_QUERY_KEYS.some((key) => absoluteUrl.searchParams.has(key));

    if (isAffiliateHost || hasAffiliateQuery) {
      affiliateLinkCount += 1;
      affiliateHosts.add(absoluteUrl.hostname);
      labels.add("제휴 링크");
    }

    const text = anchor.textContent?.trim() || "";
    if (CTA_PATTERNS.some((pattern) => pattern.test(text))) {
      ctaCount += 1;
      labels.add("CTA 버튼/링크");
    }
  }

  const pageText = `${document.documentElement.innerHTML}\n${document.body?.textContent || ""}`;
  for (const hint of AD_HINTS) {
    if (hint.test(pageText)) {
      adSignals.add(hint.label);
      labels.add("광고 스크립트");
    }
  }

  for (const form of document.querySelectorAll("form")) {
    const formText = form.textContent?.trim() || "";
    if (/(subscribe|newsletter|이메일|구독|뉴스레터)/i.test(formText)) {
      newsletterSignals.add("뉴스레터/구독");
      labels.add("리드 수집");
    }
    if (/(ebook|checklist|template|freebie|자료집|다운로드|전자책)/i.test(formText)) {
      leadMagnetSignals.add("리드 마그넷");
      labels.add("리드 마그넷");
    }
  }

  if (document.querySelector("table")) {
    labels.add("비교 표");
  }

  return {
    affiliateLinkCount,
    affiliateHosts: [...affiliateHosts].sort(),
    ctaCount,
    adSignals: [...adSignals].sort(),
    newsletterSignals: [...newsletterSignals].sort(),
    leadMagnetSignals: [...leadMagnetSignals].sort(),
    labels: [...labels].sort()
  };
}

function extractCollectedInternalUrls(document, siteUrl, collectedUrlSet) {
  const urls = new Set();

  for (const anchor of document.querySelectorAll("a[href]")) {
    const normalized = normalizeSameSiteUrl(anchor.getAttribute("href"), siteUrl);
    if (!normalized || !collectedUrlSet.has(normalized) || !isLikelyContentUrl(normalized, siteUrl)) {
      continue;
    }
    urls.add(normalized);
  }

  return [...urls];
}

function countOutboundLinks(document, siteUrl) {
  let count = 0;

  for (const anchor of document.querySelectorAll("a[href]")) {
    const href = anchor.getAttribute("href");
    let absoluteUrl;

    try {
      absoluteUrl = new URL(href, siteUrl);
    } catch (error) {
      continue;
    }

    if (["http:", "https:"].includes(absoluteUrl.protocol) && !isSameSite(absoluteUrl, siteUrl)) {
      count += 1;
    }
  }

  return count;
}

function extractTitle(document) {
  return [
    document.querySelector("h1.entry-title")?.textContent,
    document.querySelector("article h1")?.textContent,
    document.querySelector("main h1")?.textContent,
    document.querySelector("h1")?.textContent,
    document.querySelector("meta[property='og:title']")?.getAttribute("content"),
    document.title
  ].map((value) => (value || "").trim()).find(Boolean) || "(제목 없음)";
}

function extractDescription(document) {
  return [
    document.querySelector("meta[name='description']")?.getAttribute("content"),
    document.querySelector("meta[property='og:description']")?.getAttribute("content")
  ].map((value) => (value || "").trim()).find(Boolean) || "";
}

function extractPublishedAt(document) {
  const rawValue = [
    document.querySelector("time[datetime]")?.getAttribute("datetime"),
    document.querySelector("meta[property='article:published_time']")?.getAttribute("content"),
    document.querySelector("meta[name='article:published_time']")?.getAttribute("content"),
    document.querySelector("meta[name='date']")?.getAttribute("content"),
    extractDateFromJsonLd(document)
  ].find(Boolean);

  return rawValue ? rawValue.trim() : "";
}

function extractDateFromJsonLd(document) {
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    const text = script.textContent?.trim();
    if (!text) {
      continue;
    }

    try {
      const data = JSON.parse(text);
      const items = Array.isArray(data) ? data : [data];
      for (const item of items) {
        if (item?.datePublished) {
          return item.datePublished;
        }
      }
    } catch (error) {
      continue;
    }
  }

  return "";
}

function extractTermTexts(document, selectors) {
  const values = new Set();
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      const text = node.textContent?.trim();
      if (text) {
        values.add(text);
      }
    }
  }
  return [...values];
}

function getBodyText(document) {
  const container = document.querySelector("article") || document.querySelector("main") || document.body;
  return (container?.textContent || "").replace(/\s+/g, " ").trim();
}

function countWords(text) {
  if (!text) {
    return 0;
  }

  const tokens = text.match(/[A-Za-z0-9]+|[가-힣]{2,}/g);
  return tokens ? tokens.length : 0;
}

function extractTitleTokens(title) {
  const matches = title.toLowerCase().match(/[a-z0-9]+|[가-힣]{2,}/g) || [];
  return matches.filter((token) => token.length > 1 && !TITLE_STOP_WORDS.has(token));
}

function buildFrequency(items) {
  const counts = new Map();
  for (const item of items) {
    if (!item) {
      continue;
    }
    counts.set(item, (counts.get(item) || 0) + 1);
  }
  return counts;
}

function rankEntries(map, limit) {
  return [...map.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
    .slice(0, limit);
}

function sanitizeCell(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function round(value) {
  return Math.round(value * 10) / 10;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
