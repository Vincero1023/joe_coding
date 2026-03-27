const originalRunCollectStage = typeof window.runCollectStage === "function" ? window.runCollectStage : null;

const originalRunExpandStage = typeof window.runExpandStage === "function" ? window.runExpandStage : null;

const originalRunAnalyzeStage = typeof window.runAnalyzeStage === "function" ? window.runAnalyzeStage : null;

const originalRenderResults = typeof window.renderResults === "function"
    ? window.renderResults
    : (typeof renderResults === "function" ? renderResults : null);

const LONGTAIL_OPTION_LIBRARY = [
    {
        key: "guide",
        label: "가이드",
        description: "정보형 정리나 안내 글에만 필요할 때 씁니다.",
    },
    {
        key: "checklist",
        label: "체크리스트",
        description: "준비 단계나 확인 순서가 분명할 때만 씁니다.",
    },
];

const RESULT_STAGE_DOCK_LIBRARY = [
    { key: "collected", stageLabel: "1단계 수집", tabTitle: "수집" },
    { key: "expanded", stageLabel: "2단계 확장", tabTitle: "확장" },
    { key: "analyzed", stageLabel: "3단계 분석", tabTitle: "분석" },
    { key: "selected", stageLabel: "4단계 선별", tabTitle: "선별" },
    { key: "titled", stageLabel: "5단계 제목", tabTitle: "제목" },
];

function buildResultStageDockItems() {
    const collectedItems = state.results.collected?.collected_keywords || [];
    const expandedItems = state.results.expanded?.expanded_keywords || [];
    const analyzedItems = state.results.analyzed?.analyzed_keywords || [];
    const selectedItems = state.results.selected?.selected_keywords || [];
    const generatedTitles = state.results.titled?.generated_titles || [];
    const collectedState = state.stageStatus.collected.state;
    const expandedState = state.stageStatus.expanded.state;
    const analyzedState = state.stageStatus.analyzed.state;
    const selectedState = state.stageStatus.selected.state;
    const titledState = state.stageStatus.titled.state;
    const workbenchAvailable = (
        expandedItems.length
        || analyzedItems.length
        || expandedState === "running"
        || analyzedState === "running"
        || expandedState === "cancelled"
        || analyzedState === "cancelled"
        || expandedState === "error"
        || analyzedState === "error"
    );
    const analyzedAvailable = (
        analyzedItems.length
        || analyzedState === "running"
        || analyzedState === "cancelled"
        || analyzedState === "error"
    );

    return RESULT_STAGE_DOCK_LIBRARY.map((stage) => {
        if (stage.key === "collected") {
            return {
                ...stage,
                available: Boolean(collectedItems.length || collectedState !== "pending"),
                state: collectedState,
                countLabel: collectedItems.length
                    ? `${countItems(collectedItems)}건`
                    : String(state.stageStatus.collected.message || "준비 중").trim(),
            };
        }
        if (stage.key === "expanded") {
            return {
                ...stage,
                available: Boolean(workbenchAvailable),
                state: expandedState,
                countLabel: expandedItems.length
                    ? `확장 ${countItems(expandedItems)}건`
                    : String(state.stageStatus.expanded.message || "준비 중").trim(),
            };
        }
        if (stage.key === "analyzed") {
            return {
                ...stage,
                available: Boolean(analyzedAvailable),
                state: analyzedState,
                countLabel: analyzedItems.length
                    ? `검증 ${countItems(analyzedItems)}건`
                    : String(state.stageStatus.analyzed.message || "준비 중").trim(),
            };
        }
        if (stage.key === "selected") {
            return {
                ...stage,
                available: Boolean(selectedItems.length || selectedState !== "pending"),
                state: selectedState,
                countLabel: selectedItems.length
                    ? `${countItems(selectedItems)}건`
                    : String(state.stageStatus.selected.message || "준비 중").trim(),
            };
        }
        return {
            ...stage,
            available: Boolean(generatedTitles.length || titledState !== "pending"),
            state: titledState,
            countLabel: generatedTitles.length
                ? `${countItems(generatedTitles)}세트`
                : String(state.stageStatus.titled.message || "준비 중").trim(),
        };
    });
}

function renderResultStageDock() {
    if (!elements.resultStageDock) {
        return;
    }

    const stageItems = buildResultStageDockItems();
    const availableViews = stageItems
        .filter((item) => item.available)
        .map((item) => ({ key: item.key }));
    const activeViewKey = availableViews.length
        ? resolveActiveResultView(availableViews)
        : "";

    if (elements.resultStageDockPanel) {
        elements.resultStageDockPanel.hidden = false;
    }
    elements.resultStageDock.innerHTML = `
        <div class="results-stage-switcher result-stage-dock-switcher">
            ${stageItems.map((item) => {
                const isActive = item.key === activeViewKey;
                const isDisabled = !item.available;
                return `
                    <button
                        type="button"
                        class="results-stage-tab result-stage-dock-tab ${escapeHtml(item.state || "pending")}${isActive ? " active" : ""}${isDisabled ? " disabled" : ""}"
                        ${isDisabled ? "disabled" : ""}
                        data-result-tab="${escapeHtml(item.key)}"
                        aria-disabled="${isDisabled ? "true" : "false"}"
                        aria-pressed="${isActive ? "true" : "false"}"
                    >
                        <span class="results-stage-step">${escapeHtml(item.stageLabel)}</span>
                        <strong>${escapeHtml(item.tabTitle)}</strong>
                        <span class="results-stage-meta">${escapeHtml(item.countLabel)}</span>
                    </button>
                `;
            }).join("")}
        </div>
    `;
}

window.renderResultStageTabs = function renderResultStageTabsOverride() {
    return "";
};
renderResultStageTabs = window.renderResultStageTabs;

window.renderResults = function renderResultsOverride(...args) {
    const result = originalRenderResults?.(...args);
    renderResultStageDock();
    return result;
};
renderResults = window.renderResults;

function normalizeLongtailOptionalSuffixKey(value) {
    const normalized = String(value || "").trim().toLowerCase();
    return LONGTAIL_OPTION_LIBRARY.some((option) => option.key === normalized)
        ? normalized
        : "";
}

function normalizeLongtailOptionalSuffixKeys(values) {
    if (!Array.isArray(values)) {
        return [];
    }
    const seen = new Set();
    return values
        .map((value) => normalizeLongtailOptionalSuffixKey(value))
        .filter((value) => value && !seen.has(value) && seen.add(value));
}

function getLongtailOptionalSuffixKeys(selectedResult = null) {
    if (!Array.isArray(state.longtailOptionalSuffixKeys)) {
        state.longtailOptionalSuffixKeys = [];
    }
    if (!state.longtailOptionalSuffixKeys.length) {
        const fallbackKeys = normalizeLongtailOptionalSuffixKeys(
            selectedResult?.longtail_options?.optional_suffix_keys || [],
        );
        if (fallbackKeys.length) {
            state.longtailOptionalSuffixKeys = fallbackKeys;
        }
    }
    return normalizeLongtailOptionalSuffixKeys(state.longtailOptionalSuffixKeys);
}

function buildLongtailOptionsPayload(selectedResult = null) {
    return {
        optional_suffix_keys: getLongtailOptionalSuffixKeys(selectedResult),
    };
}
window.buildLongtailOptionsPayload = buildLongtailOptionsPayload;

function hasPendingLongtailOptionChanges(selectedResult = null) {
    const currentKeys = buildLongtailOptionsPayload(selectedResult).optional_suffix_keys;
    const appliedKeys = normalizeLongtailOptionalSuffixKeys(
        selectedResult?.longtail_options?.optional_suffix_keys || [],
    );
    return currentKeys.join("|") !== appliedKeys.join("|");
}

function formatLongtailOptionLabels(optionKeys) {
    const keySet = new Set(normalizeLongtailOptionalSuffixKeys(optionKeys));
    return LONGTAIL_OPTION_LIBRARY
        .filter((option) => keySet.has(option.key))
        .map((option) => option.label);
}

function toggleLongtailOptionalSuffixKey(optionKey) {
    const normalizedKey = normalizeLongtailOptionalSuffixKey(optionKey);
    if (!normalizedKey) {
        return;
    }
    const selectedKeys = new Set(getLongtailOptionalSuffixKeys(state.results.selected || {}));
    if (selectedKeys.has(normalizedKey)) {
        selectedKeys.delete(normalizedKey);
    } else {
        selectedKeys.add(normalizedKey);
    }
    state.longtailOptionalSuffixKeys = LONGTAIL_OPTION_LIBRARY
        .map((option) => option.key)
        .filter((key) => selectedKeys.has(key));
}

function renderLongtailOptionStrip(selectedResult) {
    const optionKeys = getLongtailOptionalSuffixKeys(selectedResult);
    const optionKeySet = new Set(optionKeys);
    const optionLabels = formatLongtailOptionLabels(optionKeys);
    const optionsChanged = hasPendingLongtailOptionChanges(selectedResult);
    return `
        <div class="longtail-option-strip">
            <span class="badge">추가 의도 토큰</span>
            ${LONGTAIL_OPTION_LIBRARY.map((option) => {
                const isActive = optionKeySet.has(option.key);
                return `
                    <button
                        type="button"
                        class="ghost-chip longtail-option-chip ${isActive ? "active" : ""}"
                        data-longtail-option-key="${escapeHtml(option.key)}"
                        aria-pressed="${isActive ? "true" : "false"}"
                        title="${escapeHtml(option.description)}"
                    >${escapeHtml(option.label)}</button>
                `;
            }).join("")}
            <span class="longtail-option-copy">
                기본은 핵심 의도만 조합합니다.
                추가 토큰 ${escapeHtml(optionLabels.length ? optionLabels.join(", ") : "없음")}
                ${optionsChanged ? " · 다시 조합 필요" : ""}
            </span>
        </div>
    `;
}

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
    return true;
}

function isAllAxisFilterSelection(profitabilityGrades, attackabilityGrades) {
    const normalizedProfitability = normalizeProfitabilityList(profitabilityGrades);
    const normalizedAttackability = normalizeAttackabilityList(attackabilityGrades);
    return normalizedProfitability.length === PROFITABILITY_ORDER.length
        && normalizedAttackability.length === ATTACKABILITY_ORDER.length;
}

function buildGradeRunLabel(profitabilityGrades, attackabilityGrades) {
    const normalizedProfitability = normalizeProfitabilityList(profitabilityGrades);
    const normalizedAttackability = normalizeAttackabilityList(attackabilityGrades);
    if (!normalizedProfitability.length || !normalizedAttackability.length) {
        return "조합 미선택";
    }
    if (isAllAxisFilterSelection(normalizedProfitability, normalizedAttackability)) {
        return "전체 조합";
    }
    return `수익성 ${normalizedProfitability.join(", ")} · 노출도 ${normalizedAttackability.join(", ")}`;
}

function getSelectionPresetConfig(presetKey) {
    const safeKey = String(presetKey || "").trim();
    return GRADE_PRESET_MAP[safeKey] || null;
}

