const originalBindElements = typeof window.bindElements === "function" ? window.bindElements : null;
const originalBindEvents = typeof window.bindEvents === "function" ? window.bindEvents : null;

window.bindElements = function bindElementsOverride() {
    originalBindElements?.();
    elements.gradePresetButtons = Array.from(document.querySelectorAll("[data-selection-preset]"));
    elements.gradeToggleButtons = Array.from(document.querySelectorAll("[data-profitability-toggle]"));
    elements.attackabilityToggleButtons = Array.from(document.querySelectorAll("[data-attackability-toggle]"));
    elements.runGradeSelectButton = document.getElementById("runGradeSelectButton");
    elements.gradeSelectSummary = document.getElementById("gradeSelectSummary");
    elements.exportTitleCsvButton = document.getElementById("exportTitleCsvButton");
    elements.utilityLauncherButtons = Array.from(document.querySelectorAll("[data-utility-open]"));
    elements.utilityDrawer = document.getElementById("utilityDrawer");
    elements.utilityDrawerBackdrop = document.getElementById("utilityDrawerBackdrop");
    elements.utilityDrawerClose = document.getElementById("utilityDrawerClose");
    elements.utilityTabButtons = Array.from(document.querySelectorAll("[data-utility-tab]"));
    elements.utilityPanels = Array.from(document.querySelectorAll("[data-utility-panel]"));
};

window.bindEvents = function bindEventsOverride() {
    originalBindEvents?.();

    elements.gradePresetButtons?.forEach((button) => {
        if (button.dataset.selectionPresetBound === "true") {
            return;
        }
        button.dataset.selectionPresetBound = "true";
        button.addEventListener("click", () => {
            applyGradePreset(button.dataset.selectionPreset || "");
        });
    });

    elements.utilityLauncherButtons?.forEach((button) => {
        if (button.dataset.utilityOpenBound === "true") {
            return;
        }
        button.dataset.utilityOpenBound = "true";
        button.addEventListener("click", () => {
            openUtilityDrawer(button.dataset.utilityOpen || "diagnostics");
        });
    });

    elements.utilityTabButtons?.forEach((button) => {
        if (button.dataset.utilityTabBound === "true") {
            return;
        }
        button.dataset.utilityTabBound = "true";
        button.addEventListener("click", () => {
            setUtilityDrawerTab(button.dataset.utilityTab || "diagnostics");
        });
    });

    if (elements.utilityDrawerBackdrop && elements.utilityDrawerBackdrop.dataset.boundClick !== "true") {
        elements.utilityDrawerBackdrop.dataset.boundClick = "true";
        elements.utilityDrawerBackdrop.addEventListener("click", closeUtilityDrawer);
    }
    if (elements.utilityDrawerClose && elements.utilityDrawerClose.dataset.boundClick !== "true") {
        elements.utilityDrawerClose.dataset.boundClick = "true";
        elements.utilityDrawerClose.addEventListener("click", closeUtilityDrawer);
    }
    if (!document.body.dataset.utilityDrawerKeybound) {
        document.body.dataset.utilityDrawerKeybound = "true";
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !elements.utilityDrawer?.hidden) {
                closeUtilityDrawer();
            }
        });
    }
};

function normalizeProfitabilityValue(grade) {
    const safeGrade = String(grade || "").trim().toUpperCase();
    return PROFITABILITY_ORDER.includes(safeGrade) ? safeGrade : "";
}

function normalizeProfitabilityList(grades) {
    const gradeSet = new Set(
        (grades || [])
            .map((grade) => normalizeProfitabilityValue(grade))
            .filter(Boolean),
    );
    return PROFITABILITY_ORDER.filter((grade) => gradeSet.has(grade));
}

function normalizeAttackabilityValue(grade) {
    const safeGrade = String(grade || "").trim();
    return ATTACKABILITY_ORDER.includes(safeGrade) ? safeGrade : "";
}

function normalizeAttackabilityList(grades) {
    const gradeSet = new Set(
        (grades || [])
            .map((grade) => normalizeAttackabilityValue(grade))
            .filter(Boolean),
    );
    return ATTACKABILITY_ORDER.filter((grade) => gradeSet.has(grade));
}

function getSelectedGradeFilters() {
    return normalizeProfitabilityList(state.selectGradeFilters);
}

function getSelectedAttackabilityFilters() {
    return normalizeAttackabilityList(state.selectAttackabilityFilters);
}

function hasExplicitAxisFilterSelection(profitabilityGrades, attackabilityGrades) {
    const normalizedProfitability = normalizeProfitabilityList(profitabilityGrades);
    const normalizedAttackability = normalizeAttackabilityList(attackabilityGrades);
    if (!normalizedProfitability.length || !normalizedAttackability.length) {
        return false;
    }
    return normalizedProfitability.length !== PROFITABILITY_ORDER.length
        || normalizedAttackability.length !== ATTACKABILITY_ORDER.length;
}

function buildGradeRunLabel(profitabilityGrades, attackabilityGrades) {
    const normalizedProfitability = normalizeProfitabilityList(profitabilityGrades);
    const normalizedAttackability = normalizeAttackabilityList(attackabilityGrades);
    if (!hasExplicitAxisFilterSelection(normalizedProfitability, normalizedAttackability)) {
        return "전체 조합";
    }
    return `수익성 ${normalizedProfitability.join(", ")} · 공략성 ${normalizedAttackability.join(", ")}`;
}