function resolveSelectionPresetKey(profitabilityGrades, attackabilityGrades) {
    const normalizedProfitability = normalizeProfitabilityList(profitabilityGrades);
    const normalizedAttackability = normalizeAttackabilityList(attackabilityGrades);
    const presetKeys = Array.isArray(SELECTION_PRESET_ORDER) ? SELECTION_PRESET_ORDER : Object.keys(GRADE_PRESET_MAP || {});
    for (const presetKey of presetKeys) {
        const preset = getSelectionPresetConfig(presetKey);
        const presetProfitability = normalizeProfitabilityList(preset?.profitability || []);
        const presetAttackability = normalizeAttackabilityList(preset?.attackability || []);
        if (
            presetProfitability.length === normalizedProfitability.length
            && presetAttackability.length === normalizedAttackability.length
            && presetProfitability.every((grade) => normalizedProfitability.includes(grade))
            && presetAttackability.every((grade) => normalizedAttackability.includes(grade))
        ) {
            return presetKey;
        }
    }
    return "custom";
}

function resolveSelectionPresetLabel(presetKey) {
    if (presetKey === "auto") {
        return "자동 선별";
    }
    if (presetKey === "custom") {
        return "사용자 정의";
    }
    return getSelectionPresetConfig(presetKey)?.label || "사용자 정의";
}

function hasEditorialSupportSelection(items) {
    return (items || []).some((item) => String(item?.selection_mode || "").trim() === "editorial_support");
}
window.resolveSelectionPresetKey = resolveSelectionPresetKey;
window.resolveSelectionPresetLabel = resolveSelectionPresetLabel;
window.hasEditorialSupportSelection = hasEditorialSupportSelection;

function buildSelectionPresetRunLabel(profitabilityGrades, attackabilityGrades) {
    const presetKey = resolveSelectionPresetKey(profitabilityGrades, attackabilityGrades);
    const presetLabel = resolveSelectionPresetLabel(presetKey);
    if (presetKey !== "custom" && presetKey !== "all") {
        return `${presetLabel} (${buildGradeRunLabel(profitabilityGrades, attackabilityGrades)})`;
    }
    return buildGradeRunLabel(profitabilityGrades, attackabilityGrades);
}

function buildSelectionResultTitle(items, profile) {
    if (profile?.mode === "grade_filter") {
        return "등급 선별 키워드";
    }
    if (profile?.mode === "default" && hasEditorialSupportSelection(items)) {
        return "글감 후보";
    }
    if (profile?.mode === "combo_filter" && profile?.preset_key === "longtail_explore") {
        return "롱테일 탐색 후보";
    }
    return "선별 키워드";
}

function buildSelectionResultSubtitle(items, profile) {
    if (!profile) {
        return countItems(items) ? "선별 결과를 다음 단계에 바로 넘길 수 있습니다." : "";
    }

    if (profile.mode === "combo_filter") {
        const presetKey = String(profile.preset_key || "").trim();
        const presetLabel = String(profile.preset_label || resolveSelectionPresetLabel(presetKey)).trim();
        if (presetKey === "all") {
            return "전체 조합을 그대로 통과시켜 하위 키워드와 글감 후보를 함께 정리한 결과입니다.";
        }
        if (presetKey && presetKey !== "custom" && presetKey !== "all" && presetLabel) {
            return `${presetLabel} 프리셋으로 ${buildGradeRunLabel(profile.allowed_profitability_grades || [], profile.allowed_attackability_grades || [])} 조합을 선별한 결과입니다.`;
        }
        return `${buildGradeRunLabel(profile.allowed_profitability_grades || [], profile.allowed_attackability_grades || [])} 조합으로 선별한 결과입니다.`;
    }

    const grades = Array.isArray(profile.allowed_grades) ? profile.allowed_grades.filter(Boolean) : [];
    if (profile.mode === "grade_filter") {
        return grades.length ? `${grades.join(", ")} 등급 키워드를 그대로 다음 단계로 보낸 결과입니다.` : "등급 기준으로 선별한 결과입니다.";
    }

    if (profile.mode === "default" && (profile.has_editorial_support || hasEditorialSupportSelection(items))) {
        return "자동 선별에서 수익형 기준만으로는 놓치기 쉬운 글감 후보까지 함께 남긴 결과입니다.";
    }

    return countItems(items) ? "자동 선별 기준으로 다음 단계 후보를 정리한 결과입니다." : "";
}

window.buildSelectionResultTitle = buildSelectionResultTitle;
window.buildSelectionResultSubtitle = buildSelectionResultSubtitle;

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
            : "수익성과 노출도를 1개 이상 선택하세요.";
    }

    if (elements.runGradeSelectButton) {
        elements.runGradeSelectButton.disabled = state.isBusy
            || selectedProfitability.length === 0
            || selectedAttackability.length === 0;
    }
}

function applyGradePreset(presetKey) {
    const preset = getSelectionPresetConfig(presetKey) || GRADE_PRESET_MAP.all;
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

function buildEmptyCollectNotice(result = null) {
    const debug = result?.debug || {};
    const mode = String(debug.mode || (typeof getCollectorMode === "function" ? getCollectorMode() : "") || "").trim();
    const requestedSeed = String(debug.requested_seed || elements.seedInput?.value || "").trim();
    const resolvedCategory = String(
        debug.resolved_category
        || debug.requested_category
        || elements.categoryInput?.value
        || "",
    ).trim();
    const requestedSource = String(
        debug.requested_category_source
        || debug.effective_source
        || elements.categorySourceInput?.value
        || "",
    ).trim();

    if (mode === "seed" || requestedSeed) {
        const targetSeed = requestedSeed || "입력한 시드";
        const retryHint = targetSeed.includes(" ")
            ? "너무 구체적인 복합어 대신 핵심 키워드 1~2개로 다시 시도해 주세요."
            : "다른 시드나 표현으로 다시 시도해 주세요.";
        return `수집 결과가 없습니다.\n시드 "${targetSeed}"에서 자동완성/연관검색 후보를 찾지 못했습니다.\n${retryHint}`;
    }

    if (mode === "category" || resolvedCategory) {
        const targetCategory = resolvedCategory || "선택한 카테고리";
        const retryHint = requestedSource === "naver_trend"
            ? "카테고리, 날짜, 트렌드 소스를 바꾸거나 preset fallback을 켜서 다시 시도해 주세요."
            : "카테고리나 수집 소스를 바꿔서 다시 시도해 주세요.";
        return `수집 결과가 없습니다.\n${targetCategory}에서 가져올 키워드를 찾지 못했습니다.\n${retryHint}`;
    }

    return "수집 결과가 없습니다.\n입력 조건을 조금 넓혀서 다시 시도해 주세요.";
}

function buildEmptyExpandNotice() {
    return "확장 결과가 없습니다.\n현재 수집 키워드에서 추가 확장 후보를 찾지 못했습니다.\n다른 시드로 다시 수집하거나 직접 입력 모드를 사용해 주세요.";
}

function buildEmptyAnalyzeNotice() {
    return "분석 결과가 없습니다.\n확장 결과가 비어 있어 다음 단계로 진행할 수 없습니다.\n다른 키워드로 다시 확장하거나 직접 분석 입력을 사용해 주세요.";
}

window.runCollectStage = async function runCollectStageOverride() {
    const result = await originalRunCollectStage();
    if (countItems(result?.collected_keywords) > 0) {
        return result;
    }

    throw createUserNoticeError(buildEmptyCollectNotice(result), {
        code: "empty_collect_notice",
        stageKey: "collected",
    });
};
runCollectStage = window.runCollectStage;

window.runExpandStage = async function runExpandStageOverride() {
    const source = elements.expandInputSource?.value || "collector_selected";
    if (source !== "manual_text" && state.results.collected && countItems(state.results.collected?.collected_keywords) === 0) {
        throw createUserNoticeError(buildEmptyCollectNotice(state.results.collected), {
            code: "empty_collect_notice",
            stageKey: "collected",
        });
    }

    const result = await originalRunExpandStage();
    if (countItems(result?.expanded_keywords) > 0) {
        return result;
    }

    throw createUserNoticeError(buildEmptyExpandNotice(), {
        code: "empty_expand_notice",
        stageKey: "expanded",
    });
};
runExpandStage = window.runExpandStage;

window.runAnalyzeStage = async function runAnalyzeStageOverride() {
    const source = elements.analyzeInputSource?.value || "expanded_results";
    if (source !== "manual_text" && state.results.expanded && countItems(state.results.expanded?.expanded_keywords) === 0) {
        throw createUserNoticeError(buildEmptyExpandNotice(), {
            code: "empty_expand_notice",
            stageKey: "expanded",
        });
    }

    const result = await originalRunAnalyzeStage();
    if (countItems(result?.analyzed_keywords) > 0) {
        return result;
    }

    throw createUserNoticeError(buildEmptyAnalyzeNotice(), {
        code: "empty_analyze_notice",
        stageKey: "analyzed",
    });
};
runAnalyzeStage = window.runAnalyzeStage;

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
window.getForwardSelectOptions = getForwardSelectOptions;

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
    const longtailOptions = buildLongtailOptionsPayload(state.results.selected || {});
    const selectionCandidates = hasExplicitFilters
        ? analyzedKeywords.filter((item) => (
            allowedProfitabilityGrades.includes(resolveProfitabilityGrade(item))
            && allowedAttackabilityGrades.includes(resolveAttackabilityGrade(item))
        ))
        : analyzedKeywords;

    if (!selectionCandidates.length) {
        const noticeMessage = hasExplicitFilters
            ? `선택한 조건에 맞는 검색 결과가 없습니다.\n수익성 ${allowedProfitabilityGrades.join(", ")} · 노출도 ${allowedAttackabilityGrades.join(", ")} 조합을 넓혀서 다시 시도해 주세요.`
            : "선별할 검색 결과가 없습니다.\n먼저 수집/확장/분석 결과를 확인해 주세요.";
        applyEmptySelectedResult(noticeMessage);
        throw createUserNoticeError(noticeMessage, {
            code: "empty_selection_notice",
            stageKey: "selected",
        });
    }

    addLog(
        hasExplicitFilters
            ? `선별 시작: ${buildSelectionPresetRunLabel(allowedProfitabilityGrades, allowedAttackabilityGrades)} 기준으로 ${countItems(selectionCandidates)}건에 조합 기준을 적용합니다.`
            : "선별 시작: 자동 선별 기준으로 수익형 후보와 글감 후보를 함께 정리합니다.",
    );
    clearStageAndDownstream("selected");
    const result = await executeStage({
        stageKey: "selected",
        endpoint: "/select",
        inputData: {
            ...buildTitleExportRequestContext(),
            analyzed_keywords: selectionCandidates,
            select_options: {
                ...(hasExplicitFilters
                    ? {
                        allowed_profitability_grades: allowedProfitabilityGrades,
                        allowed_attackability_grades: allowedAttackabilityGrades,
                        mode: "combo_filter",
                    }
                    : {}),
                longtail_options: longtailOptions,
            },
        },
    });

    state.longtailOptionalSuffixKeys = normalizeLongtailOptionalSuffixKeys(
        result.longtail_options?.optional_suffix_keys || longtailOptions.optional_suffix_keys,
    );
    state.results.selected = {
        ...result,
        selection_profile: {
            mode: hasExplicitFilters ? "combo_filter" : "default",
            allowed_profitability_grades: allowedProfitabilityGrades,
            allowed_attackability_grades: allowedAttackabilityGrades,
            candidate_count: selectionCandidates.length,
            preset_key: hasExplicitFilters ? resolveSelectionPresetKey(allowedProfitabilityGrades, allowedAttackabilityGrades) : "auto",
            preset_label: hasExplicitFilters
                ? resolveSelectionPresetLabel(resolveSelectionPresetKey(allowedProfitabilityGrades, allowedAttackabilityGrades))
                : "자동 선별",
            has_editorial_support: hasEditorialSupportSelection(result.selected_keywords || []),
        },
    };
    addLog(
        hasExplicitFilters
            ? `선별 완료 (${buildSelectionPresetRunLabel(allowedProfitabilityGrades, allowedAttackabilityGrades)}): ${countItems(result.selected_keywords)}건`
            : `선별 완료: ${countItems(result.selected_keywords)}건`,
        "success",
    );
    const selectionExportArtifacts = Array.isArray(result.selection_export?.artifacts)
        ? result.selection_export.artifacts
        : result.selection_export?.artifact
            ? [result.selection_export.artifact]
            : [];
    if (selectionExportArtifacts.length) {
        addLog(
            `선별 키워드 파일 저장: ${selectionExportArtifacts.map((item) => item.filename).filter(Boolean).join(", ")}`,
            "success",
        );
    }
    renderAll();
    return state.results.selected;
}
window.runSelectStage = runSelectStage;

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
    const result = await executeTitleStageStream({
        selected_keywords: state.results.selected?.selected_keywords || [],
        keyword_clusters: state.results.selected?.keyword_clusters || [],
        longtail_suggestions: state.results.selected?.longtail_suggestions || [],
        longtail_options: state.results.selected?.longtail_options || null,
        analyzed_keywords: state.results.analyzed?.analyzed_keywords || [],
        serp_competition_summary: state.results.selected?.serp_competition_summary || null,
        title_options: titleOptions,
    });

    state.results.titled = result;
    addLog(`제목 생성 완료: ${countItems(result.generated_titles)}세트`, "success");
    renderAll();
    return result;
}