function updateGradeFilterUI() {
    const selectedProfitability = getSelectedGradeFilters();
    const selectedProfitabilitySet = new Set(selectedProfitability);
    const selectedAttackability = getSelectedAttackabilityFilters();
    const selectedAttackabilitySet = new Set(selectedAttackability);

    elements.gradeToggleButtons?.forEach((button) => {
        const grade = normalizeProfitabilityValue(button.dataset.profitabilityToggle || "");
        const isActive = selectedProfitabilitySet.has(grade);
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    elements.attackabilityToggleButtons?.forEach((button) => {
        const grade = normalizeAttackabilityValue(button.dataset.attackabilityToggle || "");
        const isActive = selectedAttackabilitySet.has(grade);
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });

    elements.gradePresetButtons?.forEach((button) => {
        const preset = GRADE_PRESET_MAP[button.dataset.selectionPreset || ""] || null;
        const presetProfitability = normalizeProfitabilityList(preset?.profitability || []);
        const presetAttackability = normalizeAttackabilityList(preset?.attackability || []);
        const isActive = presetProfitability.length === selectedProfitability.length
            && presetAttackability.length === selectedAttackability.length
            && presetProfitability.every((grade) => selectedProfitabilitySet.has(grade))
            && presetAttackability.every((grade) => selectedAttackabilitySet.has(grade));
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });

    if (elements.gradeSelectSummary) {
        elements.gradeSelectSummary.textContent = selectedProfitability.length && selectedAttackability.length
            ? buildGradeRunLabel(selectedProfitability, selectedAttackability)
            : "수익성과 공략성을 1개 이상 선택하세요.";
    }

    if (elements.runGradeSelectButton) {
        elements.runGradeSelectButton.disabled = state.isBusy
            || selectedProfitability.length === 0
            || selectedAttackability.length === 0;
    }
}

function applyGradePreset(presetKey) {
    const preset = GRADE_PRESET_MAP[presetKey] || GRADE_PRESET_MAP.all;
    state.selectGradeFilters = normalizeProfitabilityList(preset.profitability || []);
    state.selectAttackabilityFilters = normalizeAttackabilityList(preset.attackability || []);
    state.gradeSelectionTouched = true;
    updateGradeFilterUI();
    renderResults();
}

function toggleGradeFilter(grade) {
    const normalizedGrade = normalizeProfitabilityValue(grade);
    if (!normalizedGrade) {
        return;
    }

    const selectedSet = new Set(getSelectedGradeFilters());
    if (selectedSet.has(normalizedGrade)) {
        selectedSet.delete(normalizedGrade);
    } else {
        selectedSet.add(normalizedGrade);
    }
    state.selectGradeFilters = PROFITABILITY_ORDER.filter((item) => selectedSet.has(item));
    state.gradeSelectionTouched = true;
    updateGradeFilterUI();
    renderResults();
}

function toggleAttackabilityFilter(grade) {
    const normalizedGrade = normalizeAttackabilityValue(grade);
    if (!normalizedGrade) {
        return;
    }

    const selectedSet = new Set(getSelectedAttackabilityFilters());
    if (selectedSet.has(normalizedGrade)) {
        selectedSet.delete(normalizedGrade);
    } else {
        selectedSet.add(normalizedGrade);
    }
    state.selectAttackabilityFilters = ATTACKABILITY_ORDER.filter((item) => selectedSet.has(item));
    state.gradeSelectionTouched = true;
    updateGradeFilterUI();
    renderResults();
}

function resolveProfitabilityGrade(item) {
    return normalizeProfitabilityValue(item?.profitability_grade);
}

function resolveAttackabilityGrade(item) {
    return normalizeAttackabilityValue(item?.attackability_grade);
}

function resolveComboGrade(item) {
    const directCombo = String(item?.combo_grade || "").trim().toUpperCase();
    if (/^[ABCD][1-4]$/.test(directCombo)) {
        return directCombo;
    }
    const profitabilityGrade = resolveProfitabilityGrade(item);
    const attackabilityGrade = resolveAttackabilityGrade(item);
    return profitabilityGrade && attackabilityGrade
        ? `${profitabilityGrade}${attackabilityGrade}`
        : "";
}

function resolveGoldenBucket(item) {
    const bucket = String(item?.golden_bucket || "").trim().toLowerCase();
    return ["gold", "promising", "experimental", "hold"].includes(bucket) ? bucket : "";
}

function formatGoldenBucketLabel(bucket) {
    if (bucket === "gold") return "진짜 황금";
    if (bucket === "promising") return "유망";
    if (bucket === "experimental") return "실험";
    return "보류";
}

function renderProfitabilityBadge(grade) {
    const safeGrade = normalizeProfitabilityValue(grade) || "D";
    return `<span class="axis-badge profitability-${escapeHtml(safeGrade.toLowerCase())}">${escapeHtml(safeGrade)}</span>`;
}

function renderAttackabilityBadge(grade) {
    const safeGrade = normalizeAttackabilityValue(grade) || "4";
    return `<span class="axis-badge attackability-${escapeHtml(safeGrade)}">${escapeHtml(safeGrade)}</span>`;
}

function renderComboBadge(comboGrade) {
    const safeCombo = String(comboGrade || "-").trim().toUpperCase() || "-";
    const tone = /^[ABCD][1-4]$/.test(safeCombo) ? safeCombo.charAt(0).toLowerCase() : "d";
    return `<span class="combo-badge combo-${escapeHtml(tone)}">${escapeHtml(safeCombo)}</span>`;
}

function renderGoldenBucketPill(bucket) {
    const safeBucket = resolveGoldenBucket({ golden_bucket: bucket }) || "hold";
    return `<span class="bucket-pill ${escapeHtml(safeBucket)}">${escapeHtml(formatGoldenBucketLabel(safeBucket))}</span>`;
}

function renderAxisScoreCell(badgeHtml, scoreValue) {
    return `
        <div class="axis-score-cell">
            ${badgeHtml}
            <strong>${escapeHtml(formatNumber(scoreValue))}</strong>
        </div>
    `;
}

function runThroughGradeSelect(allowedGrades, allowedAttackabilityGrades) {
    return runSelectStage({
        allowedProfitabilityGrades: allowedGrades,
        allowedAttackabilityGrades,
    });
}

function getForwardSelectOptions() {
    if (!state.gradeSelectionTouched) {
        return {};
    }

    const allowedProfitabilityGrades = getSelectedGradeFilters();
    const allowedAttackabilityGrades = getSelectedAttackabilityFilters();
    if (!allowedProfitabilityGrades.length || !allowedAttackabilityGrades.length) {
        return {};
    }
    return hasExplicitAxisFilterSelection(allowedProfitabilityGrades, allowedAttackabilityGrades)
        ? { allowedProfitabilityGrades, allowedAttackabilityGrades }
        : {};
}

function hasMatchingSelectionProfile(allowedProfitabilityGrades, allowedAttackabilityGrades) {
    const normalizedProfitability = normalizeProfitabilityList(allowedProfitabilityGrades || []);
    const normalizedAttackability = normalizeAttackabilityList(allowedAttackabilityGrades || []);
    const profile = state.results.selected?.selection_profile || null;

    if (!normalizedProfitability.length && !normalizedAttackability.length) {
        return !profile || profile.mode === "default" || profile.mode !== "combo_filter";
    }

    if (!hasExplicitAxisFilterSelection(normalizedProfitability, normalizedAttackability)) {
        return !profile || profile.mode === "default" || profile.mode !== "combo_filter";
    }

    const profileProfitability = normalizeProfitabilityList(profile?.allowed_profitability_grades || []);
    const profileAttackability = normalizeAttackabilityList(profile?.allowed_attackability_grades || []);
    return profile?.mode === "combo_filter"
        && profileProfitability.length === normalizedProfitability.length
        && profileAttackability.length === normalizedAttackability.length
        && normalizedProfitability.every((grade) => profileProfitability.includes(grade))
        && normalizedAttackability.every((grade) => profileAttackability.includes(grade));
}

async function runSelectStage(options = {}) {
    if (!state.results.analyzed?.analyzed_keywords?.length) {
        await runAnalyzeStage();
    } else if (state.stageStatus.analyzed.state === "cancelled") {
        addLog(`중단 직전까지 분석된 ${countItems(state.results.analyzed.analyzed_keywords)}건으로 선별을 이어갑니다.`);
    }

    const allowedProfitabilityGrades = normalizeProfitabilityList(options.allowedProfitabilityGrades || []);
    const allowedAttackabilityGrades = normalizeAttackabilityList(options.allowedAttackabilityGrades || []);
    const hasExplicitFilters = hasExplicitAxisFilterSelection(
        allowedProfitabilityGrades,
        allowedAttackabilityGrades,
    );
    const analyzedKeywords = state.results.analyzed?.analyzed_keywords || [];
    const selectionCandidates = hasExplicitFilters
        ? analyzedKeywords.filter((item) => (
            allowedProfitabilityGrades.includes(resolveProfitabilityGrade(item))
            && allowedAttackabilityGrades.includes(resolveAttackabilityGrade(item))
        ))
        : analyzedKeywords;

    if (!selectionCandidates.length) {
        if (hasExplicitFilters) {
            throw new Error(
                `선택한 조합(수익성 ${allowedProfitabilityGrades.join(", ")} · 공략성 ${allowedAttackabilityGrades.join(", ")})에 맞는 분석 결과가 없습니다.`,
            );
        }
        throw new Error("선별할 분석 결과가 없습니다.");
    }

    addLog(
        hasExplicitFilters
            ? `선별 시작: 수익성 ${allowedProfitabilityGrades.join(", ")} · 공략성 ${allowedAttackabilityGrades.join(", ")} ${countItems(selectionCandidates)}건에 조합 기준을 적용합니다.`
            : "선별 시작: 기본 골든 후보 규칙(진짜 황금 + 유망 조합)을 적용합니다.",
    );
    clearStageAndDownstream("selected");
    const result = await executeStage({
        stageKey: "selected",
        endpoint: "/select",
        inputData: {
            analyzed_keywords: selectionCandidates,
            select_options: hasExplicitFilters
                ? {
                    allowed_profitability_grades: allowedProfitabilityGrades,
                    allowed_attackability_grades: allowedAttackabilityGrades,
                    mode: "combo_filter",
                }
                : {},
        },
    });

    state.results.selected = {
        ...result,
        selection_profile: {
            mode: hasExplicitFilters ? "combo_filter" : "default",
            allowed_profitability_grades: allowedProfitabilityGrades,
            allowed_attackability_grades: allowedAttackabilityGrades,
            candidate_count: selectionCandidates.length,
        },
    };
    addLog(
        hasExplicitFilters
            ? `선별 완료 (${buildGradeRunLabel(allowedProfitabilityGrades, allowedAttackabilityGrades)}): ${countItems(result.selected_keywords)}건`
            : `선별 완료: ${countItems(result.selected_keywords)}건`,
        "success",
    );
    renderAll();
    return state.results.selected;
}

async function runTitleStage() {
    const forwardSelectOptions = getForwardSelectOptions();
    if (
        !state.results.selected?.selected_keywords?.length
        || !hasMatchingSelectionProfile(
            forwardSelectOptions.allowedProfitabilityGrades || [],
            forwardSelectOptions.allowedAttackabilityGrades || [],
        )
    ) {
        await runSelectStage(forwardSelectOptions);
    }

    const titleOptions = buildTitleOptions();
    if (state.stageStatus.selected.state === "cancelled") {
        addLog(`중단 직전까지 선별된 ${countItems(state.results.selected?.selected_keywords)}건으로 제목 생성을 이어갑니다.`);
    }
    addLog(
        titleOptions.mode === "ai"
            ? `제목 생성 시작: ${buildTitleRunSummary(titleOptions)}`
            : "제목 생성 시작: template 규칙 기반 제목을 생성합니다.",
    );
    clearStageAndDownstream("titled");
    const result = await executeStage({
        stageKey: "titled",
        endpoint: "/generate-title",
        inputData: {
            selected_keywords: state.results.selected?.selected_keywords || [],
            keyword_clusters: state.results.selected?.keyword_clusters || [],
            longtail_suggestions: state.results.selected?.longtail_suggestions || [],
            analyzed_keywords: state.results.analyzed?.analyzed_keywords || [],
            title_options: titleOptions,
        },
    });

    state.results.titled = result;
    addLog(`제목 생성 완료: ${countItems(result.generated_titles)}세트`, "success");
    renderAll();
    return result;
}

function buildLongtailAnalyzerOptions() {
    const analyzeOptions = withAnalyzeKeywordStats({});
    const options = {};
    if (typeof analyzeOptions.keyword_stats_text === "string" && analyzeOptions.keyword_stats_text.trim()) {
        options.keyword_stats_text = analyzeOptions.keyword_stats_text.trim();
    }
    if (analyzeOptions.keywordmaster_benchmark) {
        options.keywordmaster_benchmark = analyzeOptions.keywordmaster_benchmark;
    }
    return options;
}

async function runLongtailVerification() {
    const selectedResult = state.results.selected || {};
    const selectedKeywords = Array.isArray(selectedResult.selected_keywords)
        ? selectedResult.selected_keywords
        : [];
    if (!selectedKeywords.length) {
        throw new Error("선별 결과가 없습니다. 먼저 선별을 실행해 주세요.");
    }

    const longtailSuggestions = Array.isArray(selectedResult.longtail_suggestions)
        ? selectedResult.longtail_suggestions
        : [];
    addLog(
        longtailSuggestions.length
            ? `롱테일 검증 시작: 제안 ${countItems(longtailSuggestions)}건을 다시 분석합니다.`
            : "롱테일 검증 시작: 선별 결과에서 새 롱테일 후보를 계산하고 분석합니다.",
    );

    const response = await postModule("/verify-longtail", {
        selected_keywords: selectedKeywords,
        keyword_clusters: Array.isArray(selectedResult.keyword_clusters) ? selectedResult.keyword_clusters : [],
        longtail_suggestions: longtailSuggestions,
        analyzer_options: buildLongtailAnalyzerOptions(),
    });
    const result = response?.result || {};
    const verifiedSuggestions = Array.isArray(result.verified_longtail_suggestions)
        ? result.verified_longtail_suggestions
        : [];
    const summary = result.longtail_verification_summary || {};

    state.results.selected = {
        ...selectedResult,
        longtail_suggestions: verifiedSuggestions,
        longtail_summary: summary,
        verified_longtail_keywords: Array.isArray(result.verified_longtail_keywords)
            ? result.verified_longtail_keywords
            : [],
        longtail_verified_at: new Date().toISOString(),
    };
    addLog(
        `롱테일 검증 완료: 통과 ${Number(summary.pass_count || 0)}건 · 검토 ${Number(summary.review_count || 0)}건 · 보류 ${Number(summary.fail_count || 0)}건`,
        "success",
    );
    renderAll();
    return state.results.selected;
}

function applyAnalyzedFilters(items) {
    const filters = getAnalyzedFilters();
    const selectedProfitability = new Set(getSelectedGradeFilters());
    const selectedAttackability = new Set(getSelectedAttackabilityFilters());
    const query = String(filters.query || "").trim().toLowerCase();
    const minScore = coerceFilterNumber(filters.minScore);
    const minPcSearch = coerceFilterNumber(filters.minPcSearch);
    const minMoSearch = coerceFilterNumber(filters.minMoSearch);
    const minTotalSearch = coerceFilterNumber(filters.minTotalSearch ?? filters.minVolume);
    const maxTotalSearch = coerceFilterNumber(filters.maxTotalSearch);
    const minBlog = coerceFilterNumber(filters.minBlog);
    const minPcClicks = coerceFilterNumber(filters.minPcClicks);
    const minMoClicks = coerceFilterNumber(filters.minMoClicks);
    const minTotalClicks = coerceFilterNumber(filters.minTotalClicks);
    const minCpc = coerceFilterNumber(filters.minCpc);
    const minBid1 = coerceFilterNumber(filters.minBid1 ?? filters.minBid);
    const minBid2 = coerceFilterNumber(filters.minBid2);
    const minBid3 = coerceFilterNumber(filters.minBid3);
    const maxCompetition = coerceFilterNumber(filters.maxCompetition);
    const priority = String(filters.priority || "all");
    const measured = String(filters.measured || "all");

    return (items || []).filter((item) => {
        if (selectedProfitability.size && !selectedProfitability.has(resolveProfitabilityGrade(item))) {
            return false;
        }
        if (selectedAttackability.size && !selectedAttackability.has(resolveAttackabilityGrade(item))) {
            return false;
        }
        const keyword = String(item.keyword || "");
        if (query && !keyword.toLowerCase().includes(query)) {
            return false;
        }
        if (priority !== "all" && String(item.priority || "") !== priority) {
            return false;
        }
        if (measured === "measured" && !isMeasuredItem(item)) {
            return false;
        }
        if (measured === "estimated" && isMeasuredItem(item)) {
            return false;
        }
        if (minScore !== null && Number(item.score || 0) < minScore) {
            return false;
        }
        if (minPcSearch !== null && Number(item.metrics?.pc_searches || 0) < minPcSearch) {
            return false;
        }
        if (minMoSearch !== null && Number(item.metrics?.mobile_searches || 0) < minMoSearch) {
            return false;
        }
        if (minTotalSearch !== null && Number(item.metrics?.volume || 0) < minTotalSearch) {
            return false;
        }
        if (maxTotalSearch !== null && Number(item.metrics?.volume || 0) > maxTotalSearch) {
            return false;
        }
        if (minBlog !== null && Number(item.metrics?.blog_results || 0) < minBlog) {
            return false;
        }
        if (minPcClicks !== null && Number(item.metrics?.pc_clicks || 0) < minPcClicks) {
            return false;
        }
        if (minMoClicks !== null && Number(item.metrics?.mobile_clicks || 0) < minMoClicks) {
            return false;
        }
        if (minTotalClicks !== null && Number(item.metrics?.total_clicks || 0) < minTotalClicks) {
            return false;
        }
        if (minCpc !== null && Number(item.metrics?.cpc || 0) < minCpc) {
            return false;
        }
        if (minBid1 !== null && Number(item.metrics?.bid || 0) < minBid1) {
            return false;
        }
        if (minBid2 !== null && Number(item.metrics?.bid_2 || 0) < minBid2) {
            return false;
        }
        if (minBid3 !== null && Number(item.metrics?.bid_3 || 0) < minBid3) {
            return false;
        }
        if (maxCompetition !== null && Number(item.metrics?.competition || 0) > maxCompetition) {
            return false;
        }
        return true;
    });
}

function isGoldenCandidate(item) {
    return ["gold", "promising"].includes(resolveGoldenBucket(item));
}

function getQuickCandidateLabel() {
    return "황금 후보";
}

function summarizeProfitabilityCounts(items) {
    const counts = new Map(PROFITABILITY_ORDER.map((grade) => [grade, 0]));
    (items || []).forEach((item) => {
        const grade = resolveProfitabilityGrade(item);
        if (grade) {
            counts.set(grade, (counts.get(grade) || 0) + 1);
        }
    });
    return PROFITABILITY_ORDER.map((grade) => ({ grade, count: counts.get(grade) || 0 }));
}

function summarizeAttackabilityCounts(items) {
    const counts = new Map(ATTACKABILITY_ORDER.map((grade) => [grade, 0]));
    (items || []).forEach((item) => {
        const grade = resolveAttackabilityGrade(item);
        if (grade) {
            counts.set(grade, (counts.get(grade) || 0) + 1);
        }
    });
    return ATTACKABILITY_ORDER.map((grade) => ({ grade, count: counts.get(grade) || 0 }));
}

function countItemsByAxisSelections(items, profitabilityGrades, attackabilityGrades) {
    const allowedProfitability = new Set(normalizeProfitabilityList(profitabilityGrades));
    const allowedAttackability = new Set(normalizeAttackabilityList(attackabilityGrades));
    return (items || []).filter((item) => (
        allowedProfitability.has(resolveProfitabilityGrade(item))
        && allowedAttackability.has(resolveAttackabilityGrade(item))
    )).length;
}

function findPreservedNode(attributeName, key) {
    return Array.from(document.querySelectorAll(`[${attributeName}]`))
        .find((node) => node.getAttribute(attributeName) === key) || null;
}

function captureResultsDomState() {
    const scrollingElement = document.scrollingElement || document.documentElement;
    return {
        pageScrollTop: scrollingElement ? scrollingElement.scrollTop : 0,
        scrollContainers: Array.from(document.querySelectorAll("[data-preserve-scroll-key]")).map((node) => ({
            key: node.getAttribute("data-preserve-scroll-key") || "",
            scrollTop: node.scrollTop,
            scrollLeft: node.scrollLeft,
            wasNearBottom: Math.abs(node.scrollHeight - node.clientHeight - node.scrollTop) <= 24,
        })).filter((entry) => entry.key),
        detailStates: Array.from(document.querySelectorAll("details[data-preserve-open-key]")).map((node) => ({
            key: node.getAttribute("data-preserve-open-key") || "",
            open: Boolean(node.open),
        })).filter((entry) => entry.key),
    };
}

function restoreResultsDomState(snapshot) {
    if (!snapshot) {
        return;
    }

    snapshot.detailStates.forEach((entry) => {
        const detailNode = findPreservedNode("data-preserve-open-key", entry.key);
        if (detailNode instanceof HTMLDetailsElement) {
            detailNode.open = entry.open;
        }
    });

    const scrollingElement = document.scrollingElement || document.documentElement;
    window.requestAnimationFrame(() => {
        snapshot.scrollContainers.forEach((entry) => {
            const container = findPreservedNode("data-preserve-scroll-key", entry.key);
            if (!(container instanceof HTMLElement)) {
                return;
            }

            const maxScrollTop = Math.max(0, container.scrollHeight - container.clientHeight);
            container.scrollTop = entry.wasNearBottom
                ? maxScrollTop
                : Math.min(entry.scrollTop, maxScrollTop);
            container.scrollLeft = entry.scrollLeft;
        });

        if (scrollingElement) {
            scrollingElement.scrollTop = snapshot.pageScrollTop;
        }
    });
}

function getUtilityDrawerTab() {
    const safeTab = String(state.utilityDrawerTab || "").trim();
    return ["diagnostics", "logs"].includes(safeTab) ? safeTab : "diagnostics";
}

function setUtilityDrawerTab(tabKey) {
    const safeTab = ["diagnostics", "logs"].includes(String(tabKey || "").trim())
        ? String(tabKey || "").trim()
        : "diagnostics";
    state.utilityDrawerTab = safeTab;
    elements.utilityTabButtons?.forEach((button) => {
        const active = (button.dataset.utilityTab || "") === safeTab;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    elements.utilityPanels?.forEach((panel) => {
        panel.hidden = (panel.dataset.utilityPanel || "") !== safeTab;
    });
    elements.utilityLauncherButtons?.forEach((button) => {
        const active = (button.dataset.utilityOpen || "") === safeTab && !elements.utilityDrawer?.hidden;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
    });
}

function openUtilityDrawer(tabKey = "diagnostics") {
    if (!elements.utilityDrawer) {
        return;
    }
    elements.utilityDrawer.hidden = false;
    document.body.classList.add("utility-drawer-open");
    setUtilityDrawerTab(tabKey);
}

function closeUtilityDrawer() {
    if (!elements.utilityDrawer) {
        return;
    }
    elements.utilityDrawer.hidden = true;
    document.body.classList.remove("utility-drawer-open");
    elements.utilityLauncherButtons?.forEach((button) => {
        button.classList.remove("active");
        button.setAttribute("aria-pressed", "false");
    });
}

function isBusySafeButton(button) {
    return Boolean(
        button?.matches?.("[data-selection-preset]")
        || button?.matches?.("[data-profitability-toggle]")
        || button?.matches?.("[data-attackability-toggle]")
        || button?.matches?.("[data-utility-open]")
        || button?.matches?.("[data-utility-tab]")
        || button?.matches?.("#utilityDrawerClose")
        || button?.matches?.("#utilityDrawerBackdrop")
        || button?.matches?.("[data-inline-action='toggle_analysis_grade']")
        || button?.matches?.("[data-inline-action='toggle_analysis_attackability']")
        || button?.matches?.("[data-inline-action='apply_analysis_grade_preset']")
        || button?.matches?.("[data-inline-action='reset_analyzed_filters']"),
    );
}

function syncBusyButtons() {
    elements.actionButtons.forEach((button) => {
        if (button === elements.stopStreamButton) {
            return;
        }
        if (isBusySafeButton(button)) {
            button.disabled = false;
            return;
        }
        button.disabled = state.isBusy;
    });
    if (typeof updateStopButtonState === "function") {
        updateStopButtonState();
    }
}

function cancelActiveStream() {
    if (state.requestAbortController) {
        if (state.requestAbortRequested) {
            return;
        }
        state.requestAbortRequested = true;
        addLog("현재 작업 중지를 요청했습니다. 지금까지 받은 결과는 유지됩니다.", "info");
        if (typeof updateStopButtonState === "function") {
            updateStopButtonState();
        }
        state.requestAbortController.abort("user_cancelled");
        renderAll();
        return;
    }

    if (!state.streamAbortController || state.streamAbortRequested) {
        return;
    }
    state.streamAbortRequested = true;
    addLog("실시간 확장/분석 중지를 요청했습니다. 지금까지 받은 결과는 유지됩니다.", "info");
    if (typeof updateStopButtonState === "function") {
        updateStopButtonState();
    }
    state.streamAbortController.abort("user_cancelled");
    renderAll();
}

function renderAnalyzedGradeBoard(items, visibleItems = null) {
    const profitabilityCounts = summarizeProfitabilityCounts(items);
    const attackabilityCounts = summarizeAttackabilityCounts(items);
    const selectedProfitability = getSelectedGradeFilters();
    const selectedAttackability = getSelectedAttackabilityFilters();
    const selectedProfitabilitySet = new Set(selectedProfitability);
    const selectedAttackabilitySet = new Set(selectedAttackability);
    const selectedCount = Array.isArray(visibleItems)
        ? countItems(visibleItems)
        : countItemsByAxisSelections(items, selectedProfitability, selectedAttackability);
    const hasExplicitFilters = hasExplicitAxisFilterSelection(selectedProfitability, selectedAttackability);
    const goldenPreset = GRADE_PRESET_MAP.golden_candidate;
    const goldenPresetActive = selectedProfitability.length === goldenPreset.profitability.length
        && selectedAttackability.length === goldenPreset.attackability.length
        && goldenPreset.profitability.every((grade) => selectedProfitabilitySet.has(grade))
        && goldenPreset.attackability.every((grade) => selectedAttackabilitySet.has(grade));

    return `
        <div class="analysis-grade-board">
            <div class="analysis-grade-head">
                <strong>2축 개수 및 즉시 필터</strong>
                <span>${escapeHtml(
                    hasExplicitFilters
                        ? `${buildGradeRunLabel(selectedProfitability, selectedAttackability)} ${selectedCount}건이 현재 테이블에 반영됩니다.`
                        : `전체 조합 ${countItems(items)}건이 현재 테이블에 반영되고 있습니다.`,
                )}</span>
            </div>
            <div class="analysis-grade-group">
                <span class="analysis-grade-group-label">수익성</span>
                <div class="analysis-grade-strip">
                    ${profitabilityCounts.map(({ grade, count }) => `
                        <button
                            type="button"
                            class="ghost-chip grade-toggle-chip analysis-grade-chip${selectedProfitabilitySet.has(grade) ? " active" : ""}"
                            data-inline-action="toggle_analysis_grade"
                            data-grade-toggle="${escapeHtml(grade)}"
                            aria-pressed="${selectedProfitabilitySet.has(grade) ? "true" : "false"}"
                        >
                            ${renderProfitabilityBadge(grade)}
                            <span class="analysis-grade-chip-copy">
                                <strong>${escapeHtml(grade)}</strong>
                                <span>${escapeHtml(`${formatNumber(count)}건`)}</span>
                            </span>
                        </button>
                    `).join("")}
                </div>
            </div>
            <div class="analysis-grade-group">
                <span class="analysis-grade-group-label">공략성</span>
                <div class="analysis-grade-strip">
                    ${attackabilityCounts.map(({ grade, count }) => `
                        <button
                            type="button"
                            class="ghost-chip grade-toggle-chip analysis-grade-chip${selectedAttackabilitySet.has(grade) ? " active" : ""}"
                            data-inline-action="toggle_analysis_attackability"
                            data-attackability-toggle="${escapeHtml(grade)}"
                            aria-pressed="${selectedAttackabilitySet.has(grade) ? "true" : "false"}"
                        >
                            ${renderAttackabilityBadge(grade)}
                            <span class="analysis-grade-chip-copy">
                                <strong>${escapeHtml(grade)}</strong>
                                <span>${escapeHtml(`${formatNumber(count)}건`)}</span>
                            </span>
                        </button>
                    `).join("")}
                </div>
            </div>
            <div class="analysis-grade-actions">
                <button type="button" class="ghost-chip${!hasExplicitFilters ? " active" : ""}" data-inline-action="apply_analysis_grade_preset" data-grade-preset="all">전체</button>
                <button type="button" class="ghost-chip${goldenPresetActive ? " active" : ""}" data-inline-action="apply_analysis_grade_preset" data-grade-preset="golden_candidate">골든 후보</button>
                <button type="button" class="inline-action-btn analysis-grade-run" data-inline-action="run_analysis_grade_select" ${selectedCount > 0 ? "" : "disabled"}>선택 조합 선별 실행</button>
            </div>
        </div>
    `;
}

function renderAnalyzedList(items) {
    const filters = getAnalyzedFilters();
    const filteredItems = applyAnalyzedFilters(items);
    const measuredCount = filteredItems.filter(isMeasuredItem).length;
    const goldenCount = filteredItems.filter(isGoldenCandidate).length;
    const trueGoldCount = filteredItems.filter((item) => resolveGoldenBucket(item) === "gold").length;
    const typeCount = new Set(filteredItems.map((item) => String(item.type || "").trim()).filter(Boolean)).size;
    const rows = filteredItems.map((item) => `
        <tr class="${isMeasuredItem(item) ? "measured-row" : "estimated-row"}">
            <td>${renderAnalysisKeywordCell(item)}</td>
            <td>${renderAxisScoreCell(renderProfitabilityBadge(resolveProfitabilityGrade(item)), item.profitability_score)}</td>
            <td>${renderAxisScoreCell(renderAttackabilityBadge(resolveAttackabilityGrade(item)), item.attackability_score)}</td>
            <td>${renderComboBadge(resolveComboGrade(item))}</td>
            <td>${renderGoldenBucketPill(resolveGoldenBucket(item))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.score))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.volume))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.blog_results))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.total_clicks))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.cpc))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.opportunity))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.competition))}</td>
            <td>${renderAnalysisSourceCell(item)}</td>
        </tr>
    `).join("");

    return `
        <div class="analysis-console">
            <div class="analysis-summary-strip">
                <div class="collector-stat-card">
                    <span>표시 키워드</span>
                    <strong>${escapeHtml(String(filteredItems.length))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>실측</span>
                    <strong>${escapeHtml(String(measuredCount))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>${escapeHtml(getQuickCandidateLabel())}</span>
                    <strong>${escapeHtml(String(goldenCount))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>진짜 황금</span>
                    <strong>${escapeHtml(String(trueGoldCount))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>출처 유형</span>
                    <strong>${escapeHtml(String(typeCount))}</strong>
                </div>
            </div>
            <div class="analysis-filter-tip">
                <strong>축 해석</strong>
                <span>수익성은 CPC, 클릭 잠재력, 검색량을 함께 보고, 공략성은 opportunity, 희소성, 경쟁 강도를 함께 반영합니다.</span>
            </div>
            <div class="analysis-filter-tip">
                <strong>골든 기준</strong>
                <span>진짜 황금은 A1, A2, B1 조합입니다. 기본 선별은 진짜 황금과 유망 조합을 함께 잡고, 표에서 직접 원하는 축 조합만 다시 선별할 수 있습니다.</span>
            </div>
            ${renderAnalyzedGradeBoard(items, filteredItems)}
            <div class="analysis-filter-stack">
                <div class="analysis-filter-row primary">
                    <input class="analysis-filter-input" type="search" data-analyzed-filter="query" value="${escapeHtml(filters.query)}" placeholder="키워드 검색.." />
                    <select class="analysis-filter-select" data-analyzed-filter="priority">
                        <option value="all"${filters.priority === "all" ? " selected" : ""}>우선순위 전체</option>
                        <option value="high"${filters.priority === "high" ? " selected" : ""}>상</option>
                        <option value="medium"${filters.priority === "medium" ? " selected" : ""}>중</option>
                        <option value="low"${filters.priority === "low" ? " selected" : ""}>하</option>
                    </select>
                    <select class="analysis-filter-select" data-analyzed-filter="measured">
                        <option value="all"${filters.measured === "all" ? " selected" : ""}>실측/추정 전체</option>
                        <option value="measured"${filters.measured === "measured" ? " selected" : ""}>실측만</option>
                        <option value="estimated"${filters.measured === "estimated" ? " selected" : ""}>추정만</option>
                    </select>
                    <button type="button" class="ghost-chip" data-inline-action="reset_analyzed_filters">필터 초기화</button>
                    <span class="analysis-filter-summary">표시 ${filteredItems.length} / 전체 ${countItems(items)}건</span>
                </div>
                <div class="analysis-filter-row metrics">
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minPcSearch" value="${escapeHtml(filters.minPcSearch)}" placeholder="PC조회수 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minMoSearch" value="${escapeHtml(filters.minMoSearch)}" placeholder="MO조회수 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minTotalSearch" value="${escapeHtml(filters.minTotalSearch)}" placeholder="총검색량 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="maxTotalSearch" value="${escapeHtml(filters.maxTotalSearch)}" placeholder="총검색량 이하" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minBlog" value="${escapeHtml(filters.minBlog)}" placeholder="블로그문서수 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minScore" value="${escapeHtml(filters.minScore)}" placeholder="총점 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minCpc" value="${escapeHtml(filters.minCpc)}" placeholder="CPC 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="maxCompetition" value="${escapeHtml(filters.maxCompetition)}" placeholder="경쟁강도 이하" />
                </div>
                <div class="analysis-filter-row metrics">
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minPcClicks" value="${escapeHtml(filters.minPcClicks)}" placeholder="PC클릭수 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minMoClicks" value="${escapeHtml(filters.minMoClicks)}" placeholder="MO클릭수 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minTotalClicks" value="${escapeHtml(filters.minTotalClicks)}" placeholder="총클릭수 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minBid1" value="${escapeHtml(filters.minBid1)}" placeholder="입찰1 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minBid2" value="${escapeHtml(filters.minBid2)}" placeholder="입찰2 이상" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minBid3" value="${escapeHtml(filters.minBid3)}" placeholder="입찰3 이상" />
                </div>
            </div>
            <div class="expanded-table-wrap full" data-preserve-scroll-key="analyzed-live-table">
                <table class="expanded-table analyzed-table compact">
                    <thead>
                        <tr>
                            <th>키워드</th>
                            <th>수익성</th>
                            <th>공략성</th>
                            <th>조합</th>
                            <th>분류</th>
                            <th>총점</th>
                            <th>검색량</th>
                            <th>블로그</th>
                            <th>클릭수</th>
                            <th>CPC</th>
                            <th>opportunity</th>
                            <th>competition</th>
                            <th>출처</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="13">조건에 맞는 키워드가 없습니다.</td></tr>`}</tbody>
                </table>
            </div>
        </div>
    `;
}

function formatContentMapIntentLabel(intentKey) {
    const labelMap = {
        commercial: "비교/추천형",
        info: "정보형",
        review: "후기형",
        problem: "문제해결형",
        action: "행동형",
        general: "일반형",
    };
    return labelMap[String(intentKey || "").trim()] || "일반형";
}

function renderContentMapBoard() {
    const summary = state.results.selected?.content_map_summary || {};
    const clusters = Array.isArray(state.results.selected?.keyword_clusters)
        ? state.results.selected.keyword_clusters
        : [];

    if (!clusters.length) {
        return "";
    }

    return `
        <section class="content-map-board">
            <div class="analysis-summary-strip content-map-summary-strip">
                <div class="collector-stat-card">
                    <span>콘텐츠 묶음</span>
                    <strong>${escapeHtml(String(summary.cluster_count || clusters.length))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>추천 글 수</span>
                    <strong>${escapeHtml(String(summary.article_count || 0))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>분리 권장 묶음</span>
                    <strong>${escapeHtml(String(summary.split_cluster_count || 0))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>선별 키워드</span>
                    <strong>${escapeHtml(String(summary.keyword_count || 0))}</strong>
                </div>
            </div>
            <div class="content-map-grid">
                ${clusters.map((cluster) => `
                    <article class="content-map-card ${escapeHtml(cluster.cluster_type || "single_article")}">
                        <div class="content-map-head">
                            <div>
                                <span class="content-map-kicker">${escapeHtml(cluster.cluster_id || "")}</span>
                                <h4>${escapeHtml(cluster.representative_keyword || "-")}</h4>
                                <p>
                                    키워드 ${escapeHtml(String(cluster.keyword_count || 0))}개 ·
                                    추천 글 ${escapeHtml(String(cluster.recommended_article_count || 1))}개 ·
                                    월간 합산 ${escapeHtml(formatNumber(cluster.total_search_volume || 0))}
                                </p>
                            </div>
                            <div class="content-map-head-badges">
                                ${cluster.top_profitability_grade ? renderProfitabilityBadge(cluster.top_profitability_grade) : ""}
                                ${cluster.top_attackability_grade ? renderAttackabilityBadge(cluster.top_attackability_grade) : ""}
                                ${cluster.top_combo ? renderComboBadge(cluster.top_combo) : ""}
                                ${cluster.top_golden_bucket ? renderGoldenBucketPill(cluster.top_golden_bucket) : ""}
                            </div>
                        </div>
                        ${Array.isArray(cluster.topic_terms) && cluster.topic_terms.length
                            ? `
                                <div class="content-map-chip-strip">
                                    ${cluster.topic_terms.map((term) => `<span class="badge">${escapeHtml(term)}</span>`).join("")}
                                </div>
                            `
                            : ""}
                        <div class="content-map-plan">
                            ${Array.isArray(cluster.article_plan)
                                ? cluster.article_plan.map((slot) => `
                                    <div class="content-map-plan-row">
                                        <div class="content-map-plan-head">
                                            <strong>글 ${escapeHtml(String(slot.slot || 1))}</strong>
                                            <span>${escapeHtml(formatContentMapIntentLabel(slot.intent_key))}</span>
                                        </div>
                                        <b>${escapeHtml(slot.lead_keyword || "-")}</b>
                                        <div class="content-map-chip-strip">
                                            ${(slot.keywords || []).map((keyword) => `<span class="badge">${escapeHtml(keyword)}</span>`).join("")}
                                        </div>
                                    </div>
                                `).join("")
                                : ""}
                        </div>
                        ${Array.isArray(cluster.supporting_keywords) && cluster.supporting_keywords.length
                            ? `
                                <div class="content-map-support">
                                    <strong>보조 키워드</strong>
                                    <div class="content-map-chip-strip">
                                        ${cluster.supporting_keywords.map((keyword) => `<span class="badge">${escapeHtml(keyword)}</span>`).join("")}
                                    </div>
                                </div>
                            `
                            : ""}
                    </article>
                `).join("")}
            </div>
        </section>
    `;
}

function normalizeLongtailVerificationStatus(value) {
    const safeValue = String(value || "").trim().toLowerCase();
    return ["pending", "pass", "review", "fail", "error"].includes(safeValue) ? safeValue : "pending";
}

function formatLongtailVerificationLabel(status, label) {
    if (label) {
        return String(label);
    }
    if (status === "pass") return "검증 통과";
    if (status === "review") return "추가 검토";
    if (status === "fail") return "보류";
    if (status === "error") return "검증 실패";
    return "검증 대기";
}

function renderLongtailVerificationPill(status, label) {
    const safeStatus = normalizeLongtailVerificationStatus(status);
    return `
        <span class="longtail-verification-pill ${escapeHtml(safeStatus)}">
            ${escapeHtml(formatLongtailVerificationLabel(safeStatus, label))}
        </span>
    `;
}

function renderLongtailAxisRow({
    profitabilityGrade,
    attackabilityGrade,
    comboGrade,
    goldenBucket,
    score,
    scoreLabel,
}) {
    const badges = [];
    if (normalizeProfitabilityValue(profitabilityGrade)) {
        badges.push(renderProfitabilityBadge(profitabilityGrade));
    }
    if (normalizeAttackabilityValue(attackabilityGrade)) {
        badges.push(renderAttackabilityBadge(attackabilityGrade));
    }
    if (String(comboGrade || "").trim()) {
        badges.push(renderComboBadge(comboGrade));
    }
    if (resolveGoldenBucket({ golden_bucket: goldenBucket })) {
        badges.push(renderGoldenBucketPill(goldenBucket));
    }
    if (score !== undefined && score !== null && score !== "") {
        badges.push(`<span class="badge">${escapeHtml(scoreLabel || "점수")} ${escapeHtml(formatNumber(score))}</span>`);
    }
    return `
        <div class="longtail-axis-row">
            ${badges.join("")}
        </div>
    `;
}

function renderLongtailBoard() {
    const summary = state.results.selected?.longtail_summary || {};
    const suggestions = Array.isArray(state.results.selected?.longtail_suggestions)
        ? state.results.selected.longtail_suggestions
        : [];
    const hasVerified = Number(summary.verified_count || 0) > 0;

    if (!suggestions.length && !summary.suggestion_count) {
        return `
            <section class="longtail-board">
                <div class="longtail-head">
                    <div>
                        <span class="field-label">롱테일 조합</span>
                        <p class="input-help compact-help">클러스터에서 중심 키워드와 의도 토큰을 조합해 실전 롱테일 후보를 제안합니다.</p>
                    </div>
                    <div class="longtail-actions">
                        <button
                            type="button"
                            class="subtle-btn"
                            data-inline-action="verify_longtail_suggestions"
                            ${state.isBusy ? "disabled" : ""}
                        >롱테일 검증 실행</button>
                    </div>
                </div>
                <div class="collector-empty longtail-empty">
                    현재 선별 결과에서는 조합 가능한 롱테일 후보가 없습니다. 클러스터가 2개 이상인 묶음이 생기면 자동 제안됩니다.
                </div>
            </section>
        `;
    }

    return `
        <section class="longtail-board">
            <div class="longtail-head">
                <div>
                    <span class="field-label">롱테일 조합</span>
                    <p class="input-help compact-help">클러스터 기반 후보를 먼저 제안하고, 검증 실행 시 다시 분석해 실제 우선순위를 판정합니다.</p>
                </div>
                <div class="longtail-actions">
                    <span class="analysis-source-pill type">클러스터당 최대 3개</span>
                    <button
                        type="button"
                        class="subtle-btn"
                        data-inline-action="verify_longtail_suggestions"
                        ${state.isBusy ? "disabled" : ""}
                    >${hasVerified ? "롱테일 다시 검증" : "롱테일 검증 실행"}</button>
                </div>
            </div>
            <div class="analysis-summary-strip longtail-summary-strip">
                <div class="collector-stat-card">
                    <span>제안 후보</span>
                    <strong>${escapeHtml(String(summary.suggestion_count || suggestions.length))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>검증 통과</span>
                    <strong>${escapeHtml(String(summary.pass_count || 0))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>추가 검토</span>
                    <strong>${escapeHtml(String(summary.review_count || 0))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>대기 / 보류</span>
                    <strong>${escapeHtml(String((summary.pending_count || 0) + (summary.fail_count || 0) + (summary.error_count || 0)))}</strong>
                </div>
            </div>
            <div class="longtail-grid">
                ${suggestions.map((item) => {
                    const verificationStatus = normalizeLongtailVerificationStatus(item.verification_status);
                    const verifiedMetrics = item.verified_metrics || {};
                    return `
                        <article class="longtail-card ${escapeHtml(verificationStatus)}">
                            <div class="longtail-card-head">
                                <div class="longtail-card-copy">
                                    <span class="content-map-kicker">${escapeHtml(item.cluster_id || "")} · ${escapeHtml(item.intent_label || "일반형")}</span>
                                    <h4>${escapeHtml(item.longtail_keyword || "-")}</h4>
                                    <p>중심어 ${escapeHtml(item.representative_keyword || "-")} · 조합 기준 ${escapeHtml(item.source_keyword || item.modifier_phrase || "-")}</p>
                                </div>
                                <div class="longtail-card-badges">
                                    ${renderLongtailVerificationPill(verificationStatus, item.verification_label)}
                                </div>
                            </div>
                            ${Array.isArray(item.combination_terms) && item.combination_terms.length
                                ? `
                                    <div class="longtail-term-strip">
                                        ${item.combination_terms.map((term) => `<span class="badge">${escapeHtml(term)}</span>`).join("")}
                                    </div>
                                `
                                : ""}
                            <div class="longtail-metric-grid">
                                <div class="longtail-metric-panel">
                                    <strong>예상 조합</strong>
                                    ${renderLongtailAxisRow({
                                        profitabilityGrade: item.projected_profitability_grade,
                                        attackabilityGrade: item.projected_attackability_grade,
                                        comboGrade: item.projected_combo_grade,
                                        goldenBucket: item.projected_golden_bucket,
                                        score: item.projected_score,
                                        scoreLabel: "예상 점수",
                                    })}
                                </div>
                                <div class="longtail-metric-panel verified">
                                    <strong>검증 결과</strong>
                                    ${verificationStatus === "pending"
                                        ? `
                                            <div class="longtail-axis-row">
                                                <span class="badge muted">아직 검증하지 않았습니다.</span>
                                            </div>
                                        `
                                        : renderLongtailAxisRow({
                                            profitabilityGrade: item.verified_profitability_grade,
                                            attackabilityGrade: item.verified_attackability_grade,
                                            comboGrade: item.verified_combo_grade,
                                            goldenBucket: item.verified_golden_bucket,
                                            score: item.verified_score,
                                            scoreLabel: "실측 점수",
                                        })}
                                    ${(verificationStatus === "pending" || verificationStatus === "error")
                                        ? ""
                                        : `
                                            <div class="longtail-verified-stats">
                                                <span class="badge">검색량 ${escapeHtml(formatNumber(verifiedMetrics.volume))}</span>
                                                <span class="badge">CPC ${escapeHtml(formatNumber(verifiedMetrics.cpc))}</span>
                                                <span class="badge">기회비 ${escapeHtml(formatNumber(verifiedMetrics.opportunity))}</span>
                                            </div>
                                        `}
                                </div>
                            </div>
                            <p class="longtail-reason">${escapeHtml(item.verification_reason || "클러스터 기반 롱테일 후보입니다.")}</p>
                        </article>
                    `;
                }).join("")}
            </div>
        </section>
    `;
}

function renderSelectedList(items) {
    const goldCount = (items || []).filter((item) => resolveGoldenBucket(item) === "gold").length;
    const promisingCount = (items || []).filter((item) => resolveGoldenBucket(item) === "promising").length;
    const rows = (items || []).map((item, index) => `
        <tr>
            <td class="num-cell">${escapeHtml(String(index + 1))}</td>
            <td>${renderAnalysisKeywordCell(item)}</td>
            <td>${renderAxisScoreCell(renderProfitabilityBadge(resolveProfitabilityGrade(item)), item.profitability_score)}</td>
            <td>${renderAxisScoreCell(renderAttackabilityBadge(resolveAttackabilityGrade(item)), item.attackability_score)}</td>
            <td>${renderComboBadge(resolveComboGrade(item))}</td>
            <td>${renderGoldenBucketPill(resolveGoldenBucket(item))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.score))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.volume))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.cpc))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.opportunity))}</td>
            <td>${renderAnalysisSourceCell(item)}</td>
        </tr>
    `).join("");

    return `
        <div class="analysis-console">
            ${renderContentMapBoard()}
            ${renderLongtailBoard()}
            <div class="analysis-summary-strip">
                <div class="collector-stat-card">
                    <span>선별 키워드</span>
                    <strong>${escapeHtml(String(countItems(items)))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>진짜 황금</span>
                    <strong>${escapeHtml(String(goldCount))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>유망 조합</span>
                    <strong>${escapeHtml(String(promisingCount))}</strong>
                </div>
            </div>
            <div class="expanded-table-wrap" data-preserve-scroll-key="selected-table">
                <table class="expanded-table selected-table compact">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>키워드</th>
                            <th>수익성</th>
                            <th>공략성</th>
                            <th>조합</th>
                            <th>분류</th>
                            <th>총점</th>
                            <th>검색량</th>
                            <th>CPC</th>
                            <th>opportunity</th>
                            <th>출처</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="11">선별 결과가 없습니다.</td></tr>`}</tbody>
                </table>
            </div>
        </div>
    `;
}

function renderWorkbenchAside(expandedItems, analyzedItems) {
    const bidLeaders = getTopAnalyzedItems(analyzedItems, (item) => item.metrics?.bid);
    const volumeLeaders = getTopAnalyzedItems(analyzedItems, (item) => item.metrics?.volume);
    const modeSummary = summarizeAnalysisModes(analyzedItems);
    const typeSummary = summarizeExpandedTypes(expandedItems);
    const dualAxisGuideCard = `
        <section class="workbench-side-card score-guide-card">
            <div class="workbench-side-head">
                <strong>2축 등급 안내</strong>
                <span>이제 총점은 참고값이고, 실제 선별은 수익성/공략성 조합으로 봅니다.</span>
            </div>
            <div class="workbench-guide-list">
                ${[
                    [renderProfitabilityBadge("A"), "A: 72+ 높은 수익성"],
                    [renderProfitabilityBadge("B"), "B: 56+ 양호한 수익성"],
                    [renderProfitabilityBadge("C"), "C: 38+ 보통 수익성"],
                    [renderProfitabilityBadge("D"), "D: 38 미만 낮은 수익성"],
                    [renderAttackabilityBadge("1"), "1: 74+ 노출 유리"],
                    [renderAttackabilityBadge("2"), "2: 58+ 공략 가능"],
                    [renderAttackabilityBadge("3"), "3: 40+ 다소 빡셈"],
                    [renderAttackabilityBadge("4"), "4: 40 미만 어려움"],
                ].map(([badgeHtml, label]) => `
                    <div class="workbench-guide-row">
                        ${badgeHtml}
                        <span>${escapeHtml(label)}</span>
                    </div>
                `).join("")}
            </div>
            <div class="workbench-guide-note">
                <strong>${renderComboBadge("A1")} · ${renderComboBadge("A2")} · ${renderComboBadge("B1")}</strong>는 진짜 황금 조합입니다.<br />
                <strong>${renderGoldenBucketPill("promising")}</strong>에는 A3, B2, B3, C1, C2가 들어갑니다.
            </div>
        </section>
    `;

    return `
        ${renderWorkbenchFeedCard(
            "고가 키워드",
            "입찰1위 기준 상단 후보",
            bidLeaders,
            "입찰 데이터가 있는 키워드가 아직 없습니다.",
            (item) => `입찰1 ${formatNumber(item.metrics?.bid)} · CPC ${formatNumber(item.metrics?.cpc)}`,
        )}
        ${renderWorkbenchFeedCard(
            "인기 키워드",
            "총조회 기준 상단 후보",
            volumeLeaders,
            "조회 데이터가 있는 키워드가 아직 없습니다.",
            (item) => `총조회 ${formatNumber(item.metrics?.volume)} · 블로그 ${formatNumber(item.metrics?.blog_results)}`,
        )}
        <section class="workbench-side-card">
            <div class="workbench-side-head">
                <strong>출처 / 유형</strong>
                <span>현재 검증에 섞인 측정 방식과 확장 유형입니다.</span>
            </div>
            <div class="workbench-chip-strip">
                <span class="analysis-source-pill measured">실측 ${escapeHtml(String(modeSummary.measured))}건</span>
                <span class="analysis-source-pill estimated">추정 ${escapeHtml(String(modeSummary.estimated))}건</span>
                ${typeSummary.map((item) => `
                    <span class="analysis-source-pill type">${escapeHtml(formatExpandedType(item.type))} ${escapeHtml(String(item.count))}건</span>
                `).join("")}
            </div>
        </section>
        ${dualAxisGuideCard}
    `;
}

function downloadAnalyzedCsv() {
    const items = state.results.analyzed?.analyzed_keywords || [];
    if (!items.length) {
        addLog("내보낼 분석 결과가 없습니다.", "error");
        return;
    }

    const header = [
        "keyword",
        "grade",
        "profitability_grade",
        "profitability_score",
        "attackability_grade",
        "attackability_score",
        "combo_grade",
        "golden_bucket",
        "priority",
        "analysis_mode",
        "confidence",
        "score",
        "cpc_score",
        "search_volume_score",
        "rarity_score",
        "click_potential_score",
        "opportunity_score",
        "competition_score",
        "pc_searches",
        "mobile_searches",
        "volume",
        "blog_results",
        "pc_clicks",
        "mobile_clicks",
        "total_clicks",
        "cpc",
        "bid",
        "bid_1",
        "bid_2",
        "bid_3",
        "mobile_bid_1",
        "mobile_bid_2",
        "mobile_bid_3",
        "profit",
        "competition",
        "opportunity",
    ];
    const rows = items.map((item) => [
        item.keyword || "",
        item.grade || "",
        resolveProfitabilityGrade(item),
        item.profitability_score ?? "",
        resolveAttackabilityGrade(item),
        item.attackability_score ?? "",
        resolveComboGrade(item),
        resolveGoldenBucket(item),
        item.priority || "",
        item.analysis_mode || "",
        item.confidence ?? item.metrics?.confidence ?? "",
        item.score ?? "",
        item.metrics?.cpc_score ?? item.metrics?.monetization_score ?? "",
        item.metrics?.search_volume_score ?? item.metrics?.volume_score ?? "",
        item.metrics?.rarity_score ?? "",
        item.metrics?.click_potential_score ?? "",
        item.metrics?.opportunity_score ?? "",
        item.metrics?.competition_score ?? "",
        item.metrics?.pc_searches ?? "",
        item.metrics?.mobile_searches ?? "",
        item.metrics?.volume ?? "",
        item.metrics?.blog_results ?? "",
        item.metrics?.pc_clicks ?? "",
        item.metrics?.mobile_clicks ?? "",
        item.metrics?.total_clicks ?? "",
        item.metrics?.cpc ?? "",
        item.metrics?.bid ?? "",
        item.metrics?.bid_1 ?? "",
        item.metrics?.bid_2 ?? "",
        item.metrics?.bid_3 ?? "",
        item.metrics?.mobile_bid_1 ?? "",
        item.metrics?.mobile_bid_2 ?? "",
        item.metrics?.mobile_bid_3 ?? "",
        item.metrics?.profit ?? "",
        item.metrics?.competition ?? "",
        item.metrics?.opportunity ?? "",
    ]);
    downloadCsvFile(header, rows, `keyword-analysis-${new Date().toISOString().slice(0, 10)}.csv`);
    addLog(`분석 결과 ${items.length}건을 CSV로 내보냈습니다.`, "success");
}

function handleResultsGridClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }

    const resultTabTrigger = event.target.closest("[data-result-tab]");
    if (resultTabTrigger) {
        setActiveResultView(resultTabTrigger.getAttribute("data-result-tab") || "");
        renderResults();
        return;
    }

    const inlineTrigger = event.target.closest("[data-inline-action]");
    if (inlineTrigger) {
        const action = inlineTrigger.getAttribute("data-inline-action") || "";
        if (action === "toggle_analysis_grade") {
            toggleGradeFilter(inlineTrigger.getAttribute("data-grade-toggle") || "");
            return;
        }
        if (action === "toggle_analysis_attackability") {
            toggleAttackabilityFilter(inlineTrigger.getAttribute("data-attackability-toggle") || "");
            return;
        }
        if (action === "apply_analysis_grade_preset") {
            applyGradePreset(inlineTrigger.getAttribute("data-grade-preset") || "");
            return;
        }
        if (action === "run_analysis_grade_select") {
            const grades = getSelectedGradeFilters();
            const attackabilityGrades = getSelectedAttackabilityFilters();
            if (!grades.length || !attackabilityGrades.length) {
                return;
            }
            runWithGuard(
                () => runThroughGradeSelect(grades, attackabilityGrades),
                `${buildGradeRunLabel(grades, attackabilityGrades)} 선별 실행 중`,
            );
            return;
        }
        if (action === "reset_analyzed_filters") {
            resetAnalyzedFilters();
            return;
        }
        if (action === "stop_stage_run") {
            cancelActiveStream();
            return;
        }
        if (action === "stop_expand_stream") {
            cancelActiveStream();
            return;
        }
        if (action === "continue_analyze") {
            runWithGuard(runThroughAnalyze, "부분 확장 결과로 분석 이어가는 중");
            return;
        }
        if (action === "continue_select") {
            runWithGuard(runThroughSelect, "부분 분석 결과로 선별 이어가는 중");
            return;
        }
        if (action === "continue_title") {
            runWithGuard(runThroughTitle, "선별 결과로 제목 생성 이어가는 중");
            return;
        }
        if (action === "verify_longtail_suggestions") {
            runWithGuard(runLongtailVerification, "롱테일 검증 실행 중");
            return;
        }
    }

    const trigger = event.target.closest("[data-collector-action]");
    if (!trigger) {
        return;
    }

    const action = trigger.getAttribute("data-collector-action") || "";
    const collectedItems = state.results.collected?.collected_keywords || [];

    if (action === "select_all") {
        applyCollectedSelection(collectedItems, true);
        return;
    }

    if (action === "clear_all") {
        applyCollectedSelection(collectedItems, false);
        return;
    }

    const groupKey = trigger.getAttribute("data-collector-group") || "";
    if (!groupKey) {
        return;
    }

    const groupItems = collectedItems.filter((item) => (item.raw || item.keyword || "") === groupKey);
    applyCollectedSelection(groupItems, action === "select_group");
}