function buildTitleStreamStatusMessage(streamMeta) {
    if (!streamMeta) {
        return "제목 생성 준비 중";
    }

    const phase = String(streamMeta.phase || "generate");
    const percent = Number(streamMeta.progressPercent || 0);
    const processedCount = Number(streamMeta.processedCount || 0);
    const totalCount = Number(streamMeta.totalCount || 0);
    const message = String(streamMeta.message || "").trim();

    if (phase === "generate" && totalCount > 0) {
        return `${processedCount} / ${totalCount}세트 · ${percent}%`;
    }
    if ((phase === "auto_retry" || phase === "model_escalation") && totalCount > 0) {
        return `${message || `${processedCount} / ${totalCount}건`} · ${percent}%`;
    }
    if (message) {
        return `${message} · ${percent}%`;
    }
    return `${percent}%`;
}

function applyTitleStreamEvent(eventPayload, startedAt) {
    if (!eventPayload || eventPayload.event !== "progress") {
        return;
    }

    const progress = eventPayload.data || {};
    const currentResult = state.results.titled || createEmptyTitledResult();
    const currentMeta = currentResult.stream_meta || {};
    currentResult.stream_meta = {
        phase: progress.phase || currentMeta.phase || "generate",
        progressPercent: Number(progress.progress_percent ?? currentMeta.progressPercent ?? 0),
        processedCount: Number(progress.processed_count ?? currentMeta.processedCount ?? 0),
        totalCount: Number(progress.total_count ?? currentMeta.totalCount ?? 0),
        currentKeyword: progress.current_keyword || currentMeta.currentKeyword || "",
        message: progress.message || currentMeta.message || "",
    };
    state.results.titled = currentResult;
    state.stageStatus.titled = {
        state: "running",
        message: buildTitleStreamStatusMessage(currentResult.stream_meta),
        startedAt,
        finishedAt: null,
        durationMs: null,
    };
    renderAll();
}

async function executeTitleStageStream(inputData) {
    const stageKey = "titled";
    const stage = getStage(stageKey);
    const startedAt = Date.now();
    const startedAtLabel = new Date(startedAt).toISOString();
    const streamController = beginStreamRequest("/generate-title/stream");
    const targetCount = countItems(inputData?.selected_keywords || []);

    setActiveResultView(stageKey);
    state.results.titled = {
        ...createEmptyTitledResult(),
        stream_meta: {
            phase: "generate",
            progressPercent: 0,
            processedCount: 0,
            totalCount: targetCount,
            currentKeyword: "",
            message: "제목 생성 준비 중",
        },
    };
    state.stageStatus[stageKey] = {
        state: "running",
        message: targetCount ? `0 / ${targetCount}세트 · 0%` : "제목 생성 준비 중",
        startedAt,
        finishedAt: null,
        durationMs: null,
    };
    renderAll();

    try {
        const response = await postModuleStream(
            "/generate-title/stream",
            inputData,
            (eventPayload) => {
                if (eventPayload?.event === "progress") {
                    applyTitleStreamEvent(eventPayload, startedAt);
                }
            },
            { signal: streamController.signal },
        );
        const result = response.result || createEmptyTitledResult();
        const itemCount = countItems(result.generated_titles);
        const durationMs = Date.now() - startedAt;

        state.stageStatus[stageKey] = {
            state: "success",
            message: `${itemCount}세트 완료`,
            startedAt,
            finishedAt: Date.now(),
            durationMs,
        };
        state.diagnostics[stageKey] = {
            stageKey,
            stageLabel: stage.label,
            status: "success",
            endpoint: "/generate-title/stream",
            requestId: response.requestId,
            startedAt: startedAtLabel,
            durationMs,
            request: sanitizeSensitiveData(inputData),
            responseSummary: buildResponseSummary(stageKey, result),
            backendDebug: result.debug || null,
        };
        return result;
    } catch (error) {
        if (isAbortLikeError(error)) {
            const finishedAt = Date.now();
            const durationMs = finishedAt - startedAt;
            state.stageStatus[stageKey] = {
                state: "cancelled",
                message: "사용자 중지",
                startedAt,
                finishedAt,
                durationMs,
            };
            state.diagnostics[stageKey] = {
                stageKey,
                stageLabel: stage.label,
                status: "cancelled",
                endpoint: "/generate-title/stream",
                requestId: "",
                startedAt: startedAtLabel,
                durationMs,
                request: sanitizeSensitiveData(inputData),
            };
            renderAll();
            throw error;
        }

        const normalizedError = normalizeError(error, {
            stageKey,
            endpoint: "/generate-title/stream",
            request: inputData,
            startedAt: startedAtLabel,
            durationMs: Date.now() - startedAt,
        });

        state.stageStatus[stageKey] = {
            state: "error",
            message: normalizedError.message,
            startedAt,
            finishedAt: Date.now(),
            durationMs: normalizedError.durationMs,
        };
        state.diagnostics[stageKey] = {
            stageKey,
            stageLabel: stage.label,
            status: "error",
            endpoint: "/generate-title/stream",
            requestId: normalizedError.requestId,
            startedAt: startedAtLabel,
            durationMs: normalizedError.durationMs,
            request: sanitizeSensitiveData(inputData),
            error: normalizedError,
        };
        state.lastError = normalizedError;
        renderAll();
        throw normalizedError;
    } finally {
        completeStreamRequest(streamController);
    }
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
    const longtailOptions = buildLongtailOptionsPayload(selectedResult);
    const shouldRebuild = hasPendingLongtailOptionChanges(selectedResult);
    addLog(
        shouldRebuild
            ? `롱테일 검증 시작: ${formatLongtailOptionLabels(longtailOptions.optional_suffix_keys).join(", ") || "기본"} 기준으로 후보를 다시 조합합니다.`
            : (longtailSuggestions.length
                ? `롱테일 검증 시작: 제안 ${countItems(longtailSuggestions)}건을 다시 분석합니다.`
                : "롱테일 검증 시작: 선별 결과에서 새 롱테일 후보를 계산하고 분석합니다."),
    );

    const response = await postModule("/verify-longtail", {
        selected_keywords: selectedKeywords,
        keyword_clusters: Array.isArray(selectedResult.keyword_clusters) ? selectedResult.keyword_clusters : [],
        longtail_suggestions: shouldRebuild ? [] : longtailSuggestions,
        analyzer_options: buildLongtailAnalyzerOptions(),
        longtail_options: longtailOptions,
        force_rebuild: shouldRebuild,
    });
    const result = response?.result || {};
    const verifiedSuggestions = Array.isArray(result.verified_longtail_suggestions)
        ? result.verified_longtail_suggestions
        : [];
    const summary = result.longtail_verification_summary || {};
    state.longtailOptionalSuffixKeys = normalizeLongtailOptionalSuffixKeys(
        result.longtail_options?.optional_suffix_keys || longtailOptions.optional_suffix_keys,
    );

    state.results.selected = {
        ...selectedResult,
        longtail_suggestions: verifiedSuggestions,
        longtail_summary: summary,
        longtail_options: result.longtail_options || longtailOptions,
        cannibalization_report: result.cannibalization_report || selectedResult.cannibalization_report || null,
        serp_competition_summary: null,
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

async function runSerpCompetitionSummary() {
    const selectedResult = state.results.selected || {};
    const selectedKeywords = Array.isArray(selectedResult.selected_keywords)
        ? selectedResult.selected_keywords
        : [];
    if (!selectedKeywords.length) {
        throw new Error("선별 결과가 없습니다. 먼저 선별을 실행해 주세요.");
    }

    addLog("SERP 경쟁 요약 시작: 네이버 상위 제목 패턴을 확인합니다.");
    const response = await postModule("/serp-competition-summary", {
        selected_keywords: selectedKeywords,
        longtail_suggestions: Array.isArray(selectedResult.longtail_suggestions)
            ? selectedResult.longtail_suggestions
            : [],
        limit: 3,
        title_options: typeof buildTitleOptions === "function" ? buildTitleOptions() : {},
    });
    const serpSummary = response?.result?.serp_competition_summary || {
        summary: {},
        queries: [],
    };
    state.results.selected = {
        ...selectedResult,
        serp_competition_summary: serpSummary,
        serp_competition_summary_at: new Date().toISOString(),
    };
    addLog(
        `SERP 경쟁 요약 완료: 성공 ${Number(serpSummary.summary?.success_count || 0)}개 · 실패 ${Number(serpSummary.summary?.error_count || 0)}개`,
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

function getQueueSnapshotState() {
    const snapshot = state.queueSnapshot && typeof state.queueSnapshot === "object"
        ? state.queueSnapshot
        : {};
    return {
        runner: snapshot.runner && typeof snapshot.runner === "object" ? snapshot.runner : {},
        jobs: Array.isArray(snapshot.jobs) ? snapshot.jobs : [],
        routines: Array.isArray(snapshot.routines) ? snapshot.routines : [],
        paths: snapshot.paths && typeof snapshot.paths === "object" ? snapshot.paths : {},
    };
}

function getQueueSelectedWeekdays() {
    const values = new Set();
    elements.queueRoutineWeekdayInputs?.forEach((input) => {
        if (!input.checked) {
            return;
        }
        const value = Number.parseInt(String(input.value || "").trim(), 10);
        if (Number.isInteger(value) && value >= 0 && value <= 6) {
            values.add(value);
        }
    });
    return Array.from(values).sort((left, right) => left - right);
}

function getQueueSelectedCategories() {
    const values = [];
    const seen = new Set();
    elements.queueRoutineCategoryInputs?.forEach((input) => {
        if (!input.checked) {
            return;
        }
        const value = String(input.value || "").trim();
        if (!value || seen.has(value)) {
            return;
        }
        seen.add(value);
        values.push(value);
    });
    return values;
}

function parseQueueListText(value) {
    return parseKeywordText(String(value || "").trim());
}

function buildQueueCollectorConfig() {
    const trendSettings = typeof getTrendSettingsFormState === "function"
        ? getTrendSettingsFormState()
        : {};
    const categorySource = String(elements.categorySourceInput?.value || "naver_trend").trim() || "naver_trend";
    return {
        category_source: categorySource,
        options: {
            collect_related: Boolean(elements.optionRelated?.checked),
            collect_autocomplete: Boolean(elements.optionAutocomplete?.checked),
            collect_bulk: Boolean(elements.optionBulk?.checked),
        },
        trend_options: {
            service: String(trendSettings.service || "naver_blog").trim() || "naver_blog",
            content_type: "text",
            date: String(trendSettings.date || "").trim(),
            auth_cookie: String(trendSettings.auth_cookie || "").trim(),
            fallback_to_preset_search: Boolean(trendSettings.fallback_to_preset_search),
        },
        debug: Boolean(elements.optionDebug?.checked),
    };
}

function buildQueueExpanderConfig() {
    const rawLimit = Number.parseInt(String(elements.expandMaxResultsInput?.value || "").trim(), 10);
    return {
        analysis_json_path: String(elements.expanderAnalysisPath?.value || "").trim(),
        expand_options: {
            enable_related: Boolean(elements.expandOptionRelated?.checked ?? true),
            enable_autocomplete: Boolean(elements.expandOptionAutocomplete?.checked ?? true),
            enable_seed_filter: Boolean(elements.expandOptionSeedFilter?.checked ?? true),
            max_results: Number.isFinite(rawLimit) && rawLimit > 0 ? rawLimit : null,
        },
    };
}

function buildQueueAnalyzerConfig() {
    const keywordStatsText = String(elements.analyzeKeywordStatsInput?.value || "").trim();
    const analyzerConfig = {
        keywordmaster_benchmark: {
            enabled: true,
            max_workers: 6,
            max_keywords: 60,
        },
    };
    if (keywordStatsText) {
        analyzerConfig.keyword_stats_text = keywordStatsText;
    }
    return analyzerConfig;
}

function buildQueuePipelineInput() {
    const collectorConfig = buildQueueCollectorConfig();
    return {
        debug: Boolean(collectorConfig.debug),
        collector: {
            category_source: collectorConfig.category_source,
            options: { ...collectorConfig.options },
            trend_options: { ...collectorConfig.trend_options },
        },
        expander: buildQueueExpanderConfig(),
        analyzer: buildQueueAnalyzerConfig(),
        title_options: typeof buildTitleOptions === "function" ? buildTitleOptions() : {},
    };
}

function formatQueueDateTime(value) {
    const normalized = String(value || "").trim();
    if (!normalized) {
        return "-";
    }
    const date = new Date(normalized);
    if (Number.isNaN(date.getTime())) {
        return normalized;
    }
    return new Intl.DateTimeFormat("ko-KR", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

function formatQueueWeekdays(weekdays) {
    const values = Array.isArray(weekdays) ? weekdays : [];
    const labels = values
        .map((value) => Number.parseInt(String(value), 10))
        .filter((value) => Number.isInteger(value) && value >= 0 && value <= 6)
        .map((value) => QUEUE_WEEKDAY_LABELS[value]);
    return labels.length ? labels.join(" / ") : "매일";
}

function formatQueueStatusLabel(status) {
    const normalized = String(status || "").trim();
    if (normalized === "pending") return "대기";
    if (normalized === "running") return "실행 중";
    if (normalized === "waiting_retry") return "재시도 대기";
    if (normalized === "completed") return "완료";
    if (normalized === "partial") return "부분 완료";
    if (normalized === "failed") return "실패";
    if (normalized === "blocked") return "차단";
    if (normalized === "canceled") return "취소";
    return normalized || "미확인";
}

function formatQueueJobMode(job) {
    return String(job?.item_mode || "").trim() === "category" ? "카테고리" : "시드";
}

function formatQueueJobSource(job) {
    return String(job?.source || "").trim() === "routine" ? "루틴 생성" : "수동 등록";
}

function formatQueueRunnerStateLabel(runner) {
    if (runner?.paused) {
        return runner.pause_reason
            ? `일시정지 · ${runner.pause_reason}`
            : "일시정지";
    }
    if (runner?.running) {
        return "실행 중";
    }
    return "대기 중";
}

function formatQueueOutputLabel(pathValue) {
    const normalized = String(pathValue || "").trim();
    if (!normalized) {
        return "-";
    }
    const parts = normalized.split(/[\\/]+/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : normalized;
}

function escapeQueueAttr(value) {
    return escapeHtml(String(value || ""));
}

function canCancelQueueJob(job) {
    const status = String(job?.status || "").trim();
    return !["completed", "partial", "failed", "canceled"].includes(status);
}

function getQueueJobItemValues(job) {
    const items = Array.isArray(job?.items) ? job.items : [];
    return items
        .map((item) => String(item?.value || "").trim())
        .filter(Boolean);
}

function formatQueueJobItemLabel(job) {
    return String(job?.item_mode || "").trim() === "category" ? "카테고리" : "시드";
}

function renderQueueJobItemSummary(job) {
    const values = getQueueJobItemValues(job);
    if (!values.length) {
        return "";
    }
    const label = formatQueueJobItemLabel(job);
    const status = String(job?.status || "").trim();
    const heading = ["completed", "partial", "failed", "canceled"].includes(status)
        ? `실행 ${label}`
        : `등록 ${label}`;
    const previewValues = values.slice(0, 5).map((value) => escapeHtml(value));
    const remainingCount = Math.max(0, values.length - previewValues.length);
    const previewText = previewValues.join(", ");
    const suffix = remainingCount > 0 ? ` 외 ${remainingCount}건` : "";
    if (values.length <= 5) {
        return `<div class="queue-path-note">${heading} ${escapeHtml(String(values.length))}건 · ${previewText}</div>`;
    }
    return `
        <details class="queue-job-item-summary">
            <summary>${heading} ${escapeHtml(String(values.length))}건 보기</summary>
            <div class="queue-path-note">${previewText}${escapeHtml(suffix)}</div>
        </details>
    `;
}

function renderQueueJobCard(job) {
    const completedCount = Number(job?.completed_count || 0);
    const failedCount = Number(job?.failed_count || 0);
    const blockedCount = Number(job?.blocked_count || 0);
    const canceledCount = Number(job?.canceled_count || 0);
    const pendingCount = Number(job?.pending_count || 0);
    const itemCount = Number(job?.item_count || 0);
    const titleMode = String(job?.input_summary?.title_mode || "").trim();
    const titleProvider = String(job?.input_summary?.title_provider || "").trim();
    const lastErrorMessage = String(job?.last_error?.message || "").trim();
    const itemSummary = [
        `${formatQueueJobMode(job)} ${itemCount}건`,
        formatQueueJobSource(job),
        titleMode ? `제목 ${titleMode}${titleProvider ? `:${titleProvider}` : ""}` : "",
    ].filter(Boolean).join(" · ");
    const metaParts = [
        job?.scheduled_for ? `예약 ${formatQueueDateTime(job.scheduled_for)}` : "",
        job?.started_at ? `시작 ${formatQueueDateTime(job.started_at)}` : "",
        job?.finished_at ? `완료 ${formatQueueDateTime(job.finished_at)}` : "",
        job?.next_attempt_at ? `재시도 ${formatQueueDateTime(job.next_attempt_at)}` : "",
        job?.current_item_value ? `현재 ${String(job.current_item_value).trim()}` : "",
    ].filter(Boolean);
    return `
        <article class="queue-item-card">
            <div class="queue-item-head">
                <div class="queue-item-title">
                    <h4>${escapeHtml(String(job?.name || "Queue Job"))}</h4>
                    <p>${escapeHtml(itemSummary)}</p>
                </div>
                <span class="queue-status-pill ${escapeQueueAttr(job?.status)}">${escapeHtml(formatQueueStatusLabel(job?.status))}</span>
            </div>
            <div class="queue-item-meta">
                ${metaParts.map((part) => `<span>${escapeHtml(part)}</span>`).join("") || "<span>등록 시각을 불러오는 중입니다.</span>"}
            </div>
            <div class="queue-mini-grid">
                <div class="queue-mini-stat">
                    <span>완료</span>
                    <strong>${escapeHtml(String(completedCount))}</strong>
                </div>
                <div class="queue-mini-stat">
                    <span>대기</span>
                    <strong>${escapeHtml(String(pendingCount))}</strong>
                </div>
                <div class="queue-mini-stat">
                    <span>실패</span>
                    <strong>${escapeHtml(String(failedCount + blockedCount))}</strong>
                </div>
                <div class="queue-mini-stat">
                    <span>취소</span>
                    <strong>${escapeHtml(String(canceledCount))}</strong>
                </div>
            </div>
            ${renderQueueJobItemSummary(job)}
            ${lastErrorMessage ? `<div class="queue-error">${escapeHtml(lastErrorMessage)}</div>` : ""}
            ${job?.artifact_path ? `<div class="queue-path-note">${escapeHtml(job.artifact_path)}</div>` : ""}
            <div class="queue-item-actions">
                ${job?.artifact_path ? `
                    <button
                        type="button"
                        class="ghost-chip"
                        data-queue-action="download-artifact"
                        data-job-id="${escapeQueueAttr(job?.job_id)}"
                    >엑셀 다운로드</button>
                ` : ""}
                ${canCancelQueueJob(job) ? `
                    <button
                        type="button"
                        class="ghost-btn"
                        data-queue-action="cancel-job"
                        data-job-id="${escapeQueueAttr(job?.job_id)}"
                    >작업 취소</button>
                ` : ""}
            </div>
        </article>
    `;
}

function renderQueueRoutineCard(routine) {
    const categories = Array.isArray(routine?.categories) ? routine.categories : [];
    const titleMode = String(routine?.input_summary?.title_mode || "").trim();
    const titleProvider = String(routine?.input_summary?.title_provider || "").trim();
    const summary = [
        `${categories.length}개 카테고리`,
        `${formatQueueWeekdays(routine?.weekdays)} ${String(routine?.time_of_day || "06:00").trim()}`,
        titleMode ? `제목 ${titleMode}${titleProvider ? `:${titleProvider}` : ""}` : "",
    ].filter(Boolean).join(" · ");
    return `
        <article class="queue-item-card">
            <div class="queue-item-head">
                <div class="queue-item-title">
                    <h4>${escapeHtml(String(routine?.name || "Routine"))}</h4>
                    <p>${escapeHtml(summary)}</p>
                </div>
                <span class="queue-status-pill ${routine?.enabled ? "completed" : "canceled"}">${routine?.enabled ? "활성" : "중지"}</span>
            </div>
            <div class="queue-item-meta">
                <span>다음 실행 ${escapeHtml(formatQueueDateTime(routine?.next_run_at))}</span>
                <span>마지막 생성 ${escapeHtml(routine?.last_enqueued_on || "-")}</span>
            </div>
            <div class="queue-path-note">${escapeHtml(categories.join(", ") || "카테고리가 없습니다.")}</div>
            <div class="queue-item-actions">
                <button
                    type="button"
                    class="ghost-btn"
                    data-queue-action="delete-routine"
                    data-routine-id="${escapeQueueAttr(routine?.routine_id)}"
                >루틴 삭제</button>
            </div>
        </article>
    `;
}

function renderQueuePanel() {
    const snapshot = getQueueSnapshotState();
    const runner = snapshot.runner;
    const jobs = snapshot.jobs;
    const routines = snapshot.routines;
    const selectedSeedCount = parseQueueListText(elements.queueSeedBatchSeedsInput?.value || "").length;
    const selectedCategories = getQueueSelectedCategories();
    const selectedCategoryCount = selectedCategories.length;
    const selectedWeekdays = getQueueSelectedWeekdays();
    const requestPending = Boolean(state.queueRequestInFlight);

    if (elements.queueRunnerStateLabel) {
        elements.queueRunnerStateLabel.textContent = formatQueueRunnerStateLabel(runner);
    }
    if (elements.queueRunnerJobLabel) {
        elements.queueRunnerJobLabel.textContent = runner?.current_job_name
            ? `${runner.current_job_name}${runner?.current_item_value ? ` · ${runner.current_item_value}` : ""}`
            : "대기 중";
    }
    if (elements.queueJobCountLabel) {
        elements.queueJobCountLabel.textContent = `작업 ${jobs.length}건 · 루틴 ${routines.length}건`;
    }
    if (elements.queueOutputDirLabel) {
        elements.queueOutputDirLabel.textContent = formatQueueOutputLabel(snapshot.paths.output_dir);
    }
    if (elements.queueSeedBatchCountLabel) {
        elements.queueSeedBatchCountLabel.textContent = `시드 ${selectedSeedCount}건`;
    }
    if (elements.queueRoutineCountLabel) {
        elements.queueRoutineCountLabel.textContent = `카테고리 ${selectedCategoryCount}건`;
    }
    if (elements.queueSeedBatchHint) {
        elements.queueSeedBatchHint.textContent = requestPending
            ? "Queue 요청을 처리 중입니다."
            : "시드 배치는 등록 시점의 현재 화면 설정을 그대로 묶어 시드별 전체 파이프라인을 순차 실행합니다. 등록 후 화면 설정을 바꿔도 이미 등록한 작업에는 반영되지 않으며, API 키나 트렌드 쿠키가 있으면 상태 파일에도 함께 저장됩니다.";
    }
    if (elements.queueRoutineHint) {
        elements.queueRoutineHint.textContent = selectedWeekdays.length
            ? `${formatQueueWeekdays(selectedWeekdays)} ${String(elements.queueRoutineTimeInput?.value || "06:00")}에 선택한 ${selectedCategoryCount}개 카테고리 작업을 자동 생성합니다. 등록 시점의 현재 화면 설정으로 이후 작업을 만들며, 현재 인증 설정도 상태 파일에 저장될 수 있습니다.`
            : "요일을 최소 1개 선택해야 루틴을 등록할 수 있습니다.";
    }
    if (elements.pauseQueueRunnerButton) {
        elements.pauseQueueRunnerButton.disabled = requestPending || Boolean(runner?.paused);
    }
    if (elements.resumeQueueRunnerButton) {
        elements.resumeQueueRunnerButton.disabled = requestPending || !Boolean(runner?.paused);
    }
    if (elements.submitQueueSeedBatchButton) {
        elements.submitQueueSeedBatchButton.disabled = requestPending || selectedSeedCount === 0;
    }
    if (elements.submitQueueRoutineButton) {
        elements.submitQueueRoutineButton.disabled = requestPending || selectedCategoryCount === 0 || selectedWeekdays.length === 0;
    }
    if (elements.queueJobsList) {
        elements.queueJobsList.innerHTML = jobs.length
            ? jobs.slice(0, 12).map((job) => renderQueueJobCard(job)).join("")
            : '<div class="collector-empty">등록된 작업이 없습니다.</div>';
    }
    if (elements.queueRoutinesList) {
        elements.queueRoutinesList.innerHTML = routines.length
            ? routines.map((routine) => renderQueueRoutineCard(routine)).join("")
            : '<div class="collector-empty">등록된 루틴이 없습니다.</div>';
    }
    if (elements.queueSnapshotStatus) {
        const syncMessage = String(state.queueSyncMessage || "").trim()
            || "스케줄러 상태를 아직 불러오지 않았습니다.";
        const pathNote = snapshot.paths.state_path
            ? `<div class="queue-path-note">상태 파일: ${escapeHtml(snapshot.paths.state_path)}</div>`
            : "";
        elements.queueSnapshotStatus.innerHTML = `${escapeHtml(syncMessage)}${pathNote}`;
    }
}

async function requestQueue(endpoint, options = {}) {
    const startedAt = Date.now();
    let response;
    try {
        response = await fetch(endpoint, {
            method: options.method || "GET",
            headers: options.body ? { "Content-Type": "application/json" } : undefined,
            body: options.body ? JSON.stringify(options.body) : undefined,
        });
    } catch (error) {
        const networkError = new Error("Queue 서버와 연결하지 못했습니다.");
        networkError.code = "queue_network_error";
        networkError.endpoint = endpoint;
        networkError.detail = error instanceof Error ? error.message : String(error);
        networkError.durationMs = Date.now() - startedAt;
        throw networkError;
    }

    const requestId = response.headers.get("X-Request-ID") || "";
    const rawText = await response.text();
    const payload = tryParseJson(rawText);
    if (!response.ok) {
        throw createApiError({
            endpoint,
            requestId,
            statusCode: response.status,
            payload,
            rawText,
            durationMs: Date.now() - startedAt,
        });
    }
    return payload || {};
}

async function refreshQueueSnapshot(options = {}) {
    if (state.queueRequestInFlight && options.background) {
        return null;
    }
    state.queueRequestInFlight = true;
    renderQueuePanel();
    try {
        const payload = await requestQueue("/queue/snapshot");
        state.queueSnapshot = payload.queue || {};
        state.queueSyncMessage = `마지막 동기화 ${formatQueueDateTime(new Date().toISOString())}`;
        renderQueuePanel();
        return state.queueSnapshot;
    } catch (error) {
        const normalizedError = normalizeError(error, { endpoint: "/queue/snapshot" });
        state.queueSyncMessage = normalizedError.message;
        renderQueuePanel();
        if (!options.silent) {
            addLog(normalizedError.message, "error");
        }
        return null;
    } finally {
        state.queueRequestInFlight = false;
        renderQueuePanel();
    }
}

async function runQueueMutation(endpoint, requestOptions, successMessage) {
    if (state.queueRequestInFlight) {
        return null;
    }
    state.queueRequestInFlight = true;
    renderQueuePanel();
    try {
        const payload = await requestQueue(endpoint, requestOptions);
        state.queueSnapshot = payload.queue || state.queueSnapshot || {};
        state.queueSyncMessage = successMessage;
        addLog(successMessage, "success");
        renderQueuePanel();
        return state.queueSnapshot;
    } catch (error) {
        const normalizedError = normalizeError(error, { endpoint });
        state.queueSyncMessage = normalizedError.message;
        addLog(normalizedError.message, "error");
        renderQueuePanel();
        return null;
    } finally {
        state.queueRequestInFlight = false;
        renderQueuePanel();
    }
}

async function pauseQueueRunner() {
    await runQueueMutation(
        "/queue/runner/pause",
        {
            method: "POST",
            body: { reason: "manual_pause_from_dashboard" },
        },
        "Queue runner를 일시정지했습니다.",
    );
}

async function resumeQueueRunner() {
    await runQueueMutation(
        "/queue/runner/resume",
        { method: "POST" },
        "Queue runner를 재개했습니다.",
    );
}

async function submitQueueSeedBatch() {
    const seedKeywordsText = String(elements.queueSeedBatchSeedsInput?.value || "").trim();
    const seeds = parseQueueListText(seedKeywordsText);
    if (!seeds.length) {
        addLog("Queue에 등록할 시드 키워드를 최소 1개 입력해 주세요.", "error");
        renderQueuePanel();
        return;
    }

    const pipeline = buildQueuePipelineInput();
    const collectorConfig = buildQueueCollectorConfig();
    const payload = {
        name: String(elements.queueSeedBatchNameInput?.value || "").trim(),
        seed_keywords_text: seedKeywordsText,
        collector_options: collectorConfig.options,
        title_options: pipeline.title_options,
        pipeline,
        scheduled_for: String(elements.queueSeedBatchScheduleInput?.value || "").trim() || null,
    };

    const snapshot = await runQueueMutation(
        "/queue/jobs/seed-batch",
        {
            method: "POST",
            body: payload,
        },
        `시드 배치 ${seeds.length}건을 Queue에 등록했습니다.`,
    );
    if (!snapshot) {
        return;
    }

    if (elements.queueSeedBatchNameInput) {
        elements.queueSeedBatchNameInput.value = "";
    }
    if (elements.queueSeedBatchScheduleInput) {
        elements.queueSeedBatchScheduleInput.value = "";
    }
    if (elements.queueSeedBatchSeedsInput) {
        elements.queueSeedBatchSeedsInput.value = "";
    }
    renderQueuePanel();
}

async function submitQueueRoutine() {
    const categories = getQueueSelectedCategories();
    const weekdays = getQueueSelectedWeekdays();
    if (!categories.length) {
        addLog("루틴에 등록할 카테고리를 최소 1개 선택해 주세요.", "error");
        renderQueuePanel();
        return;
    }
    if (!weekdays.length) {
        addLog("루틴 실행 요일을 최소 1개 선택해 주세요.", "error");
        renderQueuePanel();
        return;
    }

    const pipeline = buildQueuePipelineInput();
    const collectorConfig = buildQueueCollectorConfig();
    const timeOfDay = String(elements.queueRoutineTimeInput?.value || "06:00").trim() || "06:00";
    const payload = {
        name: String(elements.queueRoutineNameInput?.value || "").trim(),
        categories,
        time_of_day: `${timeOfDay}:00`,
        weekdays,
        category_source: collectorConfig.category_source,
        collector_options: collectorConfig.options,
        title_options: pipeline.title_options,
        pipeline,
    };

    const snapshot = await runQueueMutation(
        "/queue/routines/daily-category",
        {
            method: "POST",
            body: payload,
        },
        `일일 카테고리 루틴 ${categories.length}건을 등록했습니다.`,
    );
    if (!snapshot) {
        return;
    }

    if (elements.queueRoutineNameInput) {
        elements.queueRoutineNameInput.value = "";
    }
    renderQueuePanel();
}

async function handleQueueJobActionClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-queue-action]");
    if (!trigger) {
        return;
    }
    const action = trigger.getAttribute("data-queue-action") || "";
    const jobId = String(trigger.getAttribute("data-job-id") || "").trim();
    if (action === "download-artifact" && jobId) {
        window.location.href = `/queue/jobs/${encodeURIComponent(jobId)}/artifact`;
        return;
    }
    if (action === "cancel-job" && jobId) {
        await runQueueMutation(
            `/queue/jobs/${encodeURIComponent(jobId)}/cancel`,
            { method: "POST" },
            "Queue 작업을 취소했습니다.",
        );
    }
}

async function handleQueueRoutineActionClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-queue-action]");
    if (!trigger) {
        return;
    }
    const action = trigger.getAttribute("data-queue-action") || "";
    const routineId = String(trigger.getAttribute("data-routine-id") || "").trim();
    if (action === "delete-routine" && routineId) {
        await runQueueMutation(
            `/queue/routines/${encodeURIComponent(routineId)}`,
            { method: "DELETE" },
            "Queue 루틴을 삭제했습니다.",
        );
    }
}

function getUtilityDrawerTab() {
    const safeTab = String(state.utilityDrawerTab || "").trim();
    return QUEUE_UTILITY_TABS.includes(safeTab) ? safeTab : "diagnostics";
}

function setUtilityDrawerTab(tabKey) {
    const safeTab = QUEUE_UTILITY_TABS.includes(String(tabKey || "").trim())
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
    if (safeTab === "settings" && typeof window.refreshOperationSettings === "function") {
        window.refreshOperationSettings();
    }
    if (safeTab === "history") {
        renderExecutionHistoryPanel();
    }
    if (safeTab === "vault") {
        renderKeywordVaultPanel();
    }
    if (safeTab === "queue") {
        renderQueuePanel();
        void refreshQueueSnapshot({ silent: true, background: true });
    }
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
        || button?.matches?.("#toggleTitleAdvancedButton")
        || button?.matches?.("#refreshQueueSnapshotButton")
        || button?.matches?.("#pauseQueueRunnerButton")
        || button?.matches?.("#resumeQueueRunnerButton")
        || button?.matches?.("#submitQueueSeedBatchButton")
        || button?.matches?.("#submitQueueRoutineButton")
        || button?.matches?.("#refreshExecutionHistoryButton")
        || button?.matches?.("#clearExecutionHistoryButton")
        || button?.matches?.("#refreshKeywordVaultButton")
        || button?.matches?.("#clearKeywordVaultButton")
        || button?.matches?.("#keywordVaultQuickAddButton")
        || button?.matches?.("[data-queue-action]")
        || button?.matches?.("[data-history-action]")
        || button?.matches?.("[data-vault-action]")
        || button?.matches?.("[data-topic-seed-action]")
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
    const presetButtonsHtml = (Array.isArray(SELECTION_PRESET_ORDER) ? SELECTION_PRESET_ORDER : Object.keys(GRADE_PRESET_MAP || {}))
        .map((presetKey) => {
            const preset = getSelectionPresetConfig(presetKey);
            if (!preset) {
                return "";
            }
            const presetProfitability = normalizeProfitabilityList(preset.profitability || []);
            const presetAttackability = normalizeAttackabilityList(preset.attackability || []);
            const isActive = presetProfitability.length === selectedProfitability.length
                && presetAttackability.length === selectedAttackability.length
                && presetProfitability.every((grade) => selectedProfitabilitySet.has(grade))
                && presetAttackability.every((grade) => selectedAttackabilitySet.has(grade));
            return `
                <button type="button" class="ghost-chip${isActive ? " active" : ""}" data-inline-action="apply_analysis_grade_preset" data-grade-preset="${escapeHtml(presetKey)}">${escapeHtml(preset.label || presetKey)}</button>
            `;
        })
        .join("");

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
                <span class="analysis-grade-group-label">노출도</span>
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
                ${presetButtonsHtml}
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
            <td>${renderVaultInlineAction(item.keyword, "analyzed")}</td>
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
                <span>수익성은 CPC, 클릭 잠재력, 검색량을 함께 보고, 노출도는 opportunity, 실제 클릭 활동, 경쟁 강도, 검색량을 함께 반영합니다. 희소성은 보조 신호로만 씁니다.</span>
            </div>
            <div class="analysis-filter-tip">
                <strong>선별 프리셋</strong>
                <span>균형형은 A~C · 1~3, 수익형은 A~B · 1~4, 롱테일 탐색형은 B~D · 1~3 조합입니다. 자동 선별은 황금 조합이 부족할 때 글감 후보까지 함께 남깁니다.</span>
            </div>
            <div class="queue-form-actions result-inline-actions">
                <span class="queue-inline-meta">표시 목록 ${filteredItems.length}건</span>
                <button type="button" class="ghost-chip" data-inline-action="save_visible_analyzed_to_vault">표시 목록 보관</button>
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
                            <th>노출도</th>
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
                            <th>보관</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="14">조건에 맞는 키워드가 없습니다.</td></tr>`}</tbody>
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
    const selectedResult = state.results.selected || {};
    const summary = selectedResult.longtail_summary || {};
    const suggestions = Array.isArray(selectedResult.longtail_suggestions)
        ? selectedResult.longtail_suggestions
        : [];
    const hasVerified = Number(summary.verified_count || 0) > 0;
    const shouldRebuild = hasPendingLongtailOptionChanges(selectedResult);
    const optionStripHtml = renderLongtailOptionStrip(selectedResult);
    const actionLabel = shouldRebuild
        ? "롱테일 다시 조합"
        : (hasVerified ? "롱테일 다시 검증" : "롱테일 검증 실행");

    if (!suggestions.length && !summary.suggestion_count) {
        return `
            <section class="longtail-board">
                <div class="longtail-head">
                    <div>
                        <span class="field-label">롱테일 조합</span>
                        <p class="input-help compact-help">클러스터에서 중심 키워드와 핵심 의도만 먼저 조합합니다. 가이드와 체크리스트는 필요할 때만 아래에서 켜세요.</p>
                    </div>
                    <div class="longtail-actions">
                        <span class="analysis-source-pill type">과한 템플릿 토큰 기본 제외</span>
                        <button
                            type="button"
                            class="subtle-btn"
                            data-inline-action="verify_longtail_suggestions"
                            ${state.isBusy ? "disabled" : ""}
                        >${actionLabel}</button>
                    </div>
                </div>
                ${optionStripHtml}
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
                    <p class="input-help compact-help">클러스터 기반 후보를 먼저 제안하고, 검증 실행 시 다시 분석해 실제 우선순위를 판정합니다. 추가 토큰은 필요할 때만 켜서 다시 조합하세요.</p>
                </div>
                <div class="longtail-actions">
                    <span class="analysis-source-pill type">클러스터당 최대 3개</span>
                    <button
                        type="button"
                        class="subtle-btn"
                        data-inline-action="verify_longtail_suggestions"
                        ${state.isBusy ? "disabled" : ""}
                    >${actionLabel}</button>
                </div>
            </div>
            ${optionStripHtml}
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

function formatIntentKeyLabel(intentKey) {
    const labelMap = {
        commercial: "비교/추천",
        info: "정보형",
        review: "후기형",
        action: "행동형",
        problem: "문제 해결형",
        location: "위치형",
        policy: "정책형",
        general: "일반형",
    };
    return labelMap[String(intentKey || "").trim()] || "일반형";
}

function formatCannibalizationRiskLabel(riskLevel) {
    if (riskLevel === "high") {
        return "고위험";
    }
    if (riskLevel === "medium") {
        return "중간 위험";
    }
    return "낮은 위험";
}

function formatCannibalizationActionLabel(action) {
    if (action === "merge") {
        return "한 글로 병합 권장";
    }
    if (action === "split") {
        return "메인/서브 분리";
    }
    return "수동 검토";
}

function renderCannibalizationBoard() {
    const report = state.results.selected?.cannibalization_report || {};
    const summary = report.summary || {};
    const groups = Array.isArray(report.groups) ? report.groups : [];
    const candidateCount = Number(summary.candidate_count || 0);

    if (!candidateCount && !groups.length) {
        return "";
    }

    return `
        <section class="cannibalization-board">
            <div class="cannibalization-head">
                <div>
                    <span class="field-label">카니벌라이제이션 검사</span>
                    <p class="input-help compact-help">같은 토픽과 의도로 겹치는 후보를 묶어서, 따로 쓸지 합칠지 빠르게 판단할 수 있게 정리합니다.</p>
                </div>
                <div class="cannibalization-actions">
                    <span class="analysis-source-pill type">후보 ${escapeHtml(String(candidateCount))}건 검사</span>
                </div>
            </div>
            <div class="analysis-summary-strip cannibalization-summary-strip">
                <div class="collector-stat-card">
                    <span>충돌 묶음</span>
                    <strong>${escapeHtml(String(summary.issue_group_count || 0))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>고위험</span>
                    <strong>${escapeHtml(String(summary.high_risk_count || 0))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>중간 위험</span>
                    <strong>${escapeHtml(String(summary.medium_risk_count || 0))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>분리 가능</span>
                    <strong>${escapeHtml(String(summary.safe_split_cluster_count || 0))}</strong>
                </div>
            </div>
            ${groups.length
                ? `
                    <div class="cannibalization-grid">
                        ${groups.map((group) => `
                            <article class="cannibalization-card ${escapeHtml(group.risk_level || "medium")}">
                                <div class="cannibalization-card-head">
                                    <div class="cannibalization-card-copy">
                                        <span class="content-map-kicker">
                                            ${escapeHtml(group.cluster_id || "cluster")}
                                            · ${escapeHtml(formatIntentKeyLabel(group.intent_key))}
                                        </span>
                                        <h4>${escapeHtml(group.representative_keyword || group.primary_keyword || "-")}</h4>
                                        <p>${escapeHtml(group.primary_keyword || "-")} 중심 · 후보 ${escapeHtml(String(group.candidate_count || 0))}개 · 겹침 ${escapeHtml(String(group.overlap_score || 0))}%</p>
                                    </div>
                                    <div class="cannibalization-card-badges">
                                        <span class="cannibalization-risk-pill ${escapeHtml(group.risk_level || "medium")}">${escapeHtml(formatCannibalizationRiskLabel(group.risk_level))}</span>
                                        <span class="badge">${escapeHtml(formatCannibalizationActionLabel(group.recommended_action))}</span>
                                    </div>
                                </div>
                                ${Array.isArray(group.shared_terms) && group.shared_terms.length
                                    ? `
                                        <div class="cannibalization-term-strip">
                                            ${group.shared_terms.map((term) => `<span class="badge">${escapeHtml(term)}</span>`).join("")}
                                        </div>
                                    `
                                    : ""}
                                <div class="cannibalization-items">
                                    ${(group.items || []).map((item) => `
                                        <div class="cannibalization-item">
                                            <div>
                                                <strong>${escapeHtml(item.keyword || "-")}</strong>
                                                <span>${escapeHtml(item.source_type === "longtail" ? "롱테일" : "선별")}</span>
                                            </div>
                                            <div class="cannibalization-item-meta">
                                                ${item.is_primary ? '<span class="badge">메인 후보</span>' : ""}
                                                <span class="badge">${escapeHtml(String(item.verification_status || item.source_type || ""))}</span>
                                                <span class="badge">점수 ${escapeHtml(formatNumber(item.score))}</span>
                                            </div>
                                        </div>
                                    `).join("")}
                                </div>
                            </article>
                        `).join("")}
                    </div>
                `
                : `
                    <div class="collector-empty cannibalization-empty">
                        현재 선별 결과 기준으로는 서로 잡아먹을 가능성이 큰 키워드 묶음이 없습니다.
                    </div>
                `}
        </section>
    `;
}

function formatSerpCompetitionLevelLabel(level) {
    if (level === "high") {
        return "경쟁 높음";
    }
    if (level === "medium") {
        return "경쟁 보통";
    }
    return "경쟁 낮음";
}

function formatSerpCandidateTypeLabel(candidateType) {
    return candidateType === "longtail" ? "롱테일 후보" : "선별 키워드";
}

function formatSerpSourceBucketLabel(bucket) {
    const labelMap = {
        ugc: "블로그/카페",
        official: "공식/사전",
        news: "뉴스",
        store: "쇼핑/스토어",
        community: "커뮤니티",
        other: "기타",
    };
    return labelMap[String(bucket || "").trim()] || "기타";
}

function renderSerpCompetitionBoard() {
    const selectedKeywords = Array.isArray(state.results.selected?.selected_keywords)
        ? state.results.selected.selected_keywords
        : [];
    if (!selectedKeywords.length) {
        return "";
    }

    const serpSummary = state.results.selected?.serp_competition_summary || null;
    const summary = serpSummary?.summary || {};
    const queries = Array.isArray(serpSummary?.queries) ? serpSummary.queries : [];

    return `
        <section class="serp-board">
            <div class="serp-head">
                <div>
                    <span class="field-label">SERP 경쟁 요약</span>
                    <p class="input-help compact-help">네이버 검색 상위 제목을 모아 의도 쏠림, 반복 용어, 도메인 편중을 빠르게 확인합니다.</p>
                </div>
                <div class="serp-actions">
                    ${queries.length
                        ? `<span class="analysis-source-pill type">최근 ${escapeHtml(String(summary.success_count || 0))}개 쿼리 성공</span>`
                        : ""}
                    <button
                        type="button"
                        class="subtle-btn"
                        data-inline-action="run_serp_competition_summary"
                        ${state.isBusy ? "disabled" : ""}
                    >${queries.length ? "SERP 다시 요약" : "SERP 경쟁 요약 실행"}</button>
                </div>
            </div>
            ${queries.length
                ? `
                    <div class="analysis-summary-strip serp-summary-strip">
                        <div class="collector-stat-card">
                            <span>분석 쿼리</span>
                            <strong>${escapeHtml(String(summary.query_count || queries.length))}</strong>
                        </div>
                        <div class="collector-stat-card">
                            <span>경쟁 높음</span>
                            <strong>${escapeHtml(String(summary.high_competition_count || 0))}</strong>
                        </div>
                        <div class="collector-stat-card">
                            <span>경쟁 보통</span>
                            <strong>${escapeHtml(String(summary.medium_competition_count || 0))}</strong>
                        </div>
                        <div class="collector-stat-card">
                            <span>경쟁 낮음</span>
                            <strong>${escapeHtml(String(summary.low_competition_count || 0))}</strong>
                        </div>
                    </div>
                    <div class="serp-grid">
                        ${queries.map((query) => `
                            <article class="serp-card ${escapeHtml(query.competition_level || "low")}">
                                <div class="serp-card-head">
                                    <div class="serp-card-copy">
                                        <span class="content-map-kicker">${escapeHtml(formatSerpCandidateTypeLabel(query.candidate_type))}</span>
                                        <h4>${escapeHtml(query.query || "-")}</h4>
                                        <p>
                                            ${query.status === "success"
                                                ? `${escapeHtml(formatSerpCompetitionLevelLabel(query.competition_level))} · 점수 ${escapeHtml(String(query.competition_score || 0))}`
                                                : "검색 결과를 요약하지 못했습니다."}
                                        </p>
                                    </div>
                                    <div class="serp-card-badges">
                                        <span class="serp-level-pill ${escapeHtml(query.competition_level || "low")}">${escapeHtml(formatSerpCompetitionLevelLabel(query.competition_level))}</span>
                                        ${query.search_url
                                            ? `<a class="ghost-btn serp-search-link" href="${escapeHtml(query.search_url)}" target="_blank" rel="noopener noreferrer">검색 열기</a>`
                                            : ""}
                                    </div>
                                </div>
                                ${query.status === "success"
                                    ? `
                                        <div class="serp-meta-strip">
                                            <span class="badge">의도 ${escapeHtml((query.dominant_intents || []).map((item) => formatIntentKeyLabel(item.intent_key)).join(", ") || "혼합")}</span>
                                            <span class="badge">공통어 ${escapeHtml((query.common_terms || []).join(", ") || "없음")}</span>
                                            <span class="badge">도메인 ${escapeHtml((query.top_domains || []).map((item) => item.domain).join(", ") || "혼합")}</span>
                                        </div>
                                        <div class="serp-title-list">
                                            ${(query.top_titles || []).map((item) => `
                                                <div class="serp-title-item">
                                                    <div>
                                                        <strong>${escapeHtml(item.title || "-")}</strong>
                                                        <span>${escapeHtml(item.domain || "-")}</span>
                                                    </div>
                                                    <div class="serp-title-meta">
                                                        <span class="badge">#${escapeHtml(String(item.rank || 0))}</span>
                                                        <span class="badge">${escapeHtml(formatSerpSourceBucketLabel(item.source_bucket))}</span>
                                                    </div>
                                                </div>
                                            `).join("")}
                                        </div>
                                    `
                                    : `
                                        <div class="collector-empty serp-empty">
                                            ${escapeHtml(query.error === "no_results" ? "읽을 수 있는 상위 제목을 찾지 못했습니다." : "SERP 수집 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")}
                                        </div>
                                    `}
                            </article>
                        `).join("")}
                    </div>
                `
                : `
                    <div class="collector-empty serp-empty">
                        아직 SERP 경쟁 요약을 실행하지 않았습니다. 버튼을 누르면 상위 노출 제목 패턴을 바로 정리합니다.
                    </div>
                `}
        </section>
    `;
}

function renderResultsWorkbenchRail(context = {}) {
    const activeViewKey = String(context.activeViewKey || "").trim();
    const expandedItems = Array.isArray(context.expandedItems) ? context.expandedItems : [];
    const analyzedItems = Array.isArray(context.analyzedItems) ? context.analyzedItems : [];
    const selectedItems = Array.isArray(context.selectedItems) ? context.selectedItems : [];
    const generatedTitles = Array.isArray(context.generatedTitles) ? context.generatedTitles : [];
    const cards = [
        renderResultsRailSummaryCard({
            activeViewKey,
            expandedItems,
            analyzedItems,
            selectedItems,
            generatedTitles,
            lowQualityTitleCount: Number(context.lowQualityTitleCount || 0),
            selectedProfile: context.selectedProfile || null,
        }),
        renderSelectedKeywordRailCard(selectedItems, context.selectedProfile || null),
        renderTitleWorkflowRailCard({
            activeViewKey,
            selectedItems,
            generatedTitles,
            lowQualityTitleCount: Number(context.lowQualityTitleCount || 0),
        }),
    ].filter(Boolean);

    if (activeViewKey === "expanded" || activeViewKey === "analyzed") {
        const workbenchHtml = renderWorkbenchAside(expandedItems, analyzedItems);
        if (String(workbenchHtml || "").trim()) {
            cards.push(workbenchHtml);
        }
    }

    return cards.join("");
}

function renderResultsRailSummaryCard({
    activeViewKey,
    expandedItems,
    analyzedItems,
    selectedItems,
    generatedTitles,
    lowQualityTitleCount,
    selectedProfile,
}) {
    const selectedResult = state.results.selected || {};
    const titleGenerationMeta = state.results.titled?.generation_meta || {};
    const longtailSummary = selectedResult.longtail_summary || {};
    const serpSummary = selectedResult.serp_competition_summary?.summary || {};
    const cannibalizationSummary = selectedResult.cannibalization_report?.summary || {};
    const analyzedMeasuredCount = analyzedItems.filter(isMeasuredItem).length;
    const analyzedQuickCount = analyzedItems.filter(isGoldenCandidate).length;
    const selectedGoldCount = selectedItems.filter((item) => resolveGoldenBucket(item) === "gold").length;
    const expandedQueueSize = Number(state.results.expanded?.stream_meta?.queueSize || 0);
    const titleTargetCount = new Set(generatedTitles.map((item) => getTitleTargetIdentity(item)).filter(Boolean)).size;
    let kicker = "";
    let title = "";
    let subtitle = "";
    let stats = [];
    let actions = [];

    if (generatedTitles.length) {
        kicker = "Stage 5";
        title = "제목 결과";
        subtitle = buildEnhancedTitleGenerationSummaryText(titleGenerationMeta, generatedTitles);
        stats = [
            { label: "생성 묶음", value: countItems(generatedTitles) },
            { label: "자동 재작성", value: typeof formatTitleAutoRetryStat === "function" ? formatTitleAutoRetryStat(titleGenerationMeta) : "0회" },
            { label: "모델 승격", value: typeof formatTitleModelEscalationStat === "function" ? formatTitleModelEscalationStat(titleGenerationMeta) : "0회" },
            { label: "재생성 권장", value: lowQualityTitleCount },
        ];
        actions = [
            activeViewKey !== "titled"
                ? '<button type="button" class="subtle-btn" data-result-tab="titled">제목 결과 보기</button>'
                : "",
            lowQualityTitleCount
                ? '<button type="button" class="inline-action-btn" data-inline-action="rerun_title_flagged">기준 미달 다시 생성</button>'
                : "",
            selectedItems.length
                ? '<button type="button" class="inline-action-btn" data-inline-action="rerun_title">전체 다시 생성</button>'
                : "",
        ];
    } else if (selectedItems.length) {
        kicker = "Stage 4";
        title = "선별 완료";
        subtitle = summarizeSelectionProfileRail(selectedProfile) || "선별된 키워드를 제목 생성 단계로 바로 넘길 수 있습니다.";
        stats = [
            { label: "선별", value: countItems(selectedItems) },
            { label: "골드", value: selectedGoldCount },
            { label: "롱테일 통과", value: Number(longtailSummary.pass_count || 0) },
            { label: "SERP 고경쟁", value: Number(serpSummary.high_competition_count || 0) },
            { label: "충돌 고위험", value: Number(cannibalizationSummary.high_risk_count || 0) },
        ];
        actions = [
            activeViewKey !== "selected"
                ? '<button type="button" class="subtle-btn" data-result-tab="selected">선별 보드 보기</button>'
                : "",
            '<button type="button" class="inline-action-btn" data-inline-action="continue_title">제목 생성</button>',
        ];
    } else if (analyzedItems.length) {
        kicker = "Stage 3";
        title = "분석 완료";
        subtitle = `${countItems(analyzedItems)}건을 검증했습니다. 필터를 다듬거나 바로 선별 단계로 넘길 수 있습니다.`;
        stats = [
            { label: "검증", value: countItems(analyzedItems) },
            { label: "실측", value: analyzedMeasuredCount },
            { label: getQuickCandidateLabel(), value: analyzedQuickCount },
        ];
        actions = [
            activeViewKey !== "analyzed"
                ? '<button type="button" class="subtle-btn" data-result-tab="analyzed">검증 보기</button>'
                : "",
            '<button type="button" class="inline-action-btn" data-inline-action="continue_select">선별 이어가기</button>',
        ];
    } else if (
        expandedItems.length
        || state.stageStatus.expanded.state === "running"
        || state.stageStatus.analyzed.state === "running"
        || state.stageStatus.expanded.state === "cancelled"
        || state.stageStatus.analyzed.state === "cancelled"
    ) {
        kicker = "Stage 2";
        title = "작업대 진행";
        subtitle = expandedItems.length
            ? "확장 결과를 검증 테이블로 넘겨 선별 후보를 만들 수 있습니다."
            : (state.stageStatus.expanded.message || state.stageStatus.analyzed.message || "확장 작업이 준비되면 이 패널에서 다음 단계를 바로 이어갈 수 있습니다.");
        stats = [
            { label: "확장", value: countItems(expandedItems) },
            { label: "검증", value: countItems(analyzedItems) },
            { label: "대기", value: expandedQueueSize },
        ];
        actions = [
            activeViewKey !== "expanded"
                ? '<button type="button" class="subtle-btn" data-result-tab="expanded">작업대 보기</button>'
                : "",
            expandedItems.length
                ? '<button type="button" class="inline-action-btn" data-inline-action="continue_analyze">분석 이어가기</button>'
                : "",
        ];
    } else {
        return "";
    }

    return renderResultsRailSection({
        kicker,
        title,
        subtitle,
        stats,
        actions,
    });
}

function renderSelectedKeywordRailCard(items, selectedProfile) {
    const topItems = Array.isArray(items) ? items.slice(0, 5) : [];
    if (!topItems.length) {
        return "";
    }

    const listHtml = `
        <div class="results-rail-keyword-list">
            ${topItems.map((item) => {
                const badges = [
                    renderProfitabilityBadge(resolveProfitabilityGrade(item)),
                    renderAttackabilityBadge(resolveAttackabilityGrade(item)),
                    renderComboBadge(resolveComboGrade(item)),
                    renderGoldenBucketPill(resolveGoldenBucket(item)),
                ].filter(Boolean);
                return `
                    <div class="results-rail-keyword">
                        <div class="results-rail-keyword-copy">
                            <strong>${escapeHtml(item.keyword || "-")}</strong>
                            <span>${escapeHtml(`검색량 ${formatNumber(item.metrics?.volume)} / CPC ${formatNumber(item.metrics?.cpc)} / 점수 ${formatNumber(item.score)}`)}</span>
                        </div>
                        <div class="results-rail-keyword-badges">${badges.join("")}</div>
                    </div>
                `;
            }).join("")}
        </div>
    `;

    return renderResultsRailSection({
        kicker: "Selection",
        title: "선별 키워드 패널",
        subtitle: summarizeSelectionProfileRail(selectedProfile) || "지금 바로 다음 단계에 보낼 상위 후보입니다.",
        bodyHtml: listHtml,
    });
}

function renderTitleWorkflowRailCard({
    activeViewKey,
    selectedItems,
    generatedTitles,
    lowQualityTitleCount,
}) {
    const hasTargets = generatedTitles.length || selectedItems.length;
    if (!hasTargets) {
        return "";
    }

    const titleSettings = getTitleSettingsFormState();
    const generationMeta = state.results.titled?.generation_meta || {};
    const settingsSummary = buildTitleRunSummary(titleSettings);
    const retrySummary = generatedTitles.length && typeof buildTitleGenerationRetrySummary === "function"
        ? buildTitleGenerationRetrySummary(generationMeta)
        : "";
    const previewItems = generatedTitles.length ? generatedTitles.slice(0, 4) : selectedItems.slice(0, 4);
    const previewHtml = generatedTitles.length
        ? `
            <div class="results-rail-target-list">
                ${previewItems.map((item) => {
                    const naverHomeCount = Array.isArray(item.titles?.naver_home) ? item.titles.naver_home.length : 0;
                    const blogCount = Array.isArray(item.titles?.blog) ? item.titles.blog.length : 0;
                    return `
                        <div class="results-rail-target-item">
                            <div class="results-rail-target-copy">
                                <strong>${escapeHtml(item.keyword || "-")}</strong>
                                <span>${escapeHtml(String(item.target_mode_label || item.target_mode || "단일"))}</span>
                            </div>
                            <div class="results-rail-target-badges">
                                <span class="badge">홈 ${escapeHtml(String(naverHomeCount))}</span>
                                <span class="badge">블로그 ${escapeHtml(String(blogCount))}</span>
                            </div>
                        </div>
                    `;
                }).join("")}
            </div>
        `
        : `
            <div class="results-rail-target-list">
                ${previewItems.map((item) => `
                    <div class="results-rail-target-item">
                        <div class="results-rail-target-copy">
                            <strong>${escapeHtml(item.keyword || "-")}</strong>
                            <span>제목 생성 대기</span>
                        </div>
                        <div class="results-rail-target-badges">
                            ${renderComboBadge(resolveComboGrade(item))}
                            ${renderGoldenBucketPill(resolveGoldenBucket(item))}
                        </div>
                    </div>
                `).join("")}
            </div>
        `;

    return renderResultsRailSection({
        kicker: "Title",
        title: "제목 워크플로",
        subtitle: settingsSummary,
        stats: [
            { label: "대상", value: generatedTitles.length || countItems(selectedItems) },
            { label: "자동 재작성", value: generatedTitles.length && typeof formatTitleAutoRetryStat === "function" ? formatTitleAutoRetryStat(generationMeta) : "대기" },
            { label: "모델 승격", value: generatedTitles.length && typeof formatTitleModelEscalationStat === "function" ? formatTitleModelEscalationStat(generationMeta) : "대기" },
            { label: "재생성 권장", value: lowQualityTitleCount },
        ],
        bodyHtml: `
            <div class="results-rail-note">
                <strong>${generatedTitles.length ? "최근 생성 상태" : "현재 생성 설정"}</strong>
                <span>${escapeHtml(generatedTitles.length
                    ? buildEnhancedTitleGenerationSummaryText(generationMeta, generatedTitles)
                    : "선별된 키워드를 제목 생성 대상으로 유지한 상태입니다.")}</span>
            </div>
            ${generatedTitles.length ? `
                <div class="results-rail-note">
                    <strong>자동 재작성 메타</strong>
                    <span>${escapeHtml(retrySummary || "자동 재작성 0회 / 모델 승격 없음")}</span>
                </div>
            ` : ""}
            ${previewHtml}
        `,
        actions: [
            generatedTitles.length && activeViewKey !== "titled"
                ? '<button type="button" class="subtle-btn" data-result-tab="titled">제목 탭 열기</button>'
                : "",
            !generatedTitles.length && selectedItems.length
                ? '<button type="button" class="inline-action-btn" data-inline-action="continue_title">현재 설정으로 생성</button>'
                : "",
        ],
    });
}

function renderResultsRailSection({
    kicker = "",
    title = "",
    subtitle = "",
    stats = [],
    bodyHtml = "",
    actions = [],
}) {
    const statGridHtml = renderResultsRailStatGrid(stats);
    const actionHtml = actions.filter(Boolean).length
        ? `<div class="results-rail-actions">${actions.filter(Boolean).join("")}</div>`
        : "";
    return `
        <section class="workbench-side-card results-rail-card">
            <div class="workbench-side-head">
                ${kicker ? `<span class="panel-kicker">${escapeHtml(kicker)}</span>` : ""}
                <strong>${escapeHtml(title)}</strong>
                ${subtitle ? `<span>${escapeHtml(subtitle)}</span>` : ""}
            </div>
            ${statGridHtml}
            ${bodyHtml}
            ${actionHtml}
        </section>
    `;
}

function renderResultsRailStatGrid(stats) {
    const entries = (stats || []).filter((item) => item && item.value !== undefined && item.value !== null && Number(item.value || 0) > 0);
    if (!entries.length) {
        return "";
    }
    return `
        <div class="results-rail-stat-grid">
            ${entries.map((item) => `
                <div class="results-rail-stat">
                    <span>${escapeHtml(item.label || "")}</span>
                    <strong>${escapeHtml(String(item.value))}</strong>
                </div>
            `).join("")}
        </div>
    `;
}

function summarizeSelectionProfileRail(profile) {
    if (!profile) {
        return "";
    }

    if (profile.mode === "combo_filter") {
        const presetKey = String(profile.preset_key || "").trim();
        const presetLabel = String(profile.preset_label || resolveSelectionPresetLabel(presetKey)).trim();
        const profitability = Array.isArray(profile.allowed_profitability_grades)
            ? profile.allowed_profitability_grades.filter(Boolean).join(", ")
            : "";
        const attackability = Array.isArray(profile.allowed_attackability_grades)
            ? profile.allowed_attackability_grades.filter(Boolean).join(", ")
            : "";
        if (profitability || attackability) {
            if (presetKey && presetKey !== "custom" && presetKey !== "all" && presetLabel) {
                return `${presetLabel} / 수익성 ${profitability || "-"} / 노출도 ${attackability || "-"}`;
            }
            return `수익성 ${profitability || "-"} / 노출도 ${attackability || "-"}`;
        }
        return "2축 조합 필터 기준";
    }

    const grades = Array.isArray(profile.allowed_grades) ? profile.allowed_grades.filter(Boolean) : [];
    if (profile.mode === "grade_filter") {
        return grades.length ? `등급 필터 ${grades.join(", ")}` : "등급 필터 기준";
    }
    if (profile.mode === "default" && profile.has_editorial_support) {
        return "자동 선별 / 글감 후보 포함";
    }
    return grades.length ? `자동 선별 + 등급 ${grades.join(", ")}` : "자동 선별 기준";
}

function renderSelectedList(items) {
    const goldCount = (items || []).filter((item) => resolveGoldenBucket(item) === "gold").length;
    const promisingCount = (items || []).filter((item) => resolveGoldenBucket(item) === "promising").length;
    const editorialCount = (items || []).filter((item) => String(item?.selection_mode || "").trim() === "editorial_support").length;
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
            <td>${renderVaultInlineAction(item.keyword, "selected")}</td>
        </tr>
    `).join("");

    return `
        <div class="analysis-console">
            ${renderContentMapBoard()}
            ${renderLongtailBoard()}
            ${renderCannibalizationBoard()}
            ${renderSerpCompetitionBoard()}
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
                <div class="collector-stat-card">
                    <span>글감 후보</span>
                    <strong>${escapeHtml(String(editorialCount))}</strong>
                </div>
            </div>
            <div class="queue-form-actions result-inline-actions">
                <span class="queue-inline-meta">선별 결과 ${countItems(items)}건</span>
                <button type="button" class="ghost-chip" data-inline-action="save_selected_to_vault">선별 결과 보관</button>
            </div>
            <div class="expanded-table-wrap" data-preserve-scroll-key="selected-table">
                <table class="expanded-table selected-table compact">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>키워드</th>
                            <th>수익성</th>
                            <th>노출도</th>
                            <th>조합</th>
                            <th>분류</th>
                            <th>총점</th>
                            <th>검색량</th>
                            <th>CPC</th>
                            <th>opportunity</th>
                            <th>출처</th>
                            <th>보관</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="12">선별 결과가 없습니다.</td></tr>`}</tbody>
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
                <span>이제 총점은 참고값이고, 실제 선별은 수익성/노출도 조합으로 봅니다.</span>
            </div>
            <div class="workbench-guide-list">
                ${[
                    [renderProfitabilityBadge("A"), "A: 72+ 높은 수익성"],
                    [renderProfitabilityBadge("B"), "B: 56+ 양호한 수익성"],
                    [renderProfitabilityBadge("C"), "C: 38+ 보통 수익성"],
                    [renderProfitabilityBadge("D"), "D: 38 미만 낮은 수익성"],
                    [renderAttackabilityBadge("1"), "1: 74+ 상위 노출 가능성 높음"],
                    [renderAttackabilityBadge("2"), "2: 58+ 노출 여지 있음"],
                    [renderAttackabilityBadge("3"), "3: 40+ 경쟁 주의"],
                    [renderAttackabilityBadge("4"), "4: 40 미만 노출 어려움"],
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

    const longtailOptionTrigger = event.target.closest("[data-longtail-option-key]");
    if (longtailOptionTrigger) {
        toggleLongtailOptionalSuffixKey(longtailOptionTrigger.getAttribute("data-longtail-option-key") || "");
        renderResults();
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
            runWithGuard(
                runLongtailVerification,
                hasPendingLongtailOptionChanges(state.results.selected || {})
                    ? "롱테일 다시 조합/검증 실행 중"
                    : "롱테일 검증 실행 중",
            );
            return;
        }
        if (action === "run_serp_competition_summary") {
            runWithGuard(runSerpCompetitionSummary, "SERP 경쟁 요약 실행 중");
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
