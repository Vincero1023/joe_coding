const STAGES = [
    {
        key: "collected",
        label: "1단계 수집",
        description: "카테고리 또는 시드 기준으로 원본 키워드를 수집합니다.",
        resultKey: "collected_keywords",
    },
    {
        key: "expanded",
        label: "2단계 확장",
        description: "자동완성, 연관어, 조합 확장으로 후보군을 늘립니다.",
        resultKey: "expanded_keywords",
    },
    {
        key: "analyzed",
        label: "3단계 분석",
        description: "CPC, bid, competition, volume 기준으로 수익성을 계산합니다.",
        resultKey: "analyzed_keywords",
    },
    {
        key: "selected",
        label: "4단계 선별",
        description: "골든 키워드 조건으로 최종 후보를 걸러냅니다.",
        resultKey: "selected_keywords",
    },
    {
        key: "titled",
        label: "5단계 제목 생성",
        description: "네이버 홈형과 블로그형 제목을 각각 생성합니다.",
        resultKey: "generated_titles",
    },
];

const DOWNSTREAM_STAGE_KEYS = {
    collected: ["expanded", "analyzed", "selected", "titled"],
    expanded: ["analyzed", "selected", "titled"],
    analyzed: ["selected", "titled"],
    selected: ["titled"],
    titled: [],
};

const TREND_SETTINGS_STORAGE_KEY = "keyword_forge_trend_settings";
const TREND_SETTINGS_VERSION = 3;
const TITLE_SETTINGS_STORAGE_KEY = "keyword_forge_title_settings";
const DASHBOARD_SESSION_STORAGE_KEY = "keyword_forge_dashboard_session_v1";
const TITLE_PROMPT_PREVIEW_LIMIT = 160;
const TITLE_PROVIDER_DEFAULT_MODELS = {
    openai: "gpt-4o-mini",
    gemini: "gemini-2.5-flash-lite",
    anthropic: "claude-haiku-4-5",
};
const TITLE_PROVIDER_MODEL_OPTIONS = {
    openai: [
        { value: "gpt-4o-mini", label: "(추천) GPT-4o mini" },
        { value: "gpt-4o", label: "GPT-4o" },
        { value: "gpt-4.1-mini", label: "GPT-4.1 mini" },
        { value: "gpt-4.1", label: "GPT-4.1" },
    ],
    gemini: [
        { value: "gemini-2.5-flash-lite", label: "(추천) Gemini 2.5 Flash-Lite" },
        { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
        { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
    ],
    anthropic: [
        { value: "claude-haiku-4-5", label: "(추천) Claude Haiku 4.5" },
        { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
        { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
    ],
};
const TITLE_TEMPERATURE_PRESETS = [
    {
        value: "0.2",
        label: "안정형",
        description: "가장 보수적으로 생성합니다. 규칙 준수와 톤 일관성을 우선합니다.",
    },
    {
        value: "0.5",
        label: "절충형",
        description: "안정성을 유지하면서 표현 변주를 조금 넓힙니다.",
    },
    {
        value: "0.7",
        label: "(추천) 균형형",
        description: "제목 다양성과 품질 안정성의 균형이 가장 무난한 기본값입니다.",
    },
    {
        value: "1.0",
        label: "확장형",
        description: "표현 폭을 더 넓게 씁니다. 더 다양하지만 품질 편차도 커질 수 있습니다.",
    },
];
const TITLE_TEMPERATURE_DEFAULT = "0.7";
const TITLE_PRESET_LIBRARY = Array.isArray(window.KEYWORD_FORGE_TITLE_PRESETS)
    ? window.KEYWORD_FORGE_TITLE_PRESETS
    : [];
const MANUAL_TITLE_PRESET_KEY = "manual";
const DEFAULT_TITLE_PRESET_KEY = TITLE_PRESET_LIBRARY.find((preset) => preset?.is_default)?.key || "openai_balanced";
const TITLE_PRESET_MAP = TITLE_PRESET_LIBRARY.reduce((map, preset) => {
    const key = String(preset?.key || "").trim();
    if (key) {
        map[key] = preset;
    }
    return map;
}, {});
const GRADE_ORDER = ["S", "A", "B", "C", "D", "F"];
const PROFITABILITY_ORDER = ["A", "B", "C", "D"];
const ATTACKABILITY_ORDER = ["1", "2", "3", "4"];
const GRADE_PRESET_MAP = {
    all: {
        profitability: [...PROFITABILITY_ORDER],
        attackability: [...ATTACKABILITY_ORDER],
    },
    golden_candidate: {
        profitability: ["A", "B", "C"],
        attackability: ["1", "2", "3"],
    },
    profit_focus: {
        profitability: ["A", "B"],
        attackability: [...ATTACKABILITY_ORDER],
    },
    easy_exposure: {
        profitability: [...PROFITABILITY_ORDER],
        attackability: ["1", "2"],
    },
};
const TITLE_RESULT_MODE_FILTER_OPTIONS = [
    { value: "all", label: "전체" },
    { value: "single", label: "핵심키워드" },
    { value: "longtail_selected", label: "롱테일 V1" },
    { value: "longtail_exploratory", label: "롱테일 V2" },
    { value: "longtail_experimental", label: "롱테일 V3" },
];
const TITLE_RESULT_SORT_OPTIONS = [
    { value: "mode_quality_desc", label: "버전순 + 품질" },
    { value: "quality_desc", label: "품질 높은순" },
    { value: "quality_asc", label: "품질 낮은순" },
    { value: "keyword_asc", label: "키워드순" },
];
const RESULT_VIEW_ORDER = STAGES.map((stage) => stage.key);

const state = {
    results: createEmptyResults(),
    stageStatus: createInitialStageStatus(),
    diagnostics: createEmptyDiagnostics(),
    selectedCollectedKeys: [],
    selectGradeFilters: [...PROFITABILITY_ORDER],
    selectAttackabilityFilters: [...ATTACKABILITY_ORDER],
    gradeSelectionTouched: false,
    activeResultView: "",
    lastError: null,
    isBusy: false,
    tickerId: null,
    titleModeFilter: "all",
    titleSort: "mode_quality_desc",
};

const elements = {};
let dashboardSessionSaveTimer = null;

document.addEventListener("DOMContentLoaded", () => {
    bindElements();
    loadTrendSettings();
    loadTitleSettings();
    const restoredDashboard = restoreDashboardSession();
    bindEvents();
    window.addEventListener("pagehide", persistDashboardSessionNow);
    window.addEventListener("storage", handleTitleSettingsStorageSync);
    document.addEventListener("visibilitychange", handleTitleSettingsVisibilitySync);
    startTicker();
    addLog("대시보드가 준비되었습니다. 단계별 실행과 디버그 정보를 바로 확인할 수 있습니다.", "success");
    if (restoredDashboard && elements.activityLog?.firstElementChild) {
        elements.activityLog.removeChild(elements.activityLog.firstElementChild);
    }
    renderAll();
});

function bindElements() {
    elements.layoutGrid = document.querySelector(".layout-grid");
    elements.categoryInput = document.getElementById("categoryInput");
    elements.categorySourceInput = document.getElementById("categorySourceInput");
    elements.seedInput = document.getElementById("seedInput");
    elements.trendServiceInput = document.getElementById("trendServiceInput");
    elements.trendDateInput = document.getElementById("trendDateInput");
    elements.trendBrowserInput = document.getElementById("trendBrowserInput");
    elements.trendCookieInput = document.getElementById("trendCookieInput");
    elements.trendFallbackInput = document.getElementById("trendFallbackInput");
    elements.trendSourceHelp = document.getElementById("trendSourceHelp");
    elements.launchLoginBrowserButton = document.getElementById("launchLoginBrowserButton");
    elements.loadLocalCookieButton = document.getElementById("loadLocalCookieButton");
    elements.localCookieStatus = document.getElementById("localCookieStatus");
    elements.expanderAnalysisPath = document.getElementById("expanderAnalysisPath");
    elements.optionRelated = document.getElementById("optionRelated");
    elements.optionAutocomplete = document.getElementById("optionAutocomplete");
    elements.optionBulk = document.getElementById("optionBulk");
    elements.optionDebug = document.getElementById("optionDebug");
    elements.expandInputSource = document.getElementById("expandInputSource");
    elements.expandManualInput = document.getElementById("expandManualInput");
    elements.analyzeInputSource = document.getElementById("analyzeInputSource");
    elements.analyzeManualInput = document.getElementById("analyzeManualInput");
    elements.selectedCollectedCount = document.getElementById("selectedCollectedCount");
    elements.manualAnalyzeCount = document.getElementById("manualAnalyzeCount");
    elements.titleMode = document.getElementById("titleMode");
    elements.titleProvider = document.getElementById("titleProvider");
    elements.titleModel = document.getElementById("titleModel");
    elements.titleApiKey = document.getElementById("titleApiKey");
    elements.titleTemperature = document.getElementById("titleTemperature");
    elements.titleFallback = document.getElementById("titleFallback");
    elements.titleSystemPrompt = document.getElementById("titleSystemPrompt");
    elements.titlePromptSummary = document.getElementById("titlePromptSummary");
    elements.openTitlePromptEditorButton = document.getElementById("openTitlePromptEditorButton");
    elements.clearTitlePromptButton = document.getElementById("clearTitlePromptButton");
    elements.titleModeBadge = document.getElementById("titleModeBadge");
    elements.statusList = document.getElementById("statusList");
    elements.resultsRailPanel = document.getElementById("resultsRailPanel");
    elements.resultsRail = document.getElementById("resultsRail");
    elements.resultsGrid = document.getElementById("resultsGrid");
    elements.activityLog = document.getElementById("activityLog");
    elements.pipelineStatus = document.getElementById("pipelineStatus");
    elements.progressBar = document.getElementById("progressBar");
    elements.progressText = document.getElementById("progressText");
    elements.progressDetail = document.getElementById("progressDetail");
    elements.errorConsole = document.getElementById("errorConsole");
    elements.debugPanels = document.getElementById("debugPanels");
    elements.actionButtons = Array.from(document.querySelectorAll("button"));
}

function bindEvents() {
    document.querySelectorAll("input[name='collectorMode']").forEach((element) => {
        element.addEventListener("change", renderInputState);
    });
    document.getElementById("runCollectButton").addEventListener("click", () => {
        runWithGuard(runCollectFromScratch, "수집 단계 실행 중");
    });
    document.getElementById("runExpandButton").addEventListener("click", () => {
        runWithGuard(runThroughExpand, "확장 단계 실행 중");
    });
    document.getElementById("runAnalyzeButton").addEventListener("click", () => {
        runWithGuard(runThroughAnalyze, "분석 단계 실행 중");
    });
    document.getElementById("runSelectButton").addEventListener("click", () => {
        runWithGuard(runThroughSelect, "선별 단계 실행 중");
    });
    elements.gradePresetButtons.forEach((button) => {
        button.addEventListener("click", () => {
            applyGradePreset(button.dataset.selectionPreset || "");
        });
    });
    elements.gradeToggleButtons.forEach((button) => {
        button.addEventListener("click", () => {
            toggleGradeFilter(button.dataset.gradeToggle || "");
        });
    });
    elements.runGradeSelectButton?.addEventListener("click", () => {
        const grades = getSelectedGradeFilters();
        runWithGuard(
            () => runThroughGradeSelect(grades),
            grades.length ? `${buildGradeRunLabel(grades)} 선별 실행 중` : "등급별 선별 실행 중",
        );
    });
    document.getElementById("runTitleButton").addEventListener("click", () => {
        runWithGuard(runThroughTitle, "제목 생성 단계 실행 중");
    });
    document.getElementById("runFullButton").addEventListener("click", () => {
        runWithGuard(runFullFlow, "전체 파이프라인 실행 중");
    });
    document.getElementById("resetButton").addEventListener("click", resetAll);
    document.getElementById("clearDebugButton").addEventListener("click", clearDiagnostics);
    elements.resultsGrid.addEventListener("click", handleResultsGridClick);
    elements.resultsGrid.addEventListener("change", handleResultsGridChange);
    elements.expandManualInput.addEventListener("input", renderInputState);
    elements.analyzeManualInput.addEventListener("input", renderInputState);
    elements.expandInputSource.addEventListener("change", renderInputState);
    elements.analyzeInputSource.addEventListener("change", renderInputState);
    [
        elements.categorySourceInput,
        elements.trendServiceInput,
        elements.trendDateInput,
        elements.trendBrowserInput,
        elements.trendCookieInput,
        elements.trendFallbackInput,
    ].forEach((element) => {
        element.addEventListener("input", handleTrendSettingsChange);
        element.addEventListener("change", handleTrendSettingsChange);
    });
    elements.loadLocalCookieButton.addEventListener("click", () => {
        runWithGuard(importLocalNaverCookie, "로컬 네이버 세션을 읽는 중");
    });
    elements.launchLoginBrowserButton.addEventListener("click", () => {
        runWithGuard(openDedicatedLoginBrowser, "전용 로그인 브라우저를 여는 중");
    });
    [
        elements.titleMode,
        elements.titleProvider,
        elements.titleModel,
        elements.titleApiKey,
        elements.titleTemperature,
        elements.titleFallback,
    ].forEach((element) => {
        element.addEventListener("input", handleTitleSettingsChange);
        element.addEventListener("change", handleTitleSettingsChange);
    });

    document.querySelectorAll("[data-preset]").forEach((button) => {
        button.addEventListener("click", () => applyPreset(button.dataset.preset || "finance"));
    });
}

async function runWithGuard(task, runningMessage) {
    if (state.isBusy) {
        addLog("이미 다른 작업이 실행 중입니다. 현재 단계가 끝난 뒤 다시 시도해 주세요.", "error");
        return;
    }

    state.isBusy = true;
    state.lastError = null;
    setGlobalStatus(runningMessage, "running");
    syncBusyButtons();
    renderAll();

    try {
        await task();
        setGlobalStatus("실행 완료", "success");
    } catch (error) {
        const normalizedError = normalizeError(error);
        state.lastError = normalizedError;
        setGlobalStatus("오류 발생", "error");
        addLog(buildErrorHeadline(normalizedError), "error");
    } finally {
        state.isBusy = false;
        syncBusyButtons();
        renderAll();
    }
}

async function runFullFlow() {
    await runCollectStage();
    await runExpandStage();
    await runAnalyzeStage();
    await runSelectStage(getForwardSelectOptions());
    await runTitleStage();
    addLog("전체 파이프라인 실행이 완료되었습니다.", "success");
}

async function runCollectFromScratch() {
    resetAll();
    await runCollectStage();
}

async function runThroughExpand() {
    await runExpandStage();
}

async function runThroughAnalyze() {
    await runAnalyzeStage();
}

async function runThroughSelect() {
    await runSelectStage(getForwardSelectOptions());
}

async function runThroughTitle() {
    await runTitleStage();
}

async function runCollectStage() {
    const inputData = buildCollectInput();
    const targetLabel = inputData.mode === "category"
        ? `카테고리 ${inputData.category || "미입력"}`
        : `시드 ${inputData.seed_input || "미입력"}`;

    if (inputData.mode === "category" && inputData.category_source === "naver_trend") {
        const trendService = inputData.trend_options?.service || "naver_blog";
        const hasCookie = Boolean(inputData.trend_options?.auth_cookie);
        const usesFallback = Boolean(inputData.trend_options?.fallback_to_preset_search);

        if (!hasCookie && !usesFallback) {
            throw new Error(
                `Creator Advisor 쿠키가 없습니다. 실제 네이버 트렌드를 보려면 ${trendService} 쿠키를 입력하거나 fallback을 켜 주세요.`,
            );
        }

        if (!hasCookie && usesFallback) {
            addLog(
                `Creator Advisor 쿠키가 없어 ${trendService} 트렌드 대신 preset 검색 fallback으로 내려갑니다.`,
                "error",
            );
        } else {
            addLog(`Creator Advisor ${trendService} 트렌드로 수집을 시도합니다.`);
        }
    }

    addLog(`수집 시작: ${targetLabel}`);
    clearStageAndDownstream("collected");
    const result = await executeStage({
        stageKey: "collected",
        endpoint: "/collect",
        inputData,
    });

    state.results.collected = result;
    state.selectedCollectedKeys = (result.collected_keywords || []).map(createCollectedIdentity);
    addLog(`수집 완료: ${countItems(result.collected_keywords)}건`, "success");
    renderAll();
    return result;
}

async function runExpandStage() {
    const source = elements.expandInputSource.value;
    if (source !== "manual_text" && !state.results.collected) {
        await runCollectStage();
    }

    const inputData = buildExpandInput();
    addLog(`확장 시작: ${describeExpandSource(inputData)}`);
    clearStageAndDownstream("expanded");
    const result = await executeExpandStageStream(inputData);

    state.results.expanded = result;
    addLog(`확장 완료: ${countItems(result.expanded_keywords)}건`, "success");
    renderAll();
    return result;
}

async function runAnalyzeStage() {
    const source = elements.analyzeInputSource.value;
    if (source !== "manual_text" && !state.results.expanded) {
        await runExpandStage();
    }

    const inputData = buildAnalyzeInput();
    addLog(`분석 시작: ${describeAnalyzeSource(inputData)}`);
    clearStageAndDownstream("analyzed");
    const result = await executeStage({
        stageKey: "analyzed",
        endpoint: "/analyze",
        inputData,
    });

    state.results.analyzed = result;
    addLog(`분석 완료: ${countItems(result.analyzed_keywords)}건`, "success");
    renderAll();
    return result;
}

async function runSelectStage() {
    if (!state.results.analyzed) {
        await runAnalyzeStage();
    }

    addLog("선별 시작: 골든 키워드 기준을 적용합니다.");
    clearStageAndDownstream("selected");
    const result = await executeStage({
        stageKey: "selected",
        endpoint: "/select",
        inputData: {
            analyzed_keywords: state.results.analyzed?.analyzed_keywords || [],
        },
    });

    state.results.selected = result;
    addLog(`선별 완료: ${countItems(result.selected_keywords)}건`, "success");
    renderAll();
    return result;
}

async function runTitleStage() {
    if (!state.results.selected) {
        await runSelectStage();
    }

    const titleOptions = buildTitleOptions();
    addLog(
        titleOptions.mode === "ai"
            ? `제목 생성 시작: ${titleOptions.provider} / ${titleOptions.model} 모델을 사용합니다.`
            : "제목 생성 시작: template 규칙 기반 제목을 생성합니다.",
    );
    clearStageAndDownstream("titled");
    const result = await executeStage({
        stageKey: "titled",
        endpoint: "/generate-title",
        inputData: {
            selected_keywords: state.results.selected?.selected_keywords || [],
            title_options: titleOptions,
        },
    });

    state.results.titled = result;
    addLog(`제목 생성 완료: ${countItems(result.generated_titles)}세트`, "success");
    renderAll();
    return result;
}

async function executeStage({ stageKey, endpoint, inputData }) {
    const stage = getStage(stageKey);
    const startedAt = Date.now();
    const startedAtLabel = new Date(startedAt).toISOString();
    const requestController = beginAbortableRequest(stageKey, endpoint);

    setActiveResultView(stageKey);
    state.stageStatus[stageKey] = {
        state: "running",
        message: `${stage.label} 실행 중`,
        startedAt,
        finishedAt: null,
        durationMs: null,
    };
    renderAll();

    try {
        const response = await postModule(endpoint, inputData, { signal: requestController.signal });
        const result = response.result || {};
        const itemCount = countItems(result[stage.resultKey]);
        const durationMs = Date.now() - startedAt;

        state.stageStatus[stageKey] = {
            state: "success",
            message: `${itemCount}건 완료`,
            startedAt,
            finishedAt: Date.now(),
            durationMs,
        };
        state.diagnostics[stageKey] = {
            stageKey,
            stageLabel: stage.label,
            status: "success",
            endpoint,
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
                endpoint,
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
            endpoint,
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
            endpoint,
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
        completeAbortableRequest(requestController);
    }
}

async function executeExpandStageStream(inputData) {
    const stageKey = "expanded";
    const stage = getStage(stageKey);
    const startedAt = Date.now();
    const startedAtLabel = new Date(startedAt).toISOString();

    state.stageStatus[stageKey] = {
        state: "running",
        message: `${stage.label} ?ㅽ뻾 以?`,
        startedAt,
        finishedAt: null,
        durationMs: null,
    };
    state.results.expanded = {
        expanded_keywords: [],
        stream_meta: {
            phase: "starting",
            currentKeyword: "",
            depth: 0,
            totalResults: 0,
            queueSize: 0,
            totalOrigins: 0,
            maxDepth: 0,
        },
    };
    renderAll();

    try {
        const response = await postModuleStream("/expand/stream", inputData, (eventPayload) => {
            applyExpandStreamEvent(eventPayload, startedAt);
        });
        const result = response.result || {};
        result.expanded_keywords = mergeExpandedKeywords(
            state.results.expanded?.expanded_keywords || [],
            result.expanded_keywords || [],
        );

        const durationMs = Date.now() - startedAt;
        state.stageStatus[stageKey] = {
            state: "success",
            message: `${result.expanded_keywords.length}嫄??꾨즺`,
            startedAt,
            finishedAt: Date.now(),
            durationMs,
        };
        state.diagnostics[stageKey] = {
            stageKey,
            stageLabel: stage.label,
            status: "success",
            endpoint: "/expand/stream",
            requestId: response.requestId,
            startedAt: startedAtLabel,
            durationMs,
            request: sanitizeSensitiveData(inputData),
            responseSummary: buildResponseSummary(stageKey, result),
            backendDebug: result.debug || null,
        };

        return result;
    } catch (error) {
        const normalizedError = normalizeError(error, {
            stageKey,
            endpoint: "/expand/stream",
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
            endpoint: "/expand/stream",
            requestId: normalizedError.requestId,
            startedAt: startedAtLabel,
            durationMs: normalizedError.durationMs,
            request: sanitizeSensitiveData(inputData),
            error: normalizedError,
        };
        renderAll();
        throw normalizedError;
    }
}

async function postModule(endpoint, inputData, options = {}) {
    const startedAt = Date.now();
    const signal = options?.signal;
    let response;

    try {
        response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ input_data: inputData }),
        });
    } catch (error) {
        const networkError = new Error("서버 요청에 실패했습니다. 네트워크 또는 서버 상태를 확인해 주세요.");
        networkError.code = "network_error";
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

    return {
        requestId,
        result: payload?.result || {},
        durationMs: Date.now() - startedAt,
    };
}

async function postModuleStream(endpoint, inputData, onEvent) {
    const startedAt = Date.now();
    let response;

    try {
        response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ input_data: inputData }),
            signal,
        });
    } catch (error) {
        if (isAbortLikeError(error)) {
            throw createRequestAbortError(endpoint, startedAt);
        }
        const networkError = new Error("?쒕쾭 ?붿껌???ㅽ뙣?덉뒿?덈떎. ?ㅽ듃?뚰겕 ?먮뒗 ?쒕쾭 ?곹깭瑜??뺤씤??二쇱꽭??");
        networkError.code = "network_error";
        networkError.endpoint = endpoint;
        networkError.detail = error instanceof Error ? error.message : String(error);
        networkError.durationMs = Date.now() - startedAt;
        throw networkError;
    }

    const requestId = response.headers.get("X-Request-ID") || "";
    if (!response.ok) {
        const rawText = await response.text();
        const payload = tryParseJson(rawText);
        throw createApiError({
            endpoint,
            requestId,
            statusCode: response.status,
            payload,
            rawText,
            durationMs: Date.now() - startedAt,
        });
    }

    if (!response.body) {
        return {
            requestId,
            result: {},
            durationMs: Date.now() - startedAt,
        };
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = {};

    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

        let newlineIndex = buffer.indexOf("\n");
        while (newlineIndex !== -1) {
            const line = buffer.slice(0, newlineIndex).trim();
            buffer = buffer.slice(newlineIndex + 1);

            if (line) {
                const payload = tryParseJson(line);
                if (payload?.event === "error") {
                    throw createApiError({
                        endpoint,
                        requestId,
                        statusCode: 500,
                        payload: { error: payload.error || {} },
                        rawText: line,
                        durationMs: Date.now() - startedAt,
                    });
                }
                if (payload?.event === "completed") {
                    finalResult = payload.result || {};
                }
                if (payload && typeof onEvent === "function") {
                    onEvent(payload);
                }
            }

            newlineIndex = buffer.indexOf("\n");
        }

        if (done) {
            break;
        }
    }

    const trailingLine = buffer.trim();
    if (trailingLine) {
        const payload = tryParseJson(trailingLine);
        if (payload?.event === "error") {
            throw createApiError({
                endpoint,
                requestId,
                statusCode: 500,
                payload: { error: payload.error || {} },
                rawText: trailingLine,
                durationMs: Date.now() - startedAt,
            });
        }
        if (payload?.event === "completed") {
            finalResult = payload.result || {};
        }
        if (payload && typeof onEvent === "function") {
            onEvent(payload);
        }
    }

    return {
        requestId,
        result: finalResult,
        durationMs: Date.now() - startedAt,
    };
}

function applyExpandStreamEvent(eventPayload, startedAt) {
    if (!eventPayload || eventPayload.event !== "progress") {
        return;
    }

    const progress = eventPayload.data || {};
    const currentResult = state.results.expanded || { expanded_keywords: [] };
    const currentItems = Array.isArray(currentResult.expanded_keywords) ? currentResult.expanded_keywords : [];
    const currentMeta = currentResult.stream_meta || {};

    if (progress.type === "keyword_results" || progress.type === "depth_completed") {
        currentResult.expanded_keywords = mergeExpandedKeywords(currentItems, progress.items || []);
    }

    currentResult.stream_meta = {
        ...currentMeta,
        phase: progress.type || currentMeta.phase || "running",
        currentKeyword: progress.keyword || currentMeta.currentKeyword || "",
        depth: progress.depth || currentMeta.depth || 0,
        totalResults: progress.total_results ?? currentResult.expanded_keywords.length,
        queueSize: progress.queue_size ?? progress.next_queue_size ?? currentMeta.queueSize ?? 0,
        totalOrigins: progress.total_origins ?? currentMeta.totalOrigins ?? 0,
        maxDepth: progress.max_depth ?? currentMeta.maxDepth ?? 0,
        keywordIndex: progress.index ?? currentMeta.keywordIndex ?? 0,
        keywordTotal: progress.total ?? currentMeta.keywordTotal ?? 0,
    };
    state.results.expanded = currentResult;

    if (progress.type === "depth_completed") {
        addLog(`?뺤옣 ${progress.depth}??④퀎 ?꾨즺: ?꾩쟻 ${currentResult.expanded_keywords.length}嫄?`, "success");
    }

    state.stageStatus.expanded = {
        state: "running",
        message: buildExpandStreamStatusMessage(currentResult.stream_meta),
        startedAt,
        finishedAt: null,
        durationMs: Date.now() - startedAt,
    };
    renderAll();
}

function buildExpandStreamStatusMessage(streamMeta) {
    if (!streamMeta) {
        return "2?④퀎 ?뺤옣 ?ㅽ뻾 以?";
    }
    if (streamMeta.currentKeyword) {
        return `${streamMeta.depth || "?"}??④퀎 쨌 ${streamMeta.currentKeyword} ?뺤옣 以?`;
    }
    if (streamMeta.depth) {
        return `${streamMeta.depth}??④퀎 ?뺤옣 以?`;
    }
    return "2?④퀎 ?뺤옣 ?ㅽ뻾 以?";
}

function createApiError({ endpoint, requestId, statusCode, payload, rawText, durationMs }) {
    const apiError = payload?.error || {};
    const error = new Error(apiError.message || `요청이 실패했습니다. (${statusCode})`);
    error.code = apiError.code || "http_error";
    error.endpoint = endpoint;
    error.statusCode = statusCode;
    error.requestId = apiError.request_id || requestId;
    error.detail = apiError.detail || rawText;
    error.durationMs = durationMs;
    error.path = apiError.path || endpoint;
    return error;
}

function normalizeError(error, extra = {}) {
    if (error && error.normalized) {
        return error;
    }

    return {
        normalized: true,
        message: error?.message || "알 수 없는 오류가 발생했습니다.",
        code: error?.code || "unknown_error",
        endpoint: error?.endpoint || extra.endpoint || "",
        path: error?.path || extra.endpoint || "",
        statusCode: error?.statusCode || 0,
        requestId: error?.requestId || "",
        detail: error?.detail || "",
        durationMs: error?.durationMs || extra.durationMs || 0,
        stageKey: error?.stageKey || extra.stageKey || "",
        request: extra.request || error?.request || null,
        startedAt: extra.startedAt || null,
    };
}

function buildResponseSummary(stageKey, result) {
    const stage = getStage(stageKey);
    const items = Array.isArray(result?.[stage.resultKey]) ? result[stage.resultKey] : [];
    const summary = {
        result_keys: Object.keys(result || {}),
        item_count: items.length,
        sample_items: items.slice(0, 3),
    };

    if (result?.debug) {
        summary.backend_debug = result.debug;
    }

    return summary;
}

function buildCollectInput() {
    const trendSettings = getTrendSettingsFormState();
    const mode = getCollectorMode();

    return {
        mode,
        category: mode === "category" ? elements.categoryInput.value.trim() : "",
        category_source: elements.categorySourceInput.value.trim() || "naver_trend",
        seed_input: elements.seedInput.value.trim(),
        options: {
            collect_related: elements.optionRelated.checked,
            collect_autocomplete: elements.optionAutocomplete.checked,
            collect_bulk: elements.optionBulk.checked,
        },
        trend_options: {
            service: trendSettings.service,
            content_type: "text",
            date: trendSettings.date,
            auth_cookie: trendSettings.auth_cookie,
            fallback_to_preset_search: trendSettings.fallback_to_preset_search,
        },
        debug: elements.optionDebug.checked,
    };
}

function buildExpandInput() {
    const source = elements.expandInputSource.value;
    const analysisPath = elements.expanderAnalysisPath.value.trim();
    const category = elements.categoryInput.value.trim();

    if (source === "manual_text") {
        const keywordsText = elements.expandManualInput.value.trim();
        const keywords = parseKeywordText(keywordsText);
        if (keywords.length === 0) {
            throw new Error("확장할 키워드를 직접 입력해 주세요.");
        }

        return {
            keywords_text: keywordsText,
            category,
            source: "manual_input",
            analysis_json_path: analysisPath,
        };
    }

    const collectedKeywords = source === "collector_selected"
        ? getSelectedCollectedItems()
        : state.results.collected?.collected_keywords || [];

    if (collectedKeywords.length === 0) {
        throw new Error(
            source === "collector_selected"
                ? "확장할 수집 키워드를 최소 1개 선택해 주세요."
                : "수집 결과가 없습니다. 먼저 수집을 실행해 주세요.",
        );
    }

    return {
        collected_keywords: collectedKeywords,
        analysis_json_path: analysisPath,
    };
}

function buildAnalyzeInput() {
    const source = elements.analyzeInputSource.value;

    if (source === "manual_text") {
        const keywordsText = elements.analyzeManualInput.value.trim();
        const keywords = parseKeywordText(keywordsText);
        if (keywords.length === 0) {
            throw new Error("분석할 키워드를 직접 입력해 주세요.");
        }

        return withAnalyzeKeywordStats({
            keywords_text: keywordsText,
        });
    }

    const expandedKeywords = state.results.expanded?.expanded_keywords || [];
    if (expandedKeywords.length === 0) {
        throw new Error("확장 결과가 없습니다. 먼저 확장을 실행하거나 직접 입력으로 전환해 주세요.");
    }

    return withAnalyzeKeywordStats({
        expanded_keywords: expandedKeywords,
    });
}

function withAnalyzeKeywordStats(inputData) {
    const keywordStatsText = elements.analyzeKeywordStatsInput?.value.trim();
    const benchmarkSettings = {
        enabled: true,
        max_workers: 6,
        max_keywords: 60,
    };
    if (!keywordStatsText) {
        return {
            ...inputData,
            keywordmaster_benchmark: benchmarkSettings,
        };
    }

    return {
        ...inputData,
        keyword_stats_text: keywordStatsText,
        keywordmaster_benchmark: benchmarkSettings,
    };
}

function buildTitleOptions() {
    const formState = getTitleSettingsFormState();
    const mode = formState.mode;
    const provider = formState.provider;
    const model = formState.model;
    const apiKey = mode === "ai" ? formState.api_key : "";

    return {
        mode,
        keyword_modes: formState.keyword_modes,
        preset_key: formState.preset_key,
        provider,
        model,
        api_key: apiKey,
        temperature: formState.temperature,
        fallback_to_template: formState.fallback_to_template,
        system_prompt: formState.system_prompt,
    };
}

function formatTitleKeywordModeSummary(rawModes) {
    const modeLabelMap = {
        single: "단일",
        longtail_selected: "V1",
        longtail_exploratory: "V2",
        longtail_experimental: "V3",
    };
    const normalizedModes = typeof normalizeTitleKeywordModes === "function"
        ? normalizeTitleKeywordModes(rawModes)
        : [];
    const labels = normalizedModes
        .map((mode) => modeLabelMap[mode] || "")
        .filter(Boolean);
    return labels.length ? `키워드 모드 ${labels.join(" + ")}` : "키워드 모드 단일";
}

function buildTitleRunSummary(titleOptions) {
    const modeSummary = formatTitleKeywordModeSummary(titleOptions.keyword_modes);
    if (titleOptions.mode !== "ai") {
        return `template 규칙 기반 / ${modeSummary}`;
    }
    if (titleOptions.mode !== "ai") {
        return "template 규칙 기반 제목을 생성합니다.";
    }
    const preset = getTitlePresetConfig(titleOptions.preset_key);
    const parts = [
        preset?.label || "",
        formatTitleProviderLabel(titleOptions.provider),
        titleOptions.model,
    ].filter(Boolean);
    return `${parts.join(" / ")} / ${modeSummary}`;
    return `${parts.join(" / ")} 모델을 사용합니다.`;
}

function loadTrendSettings() {
    const defaults = {
        version: TREND_SETTINGS_VERSION,
        category_source: "naver_trend",
        service: "naver_blog",
        date: getDefaultTrendDate(),
        browser: "auto",
        auth_cookie: "",
        fallback_to_preset_search: false,
    };

    const storedSettings = readLocalStorageJson(TREND_SETTINGS_STORAGE_KEY);
    const settings = storedSettings?.version === TREND_SETTINGS_VERSION
        ? { ...defaults, ...(storedSettings || {}) }
        : {
            ...defaults,
            date: storedSettings?.date || defaults.date,
            auth_cookie: storedSettings?.auth_cookie || "",
        };

    elements.categorySourceInput.value = settings.category_source;
    elements.trendServiceInput.value = settings.service;
    elements.trendDateInput.value = settings.date;
    elements.trendBrowserInput.value = settings.browser;
    elements.trendCookieInput.value = settings.auth_cookie;
    elements.trendFallbackInput.checked = Boolean(settings.fallback_to_preset_search);

    renderTrendSettingsState();
}

function handleTrendSettingsChange() {
    if (elements.localCookieStatus && document.activeElement !== elements.loadLocalCookieButton) {
        delete elements.localCookieStatus.dataset.locked;
    }
    persistTrendSettings();
    renderTrendSettingsState();
    renderInputState();
}

function persistTrendSettings() {
    try {
        window.localStorage.setItem(
            TREND_SETTINGS_STORAGE_KEY,
            JSON.stringify(getTrendSettingsFormState()),
        );
    } catch (error) {
        addLog("브라우저 저장소에 네이버 트렌드 설정을 저장하지 못했습니다.", "error");
    }
}

function renderTrendSettingsState() {
    const categoryMode = getCollectorMode() === "category";
    const usesTrendSource = categoryMode && elements.categorySourceInput.value === "naver_trend";

    elements.trendServiceInput.disabled = !usesTrendSource;
    elements.trendDateInput.disabled = !usesTrendSource;
    elements.trendBrowserInput.disabled = !usesTrendSource;
    elements.trendCookieInput.disabled = !usesTrendSource;
    elements.trendFallbackInput.disabled = !categoryMode;
    elements.launchLoginBrowserButton.disabled = !usesTrendSource;
    elements.loadLocalCookieButton.disabled = !usesTrendSource;

    if (elements.trendSourceHelp) {
        if (usesTrendSource) {
            const hasCookie = Boolean(elements.trendCookieInput.value.trim());
            const service = elements.trendServiceInput.value || "naver_blog";
            const browser = elements.trendBrowserInput.value || "auto";
            const fallbackLabel = elements.trendFallbackInput.checked ? "켜짐" : "꺼짐";
            elements.trendSourceHelp.textContent = hasCookie
                ? `현재 Creator Advisor ${service} 트렌드를 직접 조회합니다. /naver_blog/... 페이지를 기준으로 볼 때는 service를 naver_blog로 맞춰야 하며, 로컬 브라우저는 ${browser}, fallback은 ${fallbackLabel} 상태입니다.`
                : `현재 Creator Advisor ${service} 쿠키가 비어 있습니다. 권장은 아래 '전용 로그인 브라우저 열기'로 앱 전용 세션을 만든 뒤 쓰는 방식이며, fallback이 꺼져 있으면 트렌드 수집은 멈춥니다.`;
        } else {
            elements.trendSourceHelp.textContent = "seed 모드이거나 preset_search를 고른 경우에는 기존 공개 검색 수집 경로를 사용합니다.";
        }
    }

    if (elements.localCookieStatus && !elements.localCookieStatus.dataset.locked) {
        elements.localCookieStatus.textContent = elements.trendCookieInput.value.trim()
            ? "브라우저에서 불러오거나 직접 붙여넣은 로컬 세션이 준비되어 있습니다."
            : "아직 불러온 로컬 세션이 없습니다.";
    }
}

function getTrendSettingsFormState() {
    return {
        version: TREND_SETTINGS_VERSION,
        category_source: elements.categorySourceInput.value,
        service: elements.trendServiceInput.value || "naver_blog",
        date: elements.trendDateInput.value || getDefaultTrendDate(),
        browser: elements.trendBrowserInput.value || "auto",
        auth_cookie: elements.trendCookieInput.value.trim(),
        fallback_to_preset_search: elements.trendFallbackInput.checked,
    };
}

async function importLocalNaverCookie() {
    const browser = elements.trendBrowserInput.value || "auto";
    try {
        const response = await postModule("/local/naver-session", {
            browser,
        });
        const result = response.result || {};
        const cookieHeader = String(result.cookie_header || "").trim();

        if (!cookieHeader) {
            throw new Error("로컬 브라우저에서 네이버 쿠키를 찾지 못했습니다.");
        }

        elements.trendCookieInput.value = cookieHeader;
        if (elements.localCookieStatus) {
            elements.localCookieStatus.dataset.locked = "true";
            elements.localCookieStatus.textContent = `${result.browser || browser} 브라우저에서 쿠키 ${result.cookie_count || 0}개를 불러왔습니다.`;
        }
        persistTrendSettings();
        renderTrendSettingsState();
        addLog(`${result.browser || browser} 브라우저에서 Creator Advisor 쿠키를 불러왔습니다.`, "success");
    } catch (error) {
        const normalized = normalizeError(error, {
            endpoint: "/local/naver-session",
            request: { browser },
        });
        const attempts = Array.isArray(normalized.detail?.attempts)
            ? normalized.detail.attempts
            : [];
        const hint = normalized.detail?.hint || "";
        if (elements.localCookieStatus) {
            elements.localCookieStatus.dataset.locked = "true";
            elements.localCookieStatus.textContent = buildLocalCookieFailureMessage(browser, attempts, hint, normalized.message);
        }
        throw normalized;
    }
}

function buildLocalCookieFailureMessage(browser, attempts, hint, fallbackMessage) {
    if (attempts.length > 0) {
        const first = attempts[0];
        const base = `${first.browser || browser} 브라우저 쿠키를 읽지 못했습니다: ${first.detail || fallbackMessage}`;
        return first.hint ? `${base} / ${first.hint}` : base;
    }

    return hint ? `${fallbackMessage} / ${hint}` : fallbackMessage;
}

async function openDedicatedLoginBrowser() {
    const browser = elements.trendBrowserInput.value === "chrome" ? "chrome" : "edge";

    if (elements.localCookieStatus) {
        elements.localCookieStatus.dataset.locked = "true";
        elements.localCookieStatus.textContent = `${browser} 전용 로그인 브라우저를 열었습니다. 로그인 후 창이 자동으로 닫힐 때까지 기다려 주세요.`;
    }
    addLog(`${browser} 전용 로그인 브라우저를 엽니다. 열린 창에서 네이버 로그인과 Creator Advisor 접속을 완료해 주세요.`);

    try {
        const response = await postModule("/local/naver-login-browser", {
            browser,
            timeout_seconds: 300,
        });
        const result = response.result || {};
        const cookieHeader = String(result.cookie_header || "").trim();

        if (!cookieHeader) {
            throw new Error("전용 로그인 브라우저에서 네이버 세션을 가져오지 못했습니다.");
        }

        elements.trendCookieInput.value = cookieHeader;
        if (elements.localCookieStatus) {
            elements.localCookieStatus.dataset.locked = "true";
            elements.localCookieStatus.textContent = `${result.browser || browser} 전용 프로필에서 쿠키 ${result.cookie_count || 0}개를 저장했습니다.`;
        }
        persistTrendSettings();
        renderTrendSettingsState();
        addLog(`${result.browser || browser} 전용 로그인 브라우저에서 Creator Advisor 쿠키를 저장했습니다.`, "success");
    } catch (error) {
        const normalized = normalizeError(error, {
            endpoint: "/local/naver-login-browser",
            request: { browser },
        });
        const hint = normalized.detail?.hint || "";
        if (elements.localCookieStatus) {
            elements.localCookieStatus.dataset.locked = "true";
            elements.localCookieStatus.textContent = hint
                ? `${normalized.message} / ${hint}`
                : normalized.message;
        }
        throw normalized;
    }
}

function loadTitleSettings() {
    const defaults = {
        mode: "template",
        provider: "openai",
        model: TITLE_PROVIDER_DEFAULT_MODELS.openai,
        api_key: "",
        temperature: "0.7",
        fallback_to_template: true,
    };

    const storedSettings = readLocalStorageJson(TITLE_SETTINGS_STORAGE_KEY);
    const settings = { ...defaults, ...(storedSettings || {}) };

    elements.titleMode.value = settings.mode;
    elements.titleProvider.value = settings.provider;
    elements.titleModel.value = settings.model;
    elements.titleApiKey.value = settings.api_key;
    elements.titleTemperature.value = String(settings.temperature || "0.7");
    elements.titleFallback.checked = Boolean(settings.fallback_to_template);

    renderTitleSettingsState();
}

function handleTitleSettingsChange(event) {
    if (event?.target === elements.titleProvider && !elements.titleModel.value.trim()) {
        elements.titleModel.value = TITLE_PROVIDER_DEFAULT_MODELS[elements.titleProvider.value] || "gpt-4o-mini";
    }

    if (event?.target === elements.titleProvider) {
        const providerModel = TITLE_PROVIDER_DEFAULT_MODELS[elements.titleProvider.value] || "gpt-4o-mini";
        const currentModel = elements.titleModel.value.trim();
        const knownModels = Object.values(TITLE_PROVIDER_DEFAULT_MODELS);
        if (!currentModel || knownModels.includes(currentModel)) {
            elements.titleModel.value = providerModel;
        }
    }

    persistTitleSettings();
    renderTitleSettingsState();
}

function persistTitleSettings() {
    try {
        window.localStorage.setItem(
            TITLE_SETTINGS_STORAGE_KEY,
            JSON.stringify(getTitleSettingsFormState()),
        );
    } catch (error) {
        addLog("브라우저 저장소에 제목 생성 설정을 저장하지 못했습니다.", "error");
    }
}

function renderTitleSettingsState() {
    const isAiMode = elements.titleMode.value === "ai";

    elements.titleProvider.disabled = !isAiMode;
    elements.titleModel.disabled = !isAiMode;
    elements.titleApiKey.disabled = !isAiMode;
    elements.titleTemperature.disabled = !isAiMode;
    elements.titleFallback.disabled = !isAiMode;
    elements.titleModeBadge.textContent = isAiMode ? `ai:${elements.titleProvider.value}` : "template";
}

function getTitleSettingsFormState() {
    const provider = elements.titleProvider.value;
    return {
        mode: elements.titleMode.value,
        provider,
        model: elements.titleModel.value.trim() || TITLE_PROVIDER_DEFAULT_MODELS[provider] || "gpt-4o-mini",
        api_key: elements.titleApiKey.value.trim(),
        temperature: elements.titleTemperature.value.trim() || "0.7",
        fallback_to_template: elements.titleFallback.checked,
    };
}

function getDefaultTrendDate() {
    const current = new Date();
    current.setDate(current.getDate() - 2);
    return current.toISOString().slice(0, 10);
}

function describeExpandSource(inputData) {
    if (inputData.keywords_text) {
        return `직접 입력 ${parseKeywordText(inputData.keywords_text).length}건 기준으로 후보군을 확장합니다.`;
    }
    return `수집 키워드 ${countItems(inputData.collected_keywords)}건을 기준으로 후보군을 확장합니다.`;
}

function describeAnalyzeSource(inputData) {
    if (inputData.keywords_text) {
        return `직접 입력 ${parseKeywordText(inputData.keywords_text).length}건 기준으로 수익성을 계산합니다.`;
    }
    return `확장 결과 ${countItems(inputData.expanded_keywords)}건 기준으로 수익성을 계산합니다.`;
}

function getCollectorMode() {
    const selected = document.querySelector("input[name='collectorMode']:checked");
    return selected ? selected.value : "category";
}

function applyPreset(kind) {
    const presets = {
        finance: { mode: "category", category: "비즈니스경제", seed: "보험" },
        travel: { mode: "category", category: "국내여행", seed: "제주 여행" },
        food: { mode: "category", category: "맛집", seed: "성심당" },
    };

    const preset = presets[kind] || presets.finance;
    const selector = `input[name="collectorMode"][value="${preset.mode}"]`;
    const radio = document.querySelector(selector);
    if (radio) {
        radio.checked = true;
    }

    elements.categoryInput.value = preset.category;
    elements.categorySourceInput.value = "naver_trend";
    elements.seedInput.value = preset.seed;
    persistTrendSettings();
    renderTrendSettingsState();

    document.querySelectorAll("[data-preset]").forEach((button) => {
        button.classList.toggle("active", button.dataset.preset === kind);
    });

    addLog(`${formatPresetName(kind)} 예시를 입력값에 반영했습니다.`, "success");
}

function formatPresetName(kind) {
    if (kind === "travel") return "여행";
    if (kind === "food") return "맛집";
    return "금융";
}

function clearPipelineResults(options = {}) {
    const {
        preserveGlobalStatus = false,
        preserveSelectionFilters = false,
        announce = true,
        message = "결과와 디버그 정보를 초기화했습니다.",
    } = options;

    state.results = createEmptyResults();
    state.stageStatus = createInitialStageStatus();
    state.diagnostics = createEmptyDiagnostics();
    state.selectedCollectedKeys = [];
    if (!preserveSelectionFilters) {
        state.selectGradeFilters = [...PROFITABILITY_ORDER];
        state.selectAttackabilityFilters = [...ATTACKABILITY_ORDER];
        state.gradeSelectionTouched = false;
    }
    state.activeResultView = "";
    state.lastError = null;
    state.analyzedFilters = createDefaultAnalyzedFilters();
    state.streamAbortController = null;
    state.streamAbortEndpoint = "";
    state.streamAbortRequested = false;
    state.requestAbortController = null;
    state.requestAbortStageKey = "";
    state.requestAbortEndpoint = "";
    state.requestAbortRequested = false;
    if (!preserveGlobalStatus) {
        setGlobalStatus("대기 중", "idle");
    }
    renderAll();
    if (announce) {
        addLog(message);
    }
}

function resetAll() {
    clearPipelineResults({
        preserveGlobalStatus: false,
        preserveSelectionFilters: false,
        announce: true,
        message: "결과와 디버그 정보를 초기화했습니다.",
    });
    return;
    state.results = createEmptyResults();
    state.stageStatus = createInitialStageStatus();
    state.diagnostics = createEmptyDiagnostics();
    state.selectedCollectedKeys = [];
    state.selectGradeFilters = [...GRADE_ORDER];
    state.gradeSelectionTouched = false;
    state.lastError = null;
    setGlobalStatus("대기 중", "idle");
    renderAll();
    addLog("결과와 디버그 정보를 초기화했습니다.");
}

function clearDiagnostics() {
    state.diagnostics = createEmptyDiagnostics();
    state.lastError = null;
    renderDiagnostics();
    addLog("오류/디버그 패널을 초기화했습니다.");
}

function clearStageAndDownstream(stageKey) {
    state.results[stageKey] = null;
    state.stageStatus[stageKey] = createPendingStatus();
    state.diagnostics[stageKey] = null;

    if (stageKey === "collected") {
        state.selectedCollectedKeys = [];
    }

    if (stageKey === "collected" || stageKey === "expanded" || stageKey === "analyzed") {
        state.selectGradeFilters = [...GRADE_ORDER];
        state.gradeSelectionTouched = false;
        state.analyzedFilters = createDefaultAnalyzedFilters();
    }

    DOWNSTREAM_STAGE_KEYS[stageKey].forEach((nextStageKey) => {
        state.results[nextStageKey] = null;
        state.stageStatus[nextStageKey] = createPendingStatus();
        state.diagnostics[nextStageKey] = null;
    });
}

function createEmptyResults() {
    return {
        collected: null,
        expanded: null,
        analyzed: null,
        selected: null,
        titled: null,
    };
}

function createEmptyDiagnostics() {
    return {
        collected: null,
        expanded: null,
        analyzed: null,
        selected: null,
        titled: null,
    };
}

function createInitialStageStatus() {
    return Object.fromEntries(STAGES.map((stage) => [stage.key, createPendingStatus()]));
}

function createPendingStatus() {
    return {
        state: "pending",
        message: "대기 중",
        startedAt: null,
        finishedAt: null,
        durationMs: null,
    };
}

function getStage(stageKey) {
    return STAGES.find((stage) => stage.key === stageKey);
}

function normalizeResultViewKey(viewKey) {
    const safeViewKey = String(viewKey || "").trim();
    return RESULT_VIEW_ORDER.includes(safeViewKey) ? safeViewKey : "";
}

function setActiveResultView(viewKey) {
    const normalizedViewKey = normalizeResultViewKey(viewKey);
    if (!normalizedViewKey) {
        return;
    }
    state.activeResultView = normalizedViewKey;
}

function resolveActiveResultView(resultViews) {
    const availableViews = new Set((resultViews || []).map((view) => view.key));
    const activeView = normalizeResultViewKey(state.activeResultView);
    if (activeView && availableViews.has(activeView)) {
        return activeView;
    }

    const fallbackView = [...RESULT_VIEW_ORDER].reverse().find((viewKey) => availableViews.has(viewKey)) || "";
    state.activeResultView = fallbackView;
    return fallbackView;
}

function renderAll() {
    renderCounts();
    renderProgress();
    renderStageList();
    renderInputState();
    renderTrendSettingsState();
    renderTitleSettingsState();
    syncControlFocus();
    renderGuideTabs();
    renderResults();
    renderDiagnostics();
    scheduleDashboardSessionSave();
}

function beginFreshPipelineRun(stageLabel) {
    clearPipelineResults({
        preserveGlobalStatus: true,
        preserveSelectionFilters: true,
        announce: false,
    });
    addLog(`${stageLabel} 새 세션을 시작합니다. 현재 입력값으로 다시 실행합니다.`);
}

async function runFreshCollectFlow() {
    beginFreshPipelineRun("수집");
    await runCollectStage();
}

async function runFreshExpandFlow() {
    beginFreshPipelineRun("확장");
    await runExpandStage();
}

async function runFreshAnalyzeFlow() {
    beginFreshPipelineRun("분석");
    await runAnalyzeStage();
}

async function runFreshSelectFlow() {
    beginFreshPipelineRun("선별");
    await runSelectStage(getForwardSelectOptions());
}

async function runFreshTitleFlow() {
    beginFreshPipelineRun("제목 생성");
    await runTitleStage();
}

async function runFreshFullFlow() {
    beginFreshPipelineRun("전체 파이프라인");
    await runFullFlow();
}

function renderInputState() {
    const selectedCount = getSelectedCollectedItems().length;
    const expandCount = parseKeywordText(elements.expandManualInput?.value || "").length;
    const analyzeCount = parseKeywordText(elements.analyzeManualInput?.value || "").length;
    const expandUsesManual = elements.expandInputSource?.value === "manual_text";
    const analyzeUsesManual = elements.analyzeInputSource?.value === "manual_text";
    const categoryMode = getCollectorMode() === "category";
    const usesTrendSource = categoryMode && elements.categorySourceInput?.value === "naver_trend";

    if (elements.selectedCollectedCount) {
        elements.selectedCollectedCount.textContent = expandUsesManual
            ? `직접 입력 ${expandCount}건`
            : `선택 ${selectedCount}건`;
    }
    if (elements.manualAnalyzeCount) {
        elements.manualAnalyzeCount.textContent = `직접 입력 ${analyzeCount}건`;
    }
    if (elements.expandManualInput) {
        elements.expandManualInput.disabled = !expandUsesManual;
    }
    if (elements.analyzeManualInput) {
        elements.analyzeManualInput.disabled = !analyzeUsesManual;
    }
    if (elements.categoryInput) {
        elements.categoryInput.disabled = !categoryMode;
        elements.categoryInput.title = categoryMode ? "" : "seed 모드에서는 카테고리를 사용하지 않습니다.";
    }
    if (elements.categorySourceInput) {
        elements.categorySourceInput.disabled = !categoryMode;
    }
    if (elements.optionRelated) {
        elements.optionRelated.title = usesTrendSource ? "트렌드 실패 후 preset fallback에서만 적용됩니다." : "";
    }
    if (elements.optionAutocomplete) {
        elements.optionAutocomplete.title = usesTrendSource ? "트렌드 실패 후 preset fallback에서만 적용됩니다." : "";
    }
    if (elements.optionBulk) {
        elements.optionBulk.title = usesTrendSource ? "트렌드 실패 후 preset fallback에서만 적용됩니다." : "";
    }
    renderTrendSettingsState();
}

function renderCounts() {
    document.getElementById("countCollected").textContent = countItems(state.results.collected?.collected_keywords);
    document.getElementById("countExpanded").textContent = countItems(state.results.expanded?.expanded_keywords);
    document.getElementById("countAnalyzed").textContent = countItems(state.results.analyzed?.analyzed_keywords);
    document.getElementById("countSelected").textContent = countItems(state.results.selected?.selected_keywords);
    document.getElementById("countTitled").textContent = countItems(state.results.titled?.generated_titles);
}

function renderProgress() {
    const completedCount = STAGES.filter((stage) => state.stageStatus[stage.key].state === "success").length;
    const runningStage = STAGES.find((stage) => state.stageStatus[stage.key].state === "running");
    const progressUnits = completedCount + (runningStage ? 0.45 : 0);
    const progressPercent = Math.min(100, Math.round((progressUnits / STAGES.length) * 100));

    elements.progressBar.style.width = `${progressPercent}%`;
    elements.progressText.textContent = `${completedCount} / ${STAGES.length} 단계 완료`;
    elements.progressDetail.textContent = runningStage
        ? `${runningStage.label} 진행 중 · ${formatElapsed(state.stageStatus[runningStage.key])}`
        : completedCount === 0
            ? "아직 실행되지 않았습니다."
            : `${completedCount}개 단계가 완료되었습니다.`;
}

function renderStageList() {
    elements.statusList.innerHTML = STAGES.map((stage) => {
        const status = state.stageStatus[stage.key];
        const badgeLabel = formatStageBadge(status);
        const detailLabel = buildStageDetail(status);

        return `
            <div class="status-item ${status.state}">
                <div>
                    <strong>${escapeHtml(stage.label)}</strong>
                    <span>${escapeHtml(stage.description)}</span>
                    <small class="status-meta">${escapeHtml(detailLabel)}</small>
                </div>
                <div class="stage-chip ${status.state}">${escapeHtml(badgeLabel)}</div>
            </div>
        `;
    }).join("");
}

function renderResults() {
    const cards = [];

    if (state.results.collected?.collected_keywords) {
        cards.push(resultCard("수집 키워드", state.results.collected.collected_keywords, renderCollectedList));
    }
    if (state.results.expanded?.expanded_keywords) {
        cards.push(
            resultCard("확장 키워드", state.results.expanded.expanded_keywords, renderExpandedList, {
                limit: "all",
                subtitle: "기본 12건만 먼저 보여주고, 필요하면 전체를 펼쳐서 볼 수 있습니다.",
                className: "expanded-result-card",
            }),
        );
    }
    if (state.results.analyzed?.analyzed_keywords) {
        cards.push(resultCard("분석 결과", state.results.analyzed.analyzed_keywords, renderAnalyzedList));
    }
    if (state.results.selected?.selected_keywords) {
        cards.push(resultCard("골든 키워드", state.results.selected.selected_keywords, renderSelectedList));
    }
    if (state.results.titled?.generated_titles) {
        cards.push(resultCard("생성된 제목", state.results.titled.generated_titles, renderTitleList));
    }

    elements.resultsGrid.innerHTML = cards.length > 0
        ? cards.join("")
        : `
            <div class="placeholder">
                실행 버튼을 누르면 단계별 결과와 디버그 정보가 이 영역에 표시됩니다.<br />
                수집은 공개 소스 기반으로 동작하므로, collector 진단 로그에서 어떤 쿼리가 성공/실패했는지 같이 확인할 수 있습니다.
            </div>
        `;
}

function renderDiagnostics() {
    renderErrorConsole();
    renderDebugPanels();
}

function renderErrorConsole() {
    if (!state.lastError) {
        elements.errorConsole.className = "error-console empty";
        elements.errorConsole.textContent = "오류가 발생하지 않았습니다.";
        return;
    }

    const detailText = formatDebugValue(state.lastError.detail || "추가 상세 정보가 없습니다.");
    const requestIdLabel = state.lastError.requestId ? `request_id ${state.lastError.requestId}` : "request_id 없음";
    const statusLabel = state.lastError.statusCode ? `HTTP ${state.lastError.statusCode}` : state.lastError.code;

    elements.errorConsole.className = "error-console";
    elements.errorConsole.innerHTML = `
        <div class="error-console-head">
            <strong>${escapeHtml(buildErrorHeadline(state.lastError))}</strong>
            <span>${escapeHtml(requestIdLabel)}</span>
        </div>
        <div class="error-console-meta">
            <span class="stage-chip error">${escapeHtml(statusLabel)}</span>
            <span class="stage-chip pending">${escapeHtml(state.lastError.endpoint || state.lastError.path || "-")}</span>
            <span class="stage-chip pending">${escapeHtml(formatDuration(state.lastError.durationMs))}</span>
        </div>
        <pre>${escapeHtml(detailText)}</pre>
    `;
}

function renderDebugPanels() {
    const diagnostics = STAGES
        .map((stage) => state.diagnostics[stage.key])
        .filter(Boolean);

    if (diagnostics.length === 0) {
        elements.debugPanels.innerHTML = `
            <div class="debug-placeholder">
                각 단계가 실행되면 요청 요약, 응답 샘플, collector debug 로그가 여기에 표시됩니다.
            </div>
        `;
        return;
    }

    elements.debugPanels.innerHTML = diagnostics.map((diagnostic) => renderDiagnosticCard(diagnostic)).join("");
}

function renderDiagnosticCard(diagnostic) {
    const summary = diagnostic.responseSummary || diagnostic.error || {};
    const statusLabel = diagnostic.status === "success" ? "정상" : "오류";
    const requestIdLabel = diagnostic.requestId || "없음";
    const backendDebugSummary = diagnostic.backendDebug?.summary || null;
    const openByDefault = diagnostic.status === "error" || diagnostic.stageKey === "collected";

    return `
        <details class="debug-card" ${openByDefault ? "open" : ""}>
            <summary>
                <div>
                    <strong>${escapeHtml(diagnostic.stageLabel)}</strong>
                    <span>${escapeHtml(`${statusLabel} · ${formatDuration(diagnostic.durationMs)}`)}</span>
                </div>
                <span class="stage-chip ${diagnostic.status}">${escapeHtml(statusLabel)}</span>
            </summary>
            <div class="debug-card-body">
                <div class="debug-meta">
                    <span class="badge">request_id ${escapeHtml(requestIdLabel)}</span>
                    <span class="badge">${escapeHtml(diagnostic.endpoint || "-")}</span>
                    <span class="badge">${escapeHtml(diagnostic.startedAt || "-")}</span>
                    ${backendDebugSummary ? `<span class="badge">warning ${escapeHtml(String(backendDebugSummary.warning_count || 0))}</span>` : ""}
                </div>
                <div class="debug-columns">
                    <div class="debug-section">
                        <h4>요청</h4>
                        <pre>${escapeHtml(formatDebugValue(diagnostic.request))}</pre>
                    </div>
                    <div class="debug-section">
                        <h4>${diagnostic.status === "success" ? "응답 요약" : "오류 상세"}</h4>
                        <pre>${escapeHtml(formatDebugValue(summary))}</pre>
                    </div>
                </div>
                ${diagnostic.backendDebug ? `
                    <div class="debug-section debug-section-full">
                        <h4>Collector Debug</h4>
                        <pre>${escapeHtml(formatDebugValue(diagnostic.backendDebug))}</pre>
                    </div>
                ` : ""}
            </div>
        </details>
    `;
}

function resultCard(title, items, renderer) {
    return `
        <article class="result-card">
            <div class="result-head">
                <h3>${escapeHtml(title)}</h3>
                <span class="result-count">총 ${countItems(items)}건</span>
            </div>
            ${renderer(items.slice(0, 8))}
        </article>
    `;
}

function renderCollectedList(items) {
    return `<div class="keyword-list">${items.map((item) => `
        <div class="keyword-item">
            <div class="keyword-main">
                <strong>${escapeHtml(item.keyword || "-")}</strong>
                <span class="score-line">${escapeHtml(item.source || "출처 없음")}</span>
            </div>
            <div class="keyword-meta">
                <span class="badge">카테고리 ${escapeHtml(item.category || "미분류")}</span>
                <span class="badge">원문 ${escapeHtml(item.raw || "-")}</span>
            </div>
            <label class="keyword-select">
                <input
                    type="checkbox"
                    data-collected-key="${escapeHtml(createCollectedIdentity(item))}"
                    ${state.selectedCollectedKeys.includes(createCollectedIdentity(item)) ? "checked" : ""}
                />
                <span>확장 입력에 사용</span>
            </label>
        </div>
    `).join("")}</div>`;
}

function renderExpandedList(items) {
    const entries = sortExpandedItems(items);
    const previewItems = entries.slice(0, 12);
    const typeSummary = summarizeExpandedTypes(entries);
    const originCount = new Set(entries.map((item) => String(item.origin || "").trim()).filter(Boolean)).size;

    return `
        <div class="expanded-board">
            <div class="expanded-stat-strip">
                <div class="collector-stat-card">
                    <span>키워드</span>
                    <strong>${escapeHtml(String(entries.length))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>원본 수</span>
                    <strong>${escapeHtml(String(originCount))}</strong>
                </div>
                ${typeSummary.map((item) => `
                    <div class="collector-stat-card">
                        <span>${escapeHtml(formatExpandedType(item.type))}</span>
                        <strong>${escapeHtml(String(item.count))}</strong>
                    </div>
                `).join("")}
            </div>
            <div class="expanded-table-wrap">
                <table class="expanded-table compact">
                    <thead>
                        <tr>
                            <th>키워드</th>
                            <th>원본</th>
                            <th>유형</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${renderExpandedRows(previewItems)}
                    </tbody>
                </table>
            </div>
            ${entries.length > previewItems.length ? `
                <details class="expanded-more">
                    <summary>전체 ${escapeHtml(String(entries.length))}건 펼쳐보기</summary>
                    <div class="expanded-table-wrap full">
                        <table class="expanded-table">
                            <thead>
                                <tr>
                                    <th>키워드</th>
                                    <th>원본</th>
                                    <th>유형</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${renderExpandedRows(entries)}
                            </tbody>
                        </table>
                    </div>
                </details>
            ` : ""}
        </div>
    `;
}

function renderExpandedRows(items) {
    return items.map((item) => `
        <tr>
            <td>
                <div class="expanded-keyword-cell">
                    <strong>${escapeHtml(item.keyword || "-")}</strong>
                </div>
            </td>
            <td>${escapeHtml(item.origin || "-")}</td>
            <td><span class="badge">${escapeHtml(formatExpandedType(item.type))}</span></td>
        </tr>
    `).join("");
}

function sortExpandedItems(items) {
    return [...items].sort((left, right) => {
        const typeCompare = getExpandedTypePriority(left.type) - getExpandedTypePriority(right.type);
        if (typeCompare !== 0) {
            return typeCompare;
        }

        const originCompare = compareKoreanText(left.origin || "", right.origin || "");
        if (originCompare !== 0) {
            return originCompare;
        }

        return compareKoreanText(left.keyword || "", right.keyword || "");
    });
}

function summarizeExpandedTypes(items) {
    const counts = new Map();
    items.forEach((item) => {
        const type = String(item.type || "unknown");
        counts.set(type, (counts.get(type) || 0) + 1);
    });
    return [...counts.entries()]
        .map(([type, count]) => ({ type, count }))
        .sort((left, right) => {
            const priorityCompare = getExpandedTypePriority(left.type) - getExpandedTypePriority(right.type);
            if (priorityCompare !== 0) {
                return priorityCompare;
            }
            return right.count - left.count;
        });
}

function getExpandedTypePriority(type) {
    const priorityMap = {
        related: 0,
        autocomplete: 1,
        combinator: 2,
        manual_input: 3,
        unknown: 9,
    };

    return priorityMap[String(type || "unknown")] ?? 5;
}

function formatExpandedType(type) {
    const labelMap = {
        related: "연관검색",
        autocomplete: "자동완성",
        combinator: "조합",
        manual_input: "직접입력",
        unknown: "기타",
    };

    return labelMap[String(type || "unknown")] || String(type || "기타");
}

function renderAnalyzedList(items) {
    return `<div class="metric-list">${items.map((item) => `
        <div class="metric-item">
            <div class="keyword-main">
                <strong>${escapeHtml(item.keyword || "-")}</strong>
                <span class="badge priority-${escapeHtml(item.priority || "low")}">${escapeHtml(formatPriority(item.priority))}</span>
            </div>
            <div class="metric-meta">
                <span class="badge">점수 ${formatNumber(item.score)}</span>
                <span class="badge">CPC ${formatNumber(item.metrics?.cpc)}</span>
                <span class="badge">bid ${formatNumber(item.metrics?.bid)}</span>
                <span class="badge">경쟁 ${formatNumber(item.metrics?.competition)}</span>
                <span class="badge">기회 ${formatNumber(item.metrics?.opportunity)}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function renderSelectedList(items) {
    return `<div class="keyword-list">${items.map((item) => `
        <div class="keyword-item">
            <div class="keyword-main">
                <strong>${escapeHtml(item.keyword || "-")}</strong>
                <span class="score-line">수익 점수 ${formatNumber(item.score)}</span>
            </div>
            <div class="keyword-meta">
                <span class="badge">CPC ${formatNumber(item.metrics?.cpc)}</span>
                <span class="badge">bid ${formatNumber(item.metrics?.bid)}</span>
                <span class="badge">조회 ${formatNumber(item.metrics?.volume)}</span>
                <span class="badge">경쟁 ${formatNumber(item.metrics?.competition)}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function renderTitleList(items) {
    return `<div class="title-list">${items.map((item) => `
        <div class="title-item">
            <div class="title-keyword">
                <strong>${escapeHtml(item.keyword || "-")}</strong>
                <span class="badge">제목 4개 세트</span>
            </div>
            <div class="title-columns">
                <div class="title-column">
                    <h4>네이버 홈형</h4>
                    <ul>${(item.titles?.naver_home || []).map((title) => `<li>${escapeHtml(title)}</li>`).join("") || "<li>생성 결과 없음</li>"}</ul>
                </div>
                <div class="title-column">
                    <h4>블로그형</h4>
                    <ul>${(item.titles?.blog || []).map((title) => `<li>${escapeHtml(title)}</li>`).join("") || "<li>생성 결과 없음</li>"}</ul>
                </div>
            </div>
        </div>
    `).join("")}</div>`;
}

function handleResultsGridChange(event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
        return;
    }

    if (!target.matches("[data-collected-key]")) {
        return;
    }

    const identity = target.dataset.collectedKey || "";
    if (!identity) {
        return;
    }

    if (target.checked) {
        if (!state.selectedCollectedKeys.includes(identity)) {
            state.selectedCollectedKeys = [...state.selectedCollectedKeys, identity];
        }
    } else {
        state.selectedCollectedKeys = state.selectedCollectedKeys.filter((item) => item !== identity);
    }

    renderInputState();
}

function getSelectedCollectedItems() {
    const collectedKeywords = state.results.collected?.collected_keywords || [];
    if (collectedKeywords.length === 0) {
        return [];
    }

    const selectedSet = new Set(state.selectedCollectedKeys);
    return collectedKeywords.filter((item) => selectedSet.has(createCollectedIdentity(item)));
}

function createCollectedIdentity(item) {
    return [
        item?.keyword || "",
        item?.category || "",
        item?.source || "",
        item?.raw || "",
    ].join("||");
}

function parseKeywordText(value) {
    return String(value || "")
        .split(/[\n,;]+/g)
        .map((item) => item.trim())
        .filter((item, index, array) => item && array.indexOf(item) === index);
}

function mergeExpandedKeywords(existingItems, incomingItems) {
    const merged = [];
    const seen = new Set();

    [...(Array.isArray(existingItems) ? existingItems : []), ...(Array.isArray(incomingItems) ? incomingItems : [])]
        .forEach((item) => {
            const keyword = String(item?.keyword || "").trim();
            const origin = String(item?.origin || "").trim();
            const type = String(item?.type || "").trim();
            if (!keyword) {
                return;
            }

            const identity = `${keyword}||${origin}||${type}`;
            if (seen.has(identity)) {
                return;
            }

            seen.add(identity);
            merged.push(item);
        });

    return merged;
}

function countItems(items) {
    return Array.isArray(items) ? items.length : 0;
}

function setGlobalStatus(message, kind) {
    elements.pipelineStatus.textContent = message;
    elements.pipelineStatus.classList.remove("running", "error");
    if (kind === "running") {
        elements.pipelineStatus.classList.add("running");
    }
    if (kind === "error") {
        elements.pipelineStatus.classList.add("error");
    }
}

function addLog(message, kind = "info") {
    const now = new Date().toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });

    const line = document.createElement("div");
    line.className = `log-entry ${kind}`.trim();
    line.textContent = `[${now}] ${message}`;
    elements.activityLog.prepend(line);
    scheduleDashboardSessionSave();
}

function buildStageDetail(status) {
    if (status.state === "running") {
        return `${status.message} · ${formatElapsed(status)}`;
    }
    if (status.state === "success") {
        return `${status.message} · ${formatDuration(status.durationMs)}`;
    }
    if (status.state === "error") {
        return `${status.message} · ${formatDuration(status.durationMs)}`;
    }
    return "아직 실행되지 않았습니다.";
}

function formatStageBadge(status) {
    if (status.state === "running") return "진행 중";
    if (status.state === "success") return "완료";
    if (status.state === "error") return "오류";
    return "대기";
}

function formatElapsed(status) {
    if (!status?.startedAt) {
        return "0ms";
    }
    return formatDuration(Date.now() - status.startedAt);
}

function formatDuration(durationMs) {
    const value = Number(durationMs || 0);
    if (!Number.isFinite(value) || value <= 0) {
        return "0ms";
    }
    if (value < 1000) {
        return `${Math.round(value)}ms`;
    }
    return `${(value / 1000).toFixed(1)}s`;
}

function formatPriority(priority) {
    if (priority === "high") return "높음";
    if (priority === "medium") return "중간";
    return "낮음";
}

function formatNumber(value) {
    const number = Number(value ?? 0);
    if (!Number.isFinite(number)) return "0";
    return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
    }).format(number);
}

function buildErrorHeadline(error) {
    const stageLabel = error.stageKey ? getStage(error.stageKey)?.label || error.stageKey : "요청";
    return `${stageLabel} 실패: ${error.message}`;
}

function formatDebugValue(value) {
    if (typeof value === "string") {
        return value;
    }
    try {
        return JSON.stringify(value, null, 2);
    } catch (error) {
        return String(value);
    }
}

function tryParseJson(text) {
    if (!text) {
        return null;
    }

    try {
        return JSON.parse(text);
    } catch (error) {
        return null;
    }
}

function readLocalStorageJson(key) {
    try {
        const rawValue = window.localStorage.getItem(key);
        if (!rawValue) {
            return null;
        }
        return JSON.parse(rawValue);
    } catch (error) {
        return null;
    }
}

function readSessionStorageJson(key) {
    try {
        const rawValue = window.sessionStorage.getItem(key);
        if (!rawValue) {
            return null;
        }
        return JSON.parse(rawValue);
    } catch (error) {
        return null;
    }
}

function buildDashboardFormSnapshot() {
    const collectorMode = getCollectorMode();
    return {
        collectorMode,
        categoryInput: elements.categoryInput?.value || "",
        categorySourceInput: elements.categorySourceInput?.value || "",
        seedInput: elements.seedInput?.value || "",
        trendServiceInput: elements.trendServiceInput?.value || "",
        trendDateInput: elements.trendDateInput?.value || "",
        trendBrowserInput: elements.trendBrowserInput?.value || "",
        trendCookieInput: elements.trendCookieInput?.value || "",
        trendFallbackInput: Boolean(elements.trendFallbackInput?.checked),
        optionRelated: Boolean(elements.optionRelated?.checked),
        optionAutocomplete: Boolean(elements.optionAutocomplete?.checked),
        optionBulk: Boolean(elements.optionBulk?.checked),
        optionDebug: Boolean(elements.optionDebug?.checked),
        expanderAnalysisPath: elements.expanderAnalysisPath?.value || "",
        expandInputSource: elements.expandInputSource?.value || "collector_all",
        expandManualInput: elements.expandManualInput?.value || "",
        expandOptionRelated: Boolean(elements.expandOptionRelated?.checked),
        expandOptionAutocomplete: Boolean(elements.expandOptionAutocomplete?.checked),
        expandOptionSeedFilter: Boolean(elements.expandOptionSeedFilter?.checked),
        expandMaxResultsInput: elements.expandMaxResultsInput?.value || "",
        analyzeInputSource: elements.analyzeInputSource?.value || "expanded_results",
        analyzeManualInput: elements.analyzeManualInput?.value || "",
        analyzeKeywordStatsInput: elements.analyzeKeywordStatsInput?.value || "",
        titleMode: syncTitleModeInputFromRadios(),
        titleProvider: elements.titleProvider?.value || "",
        titleModel: elements.titleModel?.value || "",
        titleApiKey: elements.titleApiKey?.value || "",
        titleTemperature: elements.titleTemperature?.value || "",
        titleFallback: Boolean(elements.titleFallback?.checked),
        localCookieStatus: elements.localCookieStatus?.textContent || "",
    };
}

function applyDashboardFormSnapshot(formState) {
    if (!formState || typeof formState !== "object") {
        return;
    }

    document.querySelectorAll("input[name='collectorMode']").forEach((radio) => {
        radio.checked = radio.value === String(formState.collectorMode || "seed");
    });

    if (elements.categoryInput && typeof formState.categoryInput === "string") {
        elements.categoryInput.value = formState.categoryInput;
    }
    if (elements.categorySourceInput && typeof formState.categorySourceInput === "string") {
        elements.categorySourceInput.value = formState.categorySourceInput;
    }
    if (elements.seedInput && typeof formState.seedInput === "string") {
        elements.seedInput.value = formState.seedInput;
    }
    if (elements.trendServiceInput && typeof formState.trendServiceInput === "string") {
        elements.trendServiceInput.value = formState.trendServiceInput;
    }
    if (elements.trendDateInput && typeof formState.trendDateInput === "string") {
        elements.trendDateInput.value = formState.trendDateInput;
    }
    if (elements.trendBrowserInput && typeof formState.trendBrowserInput === "string") {
        elements.trendBrowserInput.value = formState.trendBrowserInput;
    }
    if (elements.trendCookieInput && typeof formState.trendCookieInput === "string") {
        elements.trendCookieInput.value = formState.trendCookieInput;
    }
    if (elements.trendFallbackInput) {
        elements.trendFallbackInput.checked = Boolean(formState.trendFallbackInput);
    }
    if (elements.optionRelated) {
        elements.optionRelated.checked = Boolean(formState.optionRelated);
    }
    if (elements.optionAutocomplete) {
        elements.optionAutocomplete.checked = Boolean(formState.optionAutocomplete);
    }
    if (elements.optionBulk) {
        elements.optionBulk.checked = Boolean(formState.optionBulk);
    }
    if (elements.optionDebug) {
        elements.optionDebug.checked = Boolean(formState.optionDebug);
    }
    if (elements.expanderAnalysisPath && typeof formState.expanderAnalysisPath === "string") {
        elements.expanderAnalysisPath.value = formState.expanderAnalysisPath;
    }
    if (elements.expandInputSource && typeof formState.expandInputSource === "string") {
        elements.expandInputSource.value = formState.expandInputSource;
    }
    if (elements.expandManualInput && typeof formState.expandManualInput === "string") {
        elements.expandManualInput.value = formState.expandManualInput;
    }
    if (elements.expandOptionRelated) {
        elements.expandOptionRelated.checked = Boolean(formState.expandOptionRelated);
    }
    if (elements.expandOptionAutocomplete) {
        elements.expandOptionAutocomplete.checked = Boolean(formState.expandOptionAutocomplete);
    }
    if (elements.expandOptionSeedFilter) {
        elements.expandOptionSeedFilter.checked = Boolean(formState.expandOptionSeedFilter);
    }
    if (elements.expandMaxResultsInput && formState.expandMaxResultsInput !== undefined) {
        elements.expandMaxResultsInput.value = String(formState.expandMaxResultsInput || "");
    }
    if (elements.analyzeInputSource && typeof formState.analyzeInputSource === "string") {
        elements.analyzeInputSource.value = formState.analyzeInputSource;
    }
    if (elements.analyzeManualInput && typeof formState.analyzeManualInput === "string") {
        elements.analyzeManualInput.value = formState.analyzeManualInput;
    }
    if (elements.analyzeKeywordStatsInput && typeof formState.analyzeKeywordStatsInput === "string") {
        elements.analyzeKeywordStatsInput.value = formState.analyzeKeywordStatsInput;
    }

    const restoredTitleMode = String(formState.titleMode || "").trim();
    if (restoredTitleMode) {
        (elements.titleModeRadios || []).forEach((radio) => {
            radio.checked = radio.value === restoredTitleMode;
        });
    }
    if (elements.titleProvider && typeof formState.titleProvider === "string") {
        elements.titleProvider.value = formState.titleProvider;
    }
    if (elements.titleModel && typeof formState.titleModel === "string") {
        elements.titleModel.value = formState.titleModel;
    }
    if (elements.titleApiKey && typeof formState.titleApiKey === "string") {
        elements.titleApiKey.value = formState.titleApiKey;
    }
    if (elements.titleTemperature && formState.titleTemperature !== undefined) {
        elements.titleTemperature.value = String(formState.titleTemperature || "");
    }
    if (elements.titleFallback) {
        elements.titleFallback.checked = Boolean(formState.titleFallback);
    }
    if (elements.localCookieStatus && typeof formState.localCookieStatus === "string" && formState.localCookieStatus.trim()) {
        elements.localCookieStatus.textContent = formState.localCookieStatus;
    }
}

function captureDashboardLogEntries(limit = 200) {
    return Array.from(elements.activityLog?.querySelectorAll(".log-entry") || [])
        .slice(0, limit)
        .map((entry) => ({
            className: entry.className || "log-entry",
            text: entry.textContent || "",
        }));
}

function restoreDashboardLogEntries(entries) {
    if (!elements.activityLog) {
        return;
    }
    elements.activityLog.innerHTML = "";
    (Array.isArray(entries) ? entries : []).forEach((entry) => {
        const line = document.createElement("div");
        line.className = String(entry?.className || "log-entry").trim() || "log-entry";
        line.textContent = String(entry?.text || "");
        elements.activityLog.append(line);
    });
}

function normalizePersistedStageStatus(stageStatusMap) {
    const nextStageStatus = createInitialStageStatus();

    STAGES.forEach((stage) => {
        const rawStatus = stageStatusMap?.[stage.key];
        if (!rawStatus || typeof rawStatus !== "object") {
            return;
        }

        const normalizedStatus = {
            ...createPendingStatus(),
            ...rawStatus,
        };
        if (normalizedStatus.state === "running") {
            const finishedAt = Date.now();
            normalizedStatus.state = "cancelled";
            normalizedStatus.message = "페이지 이동으로 중지됨";
            normalizedStatus.finishedAt = finishedAt;
            normalizedStatus.durationMs = normalizedStatus.startedAt
                ? Math.max(0, finishedAt - normalizedStatus.startedAt)
                : 0;
        }
        nextStageStatus[stage.key] = normalizedStatus;
    });

    return nextStageStatus;
}

function buildDashboardSessionPayload() {
    return {
        results: state.results,
        stageStatus: state.stageStatus,
        diagnostics: state.diagnostics,
        selectedCollectedKeys: state.selectedCollectedKeys,
        selectGradeFilters: state.selectGradeFilters,
        selectAttackabilityFilters: state.selectAttackabilityFilters,
        gradeSelectionTouched: state.gradeSelectionTouched,
        activeResultView: state.activeResultView,
        titleModeFilter: state.titleModeFilter,
        titleSort: state.titleSort,
        lastError: state.lastError,
        analyzedFilters: state.analyzedFilters,
        formState: buildDashboardFormSnapshot(),
        logEntries: captureDashboardLogEntries(),
        globalStatus: {
            message: elements.pipelineStatus?.textContent || "",
            kind: elements.pipelineStatus?.classList.contains("running")
                ? "running"
                : elements.pipelineStatus?.classList.contains("error")
                    ? "error"
                    : elements.pipelineStatus?.classList.contains("cancelled")
                        ? "cancelled"
                        : "idle",
        },
    };
}

function persistDashboardSessionNow() {
    if (!elements.resultsGrid) {
        return;
    }

    try {
        window.sessionStorage.setItem(
            DASHBOARD_SESSION_STORAGE_KEY,
            JSON.stringify(buildDashboardSessionPayload()),
        );
    } catch (error) {
        // Ignore storage failures and keep the dashboard usable.
    }
}

function scheduleDashboardSessionSave() {
    if (dashboardSessionSaveTimer) {
        window.clearTimeout(dashboardSessionSaveTimer);
    }
    dashboardSessionSaveTimer = window.setTimeout(() => {
        dashboardSessionSaveTimer = null;
        persistDashboardSessionNow();
    }, 120);
}

function restoreDashboardSession() {
    const snapshot = readSessionStorageJson(DASHBOARD_SESSION_STORAGE_KEY);
    if (!snapshot || typeof snapshot !== "object") {
        return false;
    }

    applyDashboardFormSnapshot(snapshot.formState);

    state.results = {
        ...createEmptyResults(),
        ...(snapshot.results || {}),
    };
    state.stageStatus = normalizePersistedStageStatus(snapshot.stageStatus);
    state.diagnostics = {
        ...createEmptyDiagnostics(),
        ...(snapshot.diagnostics || {}),
    };
    state.selectedCollectedKeys = Array.isArray(snapshot.selectedCollectedKeys)
        ? [...snapshot.selectedCollectedKeys]
        : [];
    state.selectGradeFilters = normalizeProfitabilityList(
        snapshot.selectGradeFilters?.length ? snapshot.selectGradeFilters : PROFITABILITY_ORDER,
    );
    state.selectAttackabilityFilters = normalizeAttackabilityList(
        snapshot.selectAttackabilityFilters?.length ? snapshot.selectAttackabilityFilters : ATTACKABILITY_ORDER,
    );
    state.gradeSelectionTouched = Boolean(snapshot.gradeSelectionTouched);
    state.activeResultView = normalizeResultViewKey(snapshot.activeResultView) || "";
    state.titleModeFilter = normalizeTitleResultModeFilter(snapshot.titleModeFilter);
    state.titleSort = normalizeTitleResultSort(snapshot.titleSort);
    state.lastError = snapshot.lastError || null;
    state.analyzedFilters = {
        ...createDefaultAnalyzedFilters(),
        ...(snapshot.analyzedFilters || {}),
    };
    state.isBusy = false;
    state.streamAbortController = null;
    state.streamAbortEndpoint = "";
    state.streamAbortRequested = false;
    state.requestAbortController = null;
    state.requestAbortStageKey = "";
    state.requestAbortEndpoint = "";
    state.requestAbortRequested = false;

    restoreDashboardLogEntries(snapshot.logEntries);

    const globalStatus = snapshot.globalStatus || {};
    if (globalStatus.message) {
        setGlobalStatus(globalStatus.message, globalStatus.kind || "idle");
    }
    return true;
}

function sanitizeSensitiveData(value) {
    if (Array.isArray(value)) {
        return value.map((item) => sanitizeSensitiveData(item));
    }

    if (!value || typeof value !== "object") {
        return value;
    }

    const sensitiveKeys = new Set([
        "api_key",
        "apikey",
        "authorization",
        "token",
        "access_token",
        "auth_cookie",
        "cookie",
    ]);
    const sanitized = {};

    Object.entries(value).forEach(([key, entryValue]) => {
        if (sensitiveKeys.has(String(key).toLowerCase())) {
            sanitized[key] = maskSecret(entryValue);
            return;
        }
        sanitized[key] = sanitizeSensitiveData(entryValue);
    });

    return sanitized;
}

function maskSecret(value) {
    const text = String(value || "");
    if (!text) {
        return "";
    }
    if (text.length <= 8) {
        return "********";
    }
    return `${text.slice(0, 4)}********${text.slice(-4)}`;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function syncBusyButtons() {
    elements.actionButtons.forEach((button) => {
        button.disabled = state.isBusy;
    });
}

function startTicker() {
    if (state.tickerId) {
        window.clearInterval(state.tickerId);
    }
    state.tickerId = window.setInterval(() => {
        if (!state.isBusy) {
            return;
        }
        renderProgress();
        renderStageList();
    }, 250);
}

function renderResults() {
    const cards = [];

    if (state.results.collected?.collected_keywords) {
        cards.push(
            resultCard("수집 키워드", state.results.collected.collected_keywords, renderCollectedList, {
                limit: "all",
                subtitle: "원본 쿼리별로 묶어서 바로 선택할 수 있습니다.",
                className: "collector-result-card",
            }),
        );
    }
    if (state.results.expanded?.expanded_keywords) {
        cards.push(resultCard("확장 키워드", state.results.expanded.expanded_keywords, renderExpandedList));
    }
    if (state.results.analyzed?.analyzed_keywords) {
        cards.push(resultCard("분석 결과", state.results.analyzed.analyzed_keywords, renderAnalyzedList));
    }
    if (state.results.selected?.selected_keywords) {
        cards.push(resultCard("골든 키워드", state.results.selected.selected_keywords, renderSelectedList));
    }
    if (state.results.titled?.generated_titles) {
        cards.push(resultCard("생성된 제목", state.results.titled.generated_titles, renderTitleList));
    }

    elements.resultsGrid.innerHTML = cards.length > 0
        ? cards.join("")
        : `
            <div class="placeholder">
                실행 버튼을 누르면 단계별 결과와 진단 정보가 이 영역에 표시됩니다.<br />
                수집 결과는 쿼리별로 묶어서 보여주고, collector 진단은 코드 대신 읽기 쉬운 표와 요약 카드로 정리합니다.
            </div>
        `;
}

function renderDiagnosticCard(diagnostic) {
    const summary = diagnostic.responseSummary || diagnostic.error || {};
    const statusLabel = diagnostic.status === "success" ? "정상" : "오류";
    const openByDefault = diagnostic.status === "error" || diagnostic.stageKey === "collected";
    const bodyHtml = diagnostic.stageKey === "collected"
        ? renderCollectorDiagnostic(diagnostic)
        : renderGenericDiagnosticBody(diagnostic, summary);

    return `
        <details class="debug-card" ${openByDefault ? "open" : ""}>
            <summary>
                <div>
                    <strong>${escapeHtml(diagnostic.stageLabel)}</strong>
                    <span>${escapeHtml(`${statusLabel} · ${formatDuration(diagnostic.durationMs)}`)}</span>
                </div>
                <span class="stage-chip ${diagnostic.status}">${escapeHtml(statusLabel)}</span>
            </summary>
            <div class="debug-card-body">${bodyHtml}</div>
        </details>
    `;
}

function renderGenericDiagnosticBody(diagnostic, summary) {
    const backendDebugSummary = diagnostic.backendDebug?.summary || null;

    return `
        <div class="debug-meta">
            <span class="badge">request_id ${escapeHtml(diagnostic.requestId || "없음")}</span>
            <span class="badge">${escapeHtml(diagnostic.endpoint || "-")}</span>
            <span class="badge">${escapeHtml(diagnostic.startedAt || "-")}</span>
            ${backendDebugSummary ? `<span class="badge">warning ${escapeHtml(String(backendDebugSummary.warning_count || 0))}</span>` : ""}
        </div>
        <div class="debug-columns">
            <div class="debug-section">
                <h4>요청</h4>
                <pre>${escapeHtml(formatDebugValue(diagnostic.request))}</pre>
            </div>
            <div class="debug-section">
                <h4>${diagnostic.status === "success" ? "응답 요약" : "오류 상세"}</h4>
                <pre>${escapeHtml(formatDebugValue(summary))}</pre>
            </div>
        </div>
        ${diagnostic.backendDebug ? `
            <div class="debug-section debug-section-full">
                <h4>Collector Debug</h4>
                <pre>${escapeHtml(formatDebugValue(diagnostic.backendDebug))}</pre>
            </div>
        ` : ""}
    `;
}

function renderCollectorDiagnostic(diagnostic) {
    const request = diagnostic.request || {};
    const backendDebug = diagnostic.backendDebug || diagnostic.responseSummary?.backend_debug || null;
    const summary = backendDebug?.summary || {};
    const queryLogs = Array.isArray(backendDebug?.query_logs) ? backendDebug.query_logs : [];
    const warnings = Array.isArray(backendDebug?.warnings) ? backendDebug.warnings : [];
    const sampleItems = Array.isArray(diagnostic.responseSummary?.sample_items)
        ? diagnostic.responseSummary.sample_items
        : [];

    return `
        <div class="debug-meta">
            <span class="badge">request_id ${escapeHtml(diagnostic.requestId || "없음")}</span>
            <span class="badge">${escapeHtml(diagnostic.endpoint || "-")}</span>
            <span class="badge">${escapeHtml(diagnostic.startedAt || "-")}</span>
            <span class="badge">${escapeHtml(formatCollectorMode(request.mode))}</span>
            ${backendDebug?.effective_source ? `<span class="badge">${escapeHtml(formatCollectorEffectiveSource(backendDebug.effective_source))}</span>` : ""}
            ${summary.warning_count ? `<span class="badge">warning ${escapeHtml(String(summary.warning_count))}</span>` : ""}
        </div>
        <div class="collector-debug-grid">
            <section class="collector-debug-panel">
                <h4>수집 요청</h4>
                <div class="collector-field-grid">
                    ${renderCollectorField("수집 모드", formatCollectorMode(request.mode))}
                    ${renderCollectorField("카테고리", request.category || backendDebug?.resolved_category || "-")}
                    ${renderCollectorField("시드", request.seed_input || "-")}
                    ${renderCollectorField("카테고리 소스", formatCollectorSourceMode(request.category_source || backendDebug?.requested_category_source))}
                    ${renderCollectorField("실제 사용 소스", formatCollectorEffectiveSource(backendDebug?.effective_source))}
                    ${renderCollectorField("연관 수집", formatEnabledState(request.options?.collect_related))}
                    ${renderCollectorField("자동완성", formatEnabledState(request.options?.collect_autocomplete))}
                    ${renderCollectorField("쿼리 확장", formatEnabledState(request.options?.collect_bulk))}
                    ${renderCollectorField("디버그", formatEnabledState(request.debug))}
                    ${renderCollectorField("검색 영역", backendDebug?.search_area || "-")}
                    ${renderCollectorField("트렌드 서비스", backendDebug?.trend_service || request.trend_options?.service || "-")}
                    ${renderCollectorField("트렌드 주제", backendDebug?.trend_topic || "-")}
                    ${renderCollectorField("트렌드 날짜", backendDebug?.trend_date || request.trend_options?.date || "-")}
                </div>
            </section>
            <section class="collector-debug-panel">
                <h4>수집 요약</h4>
                <div class="collector-stat-grid">
                    ${renderCollectorMetric("시도 쿼리", summary.queries_attempted)}
                    ${renderCollectorMetric("결과 있음", summary.queries_with_results)}
                    ${renderCollectorMetric("트렌드 성공", summary.trend_hits)}
                    ${renderCollectorMetric("자동완성 성공", summary.autocomplete_hits)}
                    ${renderCollectorMetric("연관검색 성공", summary.related_hits)}
                    ${renderCollectorMetric("검색 폴백 성공", summary.fallback_hits)}
                    ${renderCollectorMetric("중복 제거 후", summary.deduped_keyword_count)}
                    ${renderCollectorMetric("경고", summary.warning_count)}
                </div>
                ${sampleItems.length ? `
                    <div class="collector-sample-list">
                        ${sampleItems.map((item) => `
                            <span class="badge">${escapeHtml(item.keyword || "-")}</span>
                        `).join("")}
                    </div>
                ` : `
                    <div class="collector-empty">미리보기 키워드가 없습니다.</div>
                `}
            </section>
        </div>
        <section class="collector-debug-panel collector-debug-panel-full">
            <div class="collector-panel-head">
                <h4>Collector Query Log</h4>
                <span class="badge">total ${escapeHtml(String(queryLogs.length))}</span>
            </div>
            ${queryLogs.length ? `
                <div class="collector-table-wrap">
                    <table class="collector-debug-table">
                        <thead>
                            <tr>
                                <th>Query</th>
                                <th>Area</th>
                                <th>Source</th>
                                <th>Status</th>
                                <th>Results</th>
                                <th>Time</th>
                                <th>Notes</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${queryLogs.map((item) => `
                                <tr>
                                    <td>
                                        <strong>${escapeHtml(item.query || "-")}</strong>
                                    </td>
                                    <td>${escapeHtml(formatCollectorSearchArea(item.search_area))}</td>
                                    <td>${escapeHtml(formatCollectorSource(item.source))}</td>
                                    <td><span class="collector-status-pill ${escapeHtml(item.status || "empty")}">${escapeHtml(formatCollectorLogStatus(item.status))}</span></td>
                                    <td>${escapeHtml(String(item.result_count ?? 0))}</td>
                                    <td>${escapeHtml(formatDuration(item.elapsed_ms))}</td>
                                    <td>${escapeHtml(formatCollectorNotes(item.notes))}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            ` : `
                <div class="collector-empty">collector debug를 켜면 시도한 쿼리 로그가 표시됩니다.</div>
            `}
        </section>
        <section class="collector-debug-panel collector-debug-panel-full">
            <div class="collector-panel-head">
                <h4>Warnings</h4>
                <span class="badge">total ${escapeHtml(String(warnings.length))}</span>
            </div>
            ${warnings.length ? `
                <div class="collector-warning-list">
                    ${warnings.map((warning) => `
                        <article class="collector-warning-item">
                            <strong>${escapeHtml(warning.code || "warning")}</strong>
                            <p>${escapeHtml(warning.message || "-")}</p>
                            <span>${escapeHtml(formatCollectorWarningDetail(warning.detail))}</span>
                        </article>
                    `).join("")}
                </div>
            ` : `
                <div class="collector-empty">경고가 없습니다.</div>
            `}
        </section>
    `;
}

function renderCollectorField(label, value) {
    return `
        <div class="collector-field">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(String(value || "-"))}</strong>
        </div>
    `;
}

function renderCollectorMetric(label, value) {
    return `
        <div class="collector-metric-card">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(String(value ?? 0))}</strong>
        </div>
    `;
}

function formatTrendRankChange(value) {
    if (value === null || value === undefined || value === "") {
        return "변동 new";
    }

    const normalized = Number(value);
    if (!Number.isFinite(normalized)) {
        return `변동 ${String(value)}`;
    }
    if (normalized === 0) {
        return "변동 -";
    }
    return normalized > 0 ? `변동 ▲${normalized}` : `변동 ▼${Math.abs(normalized)}`;
}

function resultCard(title, items, renderer, options = {}) {
    const entries = Array.isArray(items) ? items : [];
    const visibleItems = options.limit === "all"
        ? entries
        : entries.slice(0, options.limit ?? 8);

    return `
        <article class="result-card ${escapeHtml(options.className || "")}">
            <div class="result-head">
                <div class="result-head-copy">
                    <h3>${escapeHtml(title)}</h3>
                    ${options.subtitle ? `<p class="result-subtitle">${escapeHtml(options.subtitle)}</p>` : ""}
                </div>
                <span class="result-count">총 ${countItems(entries)}건</span>
            </div>
            ${renderer(visibleItems)}
        </article>
    `;
}

function renderCollectedList(items) {
    const groups = groupCollectedItems(items);
    const selectedCount = getSelectedCollectedItems().length;
    const sourceCounts = summarizeCollectedSources(items);

    return `
        <div class="collector-board">
            <div class="collector-toolbar">
                <div class="collector-stat-strip">
                    <div class="collector-stat-card">
                        <span>키워드</span>
                        <strong>${escapeHtml(String(items.length))}</strong>
                    </div>
                    <div class="collector-stat-card">
                        <span>선택됨</span>
                        <strong>${escapeHtml(String(selectedCount))}</strong>
                    </div>
                    <div class="collector-stat-card">
                        <span>쿼리 묶음</span>
                        <strong>${escapeHtml(String(groups.length))}</strong>
                    </div>
                    <div class="collector-stat-card">
                        <span>출처 수</span>
                        <strong>${escapeHtml(String(sourceCounts.length))}</strong>
                    </div>
                </div>
                <div class="collector-toolbar-actions">
                    <button type="button" class="ghost-btn collector-action-btn" data-collector-action="select_all">전체 선택</button>
                    <button type="button" class="ghost-btn collector-action-btn" data-collector-action="clear_all">선택 해제</button>
                </div>
            </div>
            ${sourceCounts.length ? `
                <div class="collector-source-strip">
                    ${sourceCounts.map((item) => `
                        <span class="badge">${escapeHtml(formatCollectorSource(item.source))} ${escapeHtml(String(item.count))}건</span>
                    `).join("")}
                </div>
            ` : ""}
            <div class="collector-groups">
                ${groups.map((group) => `
                    <section class="collector-group">
                        <div class="collector-group-head">
                            <div>
                                <div class="collector-group-title">
                                    <strong>${escapeHtml(group.raw)}</strong>
                                    <span>${escapeHtml(String(group.items.length))}건</span>
                                </div>
                                <div class="collector-group-meta">
                                    ${group.category ? `<span class="badge">카테고리 ${escapeHtml(group.category)}</span>` : ""}
                                    ${group.sources.map((source) => `<span class="badge">${escapeHtml(formatCollectorSource(source))}</span>`).join("")}
                                    ${group.selectedCount ? `<span class="badge">${escapeHtml(String(group.selectedCount))}건 선택</span>` : ""}
                                </div>
                            </div>
                            <div class="collector-group-actions">
                                <button type="button" class="ghost-btn collector-action-btn" data-collector-action="select_group" data-collector-group="${escapeHtml(group.raw)}">묶음 선택</button>
                                <button type="button" class="ghost-btn collector-action-btn" data-collector-action="clear_group" data-collector-group="${escapeHtml(group.raw)}">묶음 해제</button>
                            </div>
                        </div>
                        <div class="collector-row-list">
                            ${group.items.map((item, index) => {
                                const identity = createCollectedIdentity(item);
                                const selected = state.selectedCollectedKeys.includes(identity);

                                return `
                                    <label class="collector-row ${selected ? "selected" : ""}">
                                        <span class="collector-rank ${item.source === "naver_trend" ? "trend" : ""}">${escapeHtml(String(item.rank ?? index + 1))}</span>
                                        <input
                                            type="checkbox"
                                            data-collected-key="${escapeHtml(identity)}"
                                            ${selected ? "checked" : ""}
                                        />
                                        <span class="collector-keyword">
                                            <strong>${escapeHtml(item.keyword || "-")}</strong>
                                            <span>${escapeHtml(formatCollectorSource(item.source))}</span>
                                        </span>
                                        <span class="collector-row-tags">
                                            ${item.rank ? `<span class="badge">순위 ${escapeHtml(String(item.rank))}위</span>` : ""}
                                            ${item.rank_change !== undefined ? `<span class="badge">${escapeHtml(formatTrendRankChange(item.rank_change))}</span>` : ""}
                                            <span class="badge">${escapeHtml(item.category || "미분류")}</span>
                                        </span>
                                    </label>
                                `;
                            }).join("")}
                        </div>
                    </section>
                `).join("")}
            </div>
        </div>
    `;
}

function handleResultsGridChange(event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
        return;
    }

    if (!target.matches("[data-collected-key]")) {
        return;
    }

    const identity = target.dataset.collectedKey || "";
    if (!identity) {
        return;
    }

    if (target.checked) {
        if (!state.selectedCollectedKeys.includes(identity)) {
            state.selectedCollectedKeys = [...state.selectedCollectedKeys, identity];
        }
    } else {
        state.selectedCollectedKeys = state.selectedCollectedKeys.filter((item) => item !== identity);
    }

    renderInputState();
    renderResults();
}

function handleResultsGridClick(event) {
    if (!(event.target instanceof Element)) {
        return;
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

function applyCollectedSelection(items, shouldSelect) {
    const nextSelection = new Set(state.selectedCollectedKeys);

    items.forEach((item) => {
        const identity = createCollectedIdentity(item);
        if (shouldSelect) {
            nextSelection.add(identity);
            return;
        }
        nextSelection.delete(identity);
    });

    state.selectedCollectedKeys = [...nextSelection];
    renderAll();
}

function groupCollectedItems(items) {
    const grouped = new Map();

    sortCollectedItems(items).forEach((item) => {
        const groupKey = item.raw || item.keyword || "-";
        const group = grouped.get(groupKey) || {
            raw: groupKey,
            category: item.category || "",
            items: [],
            selectedCount: 0,
            sources: new Set(),
        };

        group.items.push(item);
        group.sources.add(item.source || "unknown");
        if (!group.category && item.category) {
            group.category = item.category;
        }
        if (state.selectedCollectedKeys.includes(createCollectedIdentity(item))) {
            group.selectedCount += 1;
        }

        grouped.set(groupKey, group);
    });

    return [...grouped.values()]
        .map((group) => ({
            ...group,
            sources: [...group.sources].sort((left, right) => getCollectorSourcePriority(left) - getCollectorSourcePriority(right)),
        }))
        .sort((left, right) => {
            if (right.selectedCount !== left.selectedCount) {
                return right.selectedCount - left.selectedCount;
            }
            if (right.items.length !== left.items.length) {
                return right.items.length - left.items.length;
            }
            return compareKoreanText(left.raw, right.raw);
        });
}

function sortCollectedItems(items) {
    return [...items].sort((left, right) => {
        const leftSelected = state.selectedCollectedKeys.includes(createCollectedIdentity(left)) ? 0 : 1;
        const rightSelected = state.selectedCollectedKeys.includes(createCollectedIdentity(right)) ? 0 : 1;
        if (leftSelected !== rightSelected) {
            return leftSelected - rightSelected;
        }

        const rawCompare = compareKoreanText(left.raw || left.keyword, right.raw || right.keyword);
        if (rawCompare !== 0) {
            return rawCompare;
        }

        const sourceCompare = getCollectorSourcePriority(left.source) - getCollectorSourcePriority(right.source);
        if (sourceCompare !== 0) {
            return sourceCompare;
        }

        if (left.source === "naver_trend" && right.source === "naver_trend") {
            const leftRank = Number(left.rank || Number.MAX_SAFE_INTEGER);
            const rightRank = Number(right.rank || Number.MAX_SAFE_INTEGER);
            if (leftRank !== rightRank) {
                return leftRank - rightRank;
            }
        }

        return compareKoreanText(left.keyword, right.keyword);
    });
}

function summarizeCollectedSources(items) {
    const sourceMap = new Map();

    items.forEach((item) => {
        const source = item.source || "unknown";
        sourceMap.set(source, (sourceMap.get(source) || 0) + 1);
    });

    return [...sourceMap.entries()]
        .map(([source, count]) => ({ source, count }))
        .sort((left, right) => {
            if (right.count !== left.count) {
                return right.count - left.count;
            }
            return getCollectorSourcePriority(left.source) - getCollectorSourcePriority(right.source);
        });
}

function compareKoreanText(left, right) {
    return String(left || "").localeCompare(String(right || ""), "ko");
}

STAGES.splice(
    0,
    STAGES.length,
    {
        key: "collected",
        label: "1단계 수집",
        shortLabel: "수집",
        description: "시드 또는 카테고리 기준으로 시작 키워드를 수집합니다.",
        resultKey: "collected_keywords",
    },
    {
        key: "expanded",
        label: "2단계 확장",
        shortLabel: "확장",
        description: "연관확장과 자동완성으로 키워드를 넓힙니다.",
        resultKey: "expanded_keywords",
    },
    {
        key: "analyzed",
        label: "3단계 분석",
        shortLabel: "분석",
        description: "점수와 우선순위를 계산해 후보를 평가합니다.",
        resultKey: "analyzed_keywords",
    },
    {
        key: "selected",
        label: "4단계 선별",
        shortLabel: "선별",
        description: "조건에 맞는 골든 키워드만 추립니다.",
        resultKey: "selected_keywords",
    },
    {
        key: "titled",
        label: "5단계 제목",
        shortLabel: "제목",
        description: "선택한 키워드로 제목을 생성합니다.",
        resultKey: "generated_titles",
    },
);

function bindElements() {
    elements.categoryInput = document.getElementById("categoryInput");
    elements.categorySourceInput = document.getElementById("categorySourceInput");
    elements.seedInput = document.getElementById("seedInput");
    elements.trendServiceInput = document.getElementById("trendServiceInput");
    elements.trendDateInput = document.getElementById("trendDateInput");
    elements.trendBrowserInput = document.getElementById("trendBrowserInput");
    elements.trendCookieInput = document.getElementById("trendCookieInput");
    elements.trendFallbackInput = document.getElementById("trendFallbackInput");
    elements.trendSourceHelp = document.getElementById("trendSourceHelp");
    elements.launchLoginBrowserButton = document.getElementById("launchLoginBrowserButton");
    elements.loadLocalCookieButton = document.getElementById("loadLocalCookieButton");
    elements.localCookieStatus = document.getElementById("localCookieStatus");
    elements.expanderAnalysisPath = document.getElementById("expanderAnalysisPath");
    elements.optionRelated = document.getElementById("optionRelated");
    elements.optionAutocomplete = document.getElementById("optionAutocomplete");
    elements.optionBulk = document.getElementById("optionBulk");
    elements.optionDebug = document.getElementById("optionDebug");
    elements.expandInputSource = document.getElementById("expandInputSource");
    elements.expandManualInput = document.getElementById("expandManualInput");
    elements.expandOptionRelated = document.getElementById("expandOptionRelated");
    elements.expandOptionAutocomplete = document.getElementById("expandOptionAutocomplete");
    elements.expandOptionSeedFilter = document.getElementById("expandOptionSeedFilter");
    elements.expandMaxResultsInput = document.getElementById("expandMaxResultsInput");
    elements.expandLimitButtons = Array.from(document.querySelectorAll("[data-expand-limit]"));
    elements.expandSourceVisibilityBlocks = Array.from(document.querySelectorAll("[data-expand-source-visibility]"));
    elements.analyzeInputSource = document.getElementById("analyzeInputSource");
    elements.analyzeManualInput = document.getElementById("analyzeManualInput");
    elements.analyzeKeywordStatsInput = document.getElementById("analyzeKeywordStatsInput");
    elements.exportCsvButton = document.getElementById("exportCsvButton");
    elements.exportTitleCsvButton = document.getElementById("exportTitleCsvButton");
    elements.analyzeSourceVisibilityBlocks = Array.from(document.querySelectorAll("[data-analyze-source-visibility]"));
    elements.selectedCollectedCount = document.getElementById("selectedCollectedCount");
    elements.manualAnalyzeCount = document.getElementById("manualAnalyzeCount");
    elements.gradePresetButtons = Array.from(document.querySelectorAll("[data-selection-preset]"));
    elements.gradeToggleButtons = Array.from(document.querySelectorAll("[data-profitability-toggle]"));
    elements.attackabilityToggleButtons = Array.from(document.querySelectorAll("[data-attackability-toggle]"));
    elements.runGradeSelectButton = document.getElementById("runGradeSelectButton");
    elements.gradeSelectSummary = document.getElementById("gradeSelectSummary");
    elements.titleMode = document.getElementById("titleMode");
    elements.titlePreset = document.getElementById("titlePreset");
    elements.titlePresetDescription = document.getElementById("titlePresetDescription");
    elements.titleProvider = document.getElementById("titleProvider");
    elements.titleModel = document.getElementById("titleModel");
    elements.titleApiKey = document.getElementById("titleApiKey");
    elements.titleTemperature = document.getElementById("titleTemperature");
    elements.titleTemperatureDescription = document.getElementById("titleTemperatureDescription");
    elements.titleFallback = document.getElementById("titleFallback");
    elements.titleSystemPrompt = document.getElementById("titleSystemPrompt");
    elements.titlePromptSummary = document.getElementById("titlePromptSummary");
    elements.openTitlePromptEditorButton = document.getElementById("openTitlePromptEditorButton");
    elements.clearTitlePromptButton = document.getElementById("clearTitlePromptButton");
    elements.titleModeBadge = document.getElementById("titleModeBadge");
    elements.titleModeRadios = Array.from(document.querySelectorAll("input[name='titleModeOption']"));
    elements.titleModeVisibilityBlocks = Array.from(document.querySelectorAll("[data-title-mode-visibility]"));
    elements.statusList = document.getElementById("statusList");
    elements.resultsGrid = document.getElementById("resultsGrid");
    elements.activityLog = document.getElementById("activityLog");
    elements.pipelineStatus = document.getElementById("pipelineStatus");
    elements.progressBar = document.getElementById("progressBar");
    elements.progressText = document.getElementById("progressText");
    elements.progressDetail = document.getElementById("progressDetail");
    elements.errorConsole = document.getElementById("errorConsole");
    elements.debugPanels = document.getElementById("debugPanels");
    elements.actionButtons = Array.from(document.querySelectorAll("button"));
}

function bindEvents() {
    document.querySelectorAll("input[name='collectorMode']").forEach((element) => {
        element.addEventListener("change", renderInputState);
    });
    document.getElementById("runCollectButton").addEventListener("click", () => {
        runWithGuard(runCollectFromScratch, "수집 단계 실행 중");
    });
    document.getElementById("runExpandButton").addEventListener("click", () => {
        runWithGuard(runThroughExpand, "확장 단계 실행 중");
    });
    document.getElementById("runAnalyzeButton").addEventListener("click", () => {
        runWithGuard(runThroughAnalyze, "분석 단계 실행 중");
    });
    document.getElementById("runSelectButton").addEventListener("click", () => {
        runWithGuard(runThroughSelect, "선별 단계 실행 중");
    });
    document.getElementById("runTitleButton").addEventListener("click", () => {
        runWithGuard(runThroughTitle, "제목 생성 단계 실행 중");
    });
    document.getElementById("runFullButton").addEventListener("click", () => {
        runWithGuard(runFullFlow, "전체 파이프라인 실행 중");
    });
    document.getElementById("resetButton").addEventListener("click", resetAll);
    document.getElementById("clearDebugButton").addEventListener("click", clearDiagnostics);
    elements.resultsGrid.addEventListener("click", handleResultsGridClick);
    elements.resultsGrid.addEventListener("change", handleResultsGridChange);
    elements.expandManualInput.addEventListener("input", renderInputState);
    elements.expandInputSource.addEventListener("change", renderInputState);
    elements.analyzeManualInput.addEventListener("input", renderInputState);
    elements.analyzeInputSource.addEventListener("change", renderInputState);
    elements.analyzeKeywordStatsInput?.addEventListener("input", renderInputState);
    elements.expandMaxResultsInput?.addEventListener("input", () => {
        elements.expandLimitButtons.forEach((button) => button.classList.remove("active"));
    });
    [
        elements.categorySourceInput,
        elements.trendServiceInput,
        elements.trendDateInput,
        elements.trendBrowserInput,
        elements.trendCookieInput,
        elements.trendFallbackInput,
    ].forEach((element) => {
        element.addEventListener("input", handleTrendSettingsChange);
        element.addEventListener("change", handleTrendSettingsChange);
    });
    elements.loadLocalCookieButton.addEventListener("click", () => {
        runWithGuard(importLocalNaverCookie, "로컬 네이버 세션 불러오는 중");
    });
    elements.launchLoginBrowserButton.addEventListener("click", () => {
        runWithGuard(openDedicatedLoginBrowser, "전용 로그인 브라우저 여는 중");
    });
    [
        elements.titleProvider,
        elements.titleModel,
        elements.titleApiKey,
        elements.titleTemperature,
        elements.titleFallback,
    ].forEach((element) => {
        element.addEventListener("input", handleTitleSettingsChange);
        element.addEventListener("change", handleTitleSettingsChange);
    });
    elements.titleModeRadios.forEach((element) => {
        element.addEventListener("change", handleTitleSettingsChange);
    });
    document.querySelectorAll("[data-preset]").forEach((button) => {
        button.addEventListener("click", () => applyPreset(button.dataset.preset || "finance"));
    });
    elements.guideTabButtons.forEach((button) => {
        button.addEventListener("click", () => setGuideTab(button.dataset.guideTab || ""));
    });
    elements.expandLimitButtons.forEach((button) => {
        button.addEventListener("click", () => setExpandLimitPreset(button.dataset.expandLimit || "1000"));
    });
    elements.exportCsvButton?.addEventListener("click", downloadAnalyzedCsv);
    elements.exportTitleCsvButton?.addEventListener("click", downloadTitleCsv);
    setExpandLimitPreset(elements.expandMaxResultsInput?.value || "1000");
}

function setExpandLimitPreset(limit) {
    elements.expandLimitButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.expandLimit === limit);
    });

    if (!elements.expandMaxResultsInput) {
        return;
    }

    if (limit === "infinite") {
        elements.expandMaxResultsInput.value = "";
        elements.expandMaxResultsInput.placeholder = "무제한";
        return;
    }

    elements.expandMaxResultsInput.value = limit;
    elements.expandMaxResultsInput.placeholder = "예: 1000";
}

async function runAnalyzeStage() {
    const source = elements.analyzeInputSource.value;
    const expandSource = elements.expandInputSource?.value || "collector_all";

    if (source === "manual_text") {
        const inputData = buildAnalyzeInput();
        addLog(`분석 시작: ${describeAnalyzeSource(inputData)}`);
        clearStageAndDownstream("analyzed");
        const result = await executeStage({
            stageKey: "analyzed",
            endpoint: "/analyze",
            inputData,
        });
        state.results.analyzed = result;
        addLog(`분석 완료: ${countItems(result.analyzed_keywords)}건`, "success");
        renderAll();
        return result;
    }

    if (
        !state.results.expanded?.expanded_keywords?.length
        && expandSource !== "manual_text"
        && !state.results.collected?.collected_keywords?.length
    ) {
        await runCollectStage();
    }

    if (state.results.expanded?.expanded_keywords?.length) {
        const inputData = buildAnalyzeInput();
        addLog(`분석 시작: ${describeAnalyzeSource(inputData)}`);
        clearStageAndDownstream("analyzed");
        const result = await executeStage({
            stageKey: "analyzed",
            endpoint: "/analyze",
            inputData,
        });
        state.results.analyzed = result;
        addLog(`분석 완료: ${countItems(result.analyzed_keywords)}건`, "success");
        renderAll();
        return result;
    }

    const inputData = buildExpandInput();
    addLog(`확장 및 분석 시작: ${describeExpandSource(inputData)}`);
    clearStageAndDownstream("expanded");
    const result = await executeExpandAnalyzeStageStream(inputData);
    state.results.expanded = {
        ...(state.results.expanded || {}),
        expanded_keywords: result.expanded_keywords || [],
    };
    state.results.analyzed = {
        analyzed_keywords: result.analyzed_keywords || [],
    };
    addLog(
        `확장 ${countItems(result.expanded_keywords)}건 · 분석 ${countItems(result.analyzed_keywords)}건 완료`,
        "success",
    );
    renderAll();
    return result;
}

function buildExpandInput() {
    const source = elements.expandInputSource.value;
    const analysisPath = elements.expanderAnalysisPath.value.trim();
    const category = elements.categoryInput.value.trim();
    const expandOptions = {
        enable_related: elements.expandOptionRelated?.checked ?? true,
        enable_autocomplete: elements.expandOptionAutocomplete?.checked ?? true,
        enable_seed_filter: elements.expandOptionSeedFilter?.checked ?? true,
        max_results: coerceExpandLimitValue(elements.expandMaxResultsInput?.value),
    };

    if (source === "manual_text") {
        const keywordsText = elements.expandManualInput.value.trim();
        const keywords = parseKeywordText(keywordsText);
        if (keywords.length === 0) {
            throw new Error("확장할 키워드를 직접 입력해 주세요.");
        }

        return {
            keywords_text: keywordsText,
            category,
            source: "manual_input",
            analysis_json_path: analysisPath,
            expand_options: expandOptions,
        };
    }

    const collectedKeywords = source === "collector_selected"
        ? getSelectedCollectedItems()
        : state.results.collected?.collected_keywords || [];

    if (collectedKeywords.length === 0) {
        throw new Error(
            source === "collector_selected"
                ? "확장에 사용할 수집 키워드를 최소 1개 선택해 주세요."
                : "수집 결과가 없습니다. 먼저 수집을 실행해 주세요.",
        );
    }

    return {
        collected_keywords: collectedKeywords,
        analysis_json_path: analysisPath,
        expand_options: expandOptions,
    };
}

async function executeExpandAnalyzeStageStream(inputData) {
    const expandedStartedAt = Date.now();
    const analyzedStartedAt = expandedStartedAt;
    const startedAtLabel = new Date(expandedStartedAt).toISOString();

    state.stageStatus.expanded = {
        state: "running",
        message: "실시간 확장 중",
        startedAt: expandedStartedAt,
        finishedAt: null,
        durationMs: null,
    };
    state.stageStatus.analyzed = {
        state: "running",
        message: "실시간 분석 중",
        startedAt: analyzedStartedAt,
        finishedAt: null,
        durationMs: null,
    };
    state.results.expanded = {
        expanded_keywords: [],
        stream_meta: {
            phase: "starting",
            currentKeyword: "",
            depth: 0,
            totalResults: 0,
            queueSize: 0,
            totalOrigins: 0,
            maxDepth: 0,
        },
    };
    state.results.analyzed = {
        analyzed_keywords: [],
    };
    renderAll();

    try {
        const response = await postModuleStream("/expand/analyze/stream", inputData, (eventPayload) => {
            if (eventPayload?.event === "progress") {
                applyExpandStreamEvent(eventPayload, expandedStartedAt);
            }
            if (eventPayload?.event === "analysis") {
                applyAnalyzeStreamEvent(eventPayload, analyzedStartedAt);
            }
        });

        const result = response.result || {};
        result.expanded_keywords = mergeExpandedKeywords(
            state.results.expanded?.expanded_keywords || [],
            result.expanded_keywords || [],
        );
        result.analyzed_keywords = mergeAnalyzedKeywords(
            state.results.analyzed?.analyzed_keywords || [],
            result.analyzed_keywords || [],
        );

        const expandedDurationMs = Date.now() - expandedStartedAt;
        const analyzedDurationMs = Date.now() - analyzedStartedAt;
        state.stageStatus.expanded = {
            state: "success",
            message: `${result.expanded_keywords.length}건 완료`,
            startedAt: expandedStartedAt,
            finishedAt: Date.now(),
            durationMs: expandedDurationMs,
        };
        state.stageStatus.analyzed = {
            state: "success",
            message: `${result.analyzed_keywords.length}건 완료`,
            startedAt: analyzedStartedAt,
            finishedAt: Date.now(),
            durationMs: analyzedDurationMs,
        };
        state.diagnostics.expanded = {
            stageKey: "expanded",
            stageLabel: getStage("expanded").label,
            status: "success",
            endpoint: "/expand/analyze/stream",
            requestId: response.requestId,
            startedAt: startedAtLabel,
            durationMs: expandedDurationMs,
            request: sanitizeSensitiveData(inputData),
            responseSummary: buildResponseSummary("expanded", result),
            backendDebug: result.debug || null,
        };
        state.diagnostics.analyzed = {
            stageKey: "analyzed",
            stageLabel: getStage("analyzed").label,
            status: "success",
            endpoint: "/expand/analyze/stream",
            requestId: response.requestId,
            startedAt: startedAtLabel,
            durationMs: analyzedDurationMs,
            request: sanitizeSensitiveData(inputData),
            responseSummary: buildResponseSummary("analyzed", result),
            backendDebug: result.debug || null,
        };
        return result;
    } catch (error) {
        const normalizedError = normalizeError(error, {
            stageKey: "analyzed",
            endpoint: "/expand/analyze/stream",
            request: inputData,
            startedAt: startedAtLabel,
            durationMs: Date.now() - analyzedStartedAt,
        });
        state.stageStatus.expanded = {
            state: "error",
            message: normalizedError.message,
            startedAt: expandedStartedAt,
            finishedAt: Date.now(),
            durationMs: normalizedError.durationMs,
        };
        state.stageStatus.analyzed = {
            state: "error",
            message: normalizedError.message,
            startedAt: analyzedStartedAt,
            finishedAt: Date.now(),
            durationMs: normalizedError.durationMs,
        };
        state.diagnostics.expanded = {
            stageKey: "expanded",
            stageLabel: getStage("expanded").label,
            status: "error",
            endpoint: "/expand/analyze/stream",
            requestId: normalizedError.requestId,
            startedAt: startedAtLabel,
            durationMs: normalizedError.durationMs,
            request: sanitizeSensitiveData(inputData),
            error: normalizedError,
        };
        state.diagnostics.analyzed = {
            stageKey: "analyzed",
            stageLabel: getStage("analyzed").label,
            status: "error",
            endpoint: "/expand/analyze/stream",
            requestId: normalizedError.requestId,
            startedAt: startedAtLabel,
            durationMs: normalizedError.durationMs,
            request: sanitizeSensitiveData(inputData),
            error: normalizedError,
        };
        renderAll();
        throw normalizedError;
    }
}

function applyAnalyzeStreamEvent(eventPayload, startedAt) {
    if (!eventPayload || eventPayload.event !== "analysis") {
        return;
    }

    const data = eventPayload.data || {};
    const currentResult = state.results.analyzed || { analyzed_keywords: [] };
    currentResult.analyzed_keywords = mergeAnalyzedKeywords(
        currentResult.analyzed_keywords || [],
        data.items || [],
    );
    state.results.analyzed = currentResult;

    state.stageStatus.analyzed = {
        state: "running",
        message: `${currentResult.analyzed_keywords.length}건 평가 완료`,
        startedAt,
        finishedAt: null,
        durationMs: Date.now() - startedAt,
    };
    renderAll();
}

function mergeAnalyzedKeywords(existingItems, incomingItems) {
    const merged = new Map();
    [...(existingItems || []), ...(incomingItems || [])].forEach((item) => {
        if (!item || typeof item !== "object") {
            return;
        }
        const keyword = String(item.keyword || "").trim();
        if (!keyword) {
            return;
        }
        merged.set(keyword, item);
    });
    return [...merged.values()].sort((left, right) => Number(right.score || 0) - Number(left.score || 0));
}

function resolveAnalysisGrade(item) {
    const directGrade = normalizeGradeValue(item?.grade);
    if (directGrade) {
        return directGrade;
    }

    const score = Number(item?.score);
    if (!Number.isFinite(score)) {
        return "";
    }
    if (score >= 85) return "S";
    if (score >= 70) return "A";
    if (score >= 55) return "B";
    if (score >= 40) return "C";
    if (score >= 25) return "D";
    return "F";
}

function renderStageList() {
    elements.statusList.innerHTML = STAGES.map((stage) => {
        const status = state.stageStatus[stage.key];
        const icon = getStageStatusIcon(status.state);
        const tooltip = getStageTooltipText(stage, status);

        return `
            <button type="button" class="status-button ${escapeHtml(status.state)}" aria-label="${escapeHtml(stage.label)}">
                <span class="status-icon" aria-hidden="true">${icon}</span>
                <span class="status-label">${escapeHtml(stage.shortLabel || stage.label)}</span>
                <span class="status-badge">${escapeHtml(formatStageBadge(status))}</span>
                <span class="status-tooltip">${escapeHtml(tooltip)}</span>
            </button>
        `;
    }).join("");
}

function renderResults() {
    const cards = [];

    if (state.results.collected?.collected_keywords) {
        cards.push(resultCard("수집 키워드", state.results.collected.collected_keywords, renderCollectedList));
    }
    if (state.results.expanded?.expanded_keywords) {
        cards.push(
            resultCard("확장 키워드", state.results.expanded.expanded_keywords, renderExpandedList, {
                className: "expanded-result-card",
            }),
        );
    }
    if (state.results.analyzed?.analyzed_keywords) {
        cards.push(resultCard("분석 결과", state.results.analyzed.analyzed_keywords, renderAnalyzedList));
    }
    if (state.results.selected?.selected_keywords) {
        cards.push(resultCard("골든 키워드", state.results.selected.selected_keywords, renderSelectedList));
    }
    if (state.results.titled?.generated_titles) {
        cards.push(resultCard("생성된 제목", state.results.titled.generated_titles, renderTitleList));
    }

    elements.resultsGrid.innerHTML = cards.length > 0
        ? cards.join("")
        : `
            <div class="placeholder">
                상단 설정을 고른 뒤 실행 버튼을 누르면 결과가 이 영역에 표시됩니다.<br />
                키워드 발굴과 분석을 먼저 확인한 뒤, 마지막에 제목 생성으로 넘어가면 됩니다.
            </div>
        `;
}

function resultCard(title, items, renderer, options = {}) {
    return `
        <article class="result-card ${escapeHtml(options.className || "")}">
            <div class="result-head">
                <h3>${escapeHtml(title)}</h3>
                <span class="result-count">총 ${countItems(items)}건</span>
            </div>
            ${options.subtitle ? `<p class="result-subtitle">${escapeHtml(options.subtitle)}</p>` : ""}
            ${renderer(items)}
        </article>
    `;
}

function renderCollectedList(items) {
    return `<div class="keyword-list">${items.slice(0, 20).map((item) => `
        <div class="keyword-item">
            <div class="keyword-main">
                <strong>${escapeHtml(item.keyword || "-")}</strong>
                <span class="score-line">${escapeHtml(item.source || "source 없음")}</span>
            </div>
            <div class="keyword-meta">
                <span class="badge">카테고리 ${escapeHtml(item.category || "미분류")}</span>
                <span class="badge">원문 ${escapeHtml(item.raw || "-")}</span>
            </div>
            <label class="keyword-select">
                <input
                    type="checkbox"
                    data-collected-key="${escapeHtml(createCollectedIdentity(item))}"
                    ${state.selectedCollectedKeys.includes(createCollectedIdentity(item)) ? "checked" : ""}
                />
                <span>확장 입력에 사용</span>
            </label>
        </div>
    `).join("")}</div>`;
}

function renderAnalyzedList(items) {
    const rows = (items || []).slice(0, 50).map((item) => `
        <tr>
            <td><strong>${escapeHtml(item.keyword || "-")}</strong></td>
            <td>${escapeHtml(formatPriority(item.priority))}</td>
            <td>${escapeHtml(formatNumber(item.score))}</td>
            <td>${escapeHtml(formatNumber(item.metrics?.volume))}</td>
            <td>${escapeHtml(formatNumber(item.metrics?.competition))}</td>
            <td>${escapeHtml(formatNumber(item.metrics?.cpc))}</td>
            <td>${escapeHtml(formatNumber(item.metrics?.bid))}</td>
            <td>${escapeHtml(formatNumber(item.metrics?.profit))}</td>
        </tr>
    `).join("");

    return `
        <div class="expanded-table-wrap full">
            <table class="expanded-table analyzed-table">
                <thead>
                    <tr>
                        <th>키워드</th>
                        <th>등급</th>
                        <th>점수</th>
                        <th>조회량</th>
                        <th>경쟁도</th>
                        <th>CPC</th>
                        <th>입찰가</th>
                        <th>수익성</th>
                    </tr>
                </thead>
                <tbody>${rows || `<tr><td colspan="8">분석 결과가 없습니다.</td></tr>`}</tbody>
            </table>
        </div>
    `;
}

function renderSelectedList(items) {
    return `<div class="keyword-list">${items.map((item) => `
        <div class="keyword-item">
            <div class="keyword-main">
                <strong>${escapeHtml(item.keyword || "-")}</strong>
                <span class="score-line">수익 점수 ${escapeHtml(formatNumber(item.score))}</span>
            </div>
            <div class="keyword-meta">
                <span class="badge">CPC ${escapeHtml(formatNumber(item.metrics?.cpc))}</span>
                <span class="badge">입찰 ${escapeHtml(formatNumber(item.metrics?.bid))}</span>
                <span class="badge">경쟁 ${escapeHtml(formatNumber(item.metrics?.competition))}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function renderTitleList(items) {
    return `<div class="title-list">${items.map((item) => `
        <div class="title-item">
            <div class="title-keyword">
                <strong>${escapeHtml(item.keyword || "-")}</strong>
                <span class="badge">제목 ${escapeHtml(String((item.titles?.naver_home || []).length + (item.titles?.blog || []).length))}개</span>
            </div>
            <div class="title-columns">
                <div class="title-column">
                    <h4>네이버 홈형</h4>
                    <ul>${(item.titles?.naver_home || []).map((title) => `<li>${escapeHtml(title)}</li>`).join("") || "<li>결과 없음</li>"}</ul>
                </div>
                <div class="title-column">
                    <h4>블로그형</h4>
                    <ul>${(item.titles?.blog || []).map((title) => `<li>${escapeHtml(title)}</li>`).join("") || "<li>결과 없음</li>"}</ul>
                </div>
            </div>
        </div>
    `).join("")}</div>`;
}

function buildStageDetail(status) {
    if (status.state === "running") {
        return `${status.message} · ${formatElapsed(status)}`;
    }
    if (status.state === "success") {
        return `${status.message} · ${formatDuration(status.durationMs)}`;
    }
    if (status.state === "error") {
        return `${status.message} · ${formatDuration(status.durationMs)}`;
    }
    return "아직 실행하지 않았습니다.";
}

function formatStageBadge(status) {
    if (status.state === "running") return "실행중";
    if (status.state === "success") return "완료";
    if (status.state === "error") return "오류";
    return "대기";
}

function formatPriority(priority) {
    if (priority === "high") return "상";
    if (priority === "medium") return "중";
    return "하";
}

function getStageStatusIcon(stateValue) {
    if (stateValue === "running") return "◔";
    if (stateValue === "success") return "●";
    if (stateValue === "error") return "▲";
    return "○";
}

function getStageTooltipText(stage, status) {
    return `${stage.description} ${buildStageDetail(status)}`;
}

function coerceExpandLimitValue(rawValue) {
    const value = String(rawValue || "").trim();
    if (!value) {
        return null;
    }
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) {
        return null;
    }
    return Math.floor(number);
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
        "priority",
        "analysis_mode",
        "confidence",
        "score",
        "cpc_score",
        "search_volume_score",
        "rarity_score",
        "pc_searches",
        "mobile_searches",
        "volume",
        "blog_results",
        "pc_clicks",
        "mobile_clicks",
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
        item.priority || "",
        item.analysis_mode || "",
        item.confidence ?? item.metrics?.confidence ?? "",
        item.score ?? "",
        item.metrics?.cpc_score ?? item.metrics?.monetization_score ?? "",
        item.metrics?.search_volume_score ?? item.metrics?.volume_score ?? "",
        item.metrics?.rarity_score ?? "",
        item.metrics?.pc_searches ?? "",
        item.metrics?.mobile_searches ?? "",
        item.metrics?.volume ?? "",
        item.metrics?.blog_results ?? "",
        item.metrics?.pc_clicks ?? "",
        item.metrics?.mobile_clicks ?? "",
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

function downloadTitleCsv() {
    const items = state.results.titled?.generated_titles || [];
    if (!items.length) {
        addLog("내보낼 제목 결과가 없습니다.", "error");
        return;
    }

    const header = [
        "target_mode",
        "base_keyword",
        "support_keywords",
        "source_kind",
        "source_note",
        "keyword",
        "naver_home_1",
        "naver_home_2",
        "blog_1",
        "blog_2",
    ];
    const rows = items.map((item) => {
        const naverHomeTitles = Array.isArray(item.titles?.naver_home) ? item.titles.naver_home : [];
        const blogTitles = Array.isArray(item.titles?.blog) ? item.titles.blog : [];
        return [
            item.target_mode_label || item.target_mode || "",
            item.base_keyword || "",
            Array.isArray(item.support_keywords) ? item.support_keywords.join(" | ") : "",
            item.source_kind || "",
            item.source_note || "",
            item.keyword || "",
            naverHomeTitles[0] || "",
            naverHomeTitles[1] || "",
            blogTitles[0] || "",
            blogTitles[1] || "",
        ];
    });

    downloadCsvFile(header, rows, `keyword-titles-${new Date().toISOString().slice(0, 10)}.csv`);
    addLog(`제목 결과 ${items.length}건을 CSV로 내보냈습니다.`, "success");
}

function downloadCsvFile(header, rows, filename) {
    const csvText = [header, ...(rows || [])]
        .map((row) => row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(","))
        .join("\n");

    const blob = new Blob(["\ufeff" + csvText], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

function getCollectorSourcePriority(source) {
    const priorityMap = {
        naver_trend: 0,
        naver_autocomplete: 1,
        naver_related: 2,
        naver_search: 3,
        unknown: 9,
    };

    return priorityMap[source] ?? 5;
}

function formatCollectorSource(source) {
    const labelMap = {
        naver_trend: "네이버 트렌드",
        naver_autocomplete: "네이버 자동완성",
        naver_related: "네이버 연관검색",
        naver_search: "네이버 검색 결과",
        unknown: "기타",
    };

    return labelMap[source] || String(source || "기타");
}

function formatCollectorMode(mode) {
    return mode === "category" ? "카테고리 모드" : mode === "seed" ? "시드 모드" : "-";
}

function formatCollectorSourceMode(mode) {
    if (mode === "naver_trend") {
        return "네이버 트렌드";
    }
    if (mode === "preset_search") {
        return "검색 preset";
    }
    return "-";
}

function formatCollectorEffectiveSource(source) {
    const labelMap = {
        naver_trend: "네이버 트렌드",
        preset_search: "검색 preset",
        seed_keyword_sources: "시드 키워드 소스",
    };

    return labelMap[source] || "-";
}

function formatCollectorSearchArea(searchArea) {
    const normalized = String(searchArea || "");
    const labelMap = {
        autocomplete: "자동완성",
        related: "연관검색",
        blog: "블로그",
        news: "뉴스",
        seed_keyword_sources: "시드 키워드 소스",
    };

    if (normalized.startsWith("trend/")) {
        return `트렌드 ${normalized.slice(6)}`;
    }

    return labelMap[normalized] || normalized || "-";
}

function formatEnabledState(value) {
    return value ? "켜짐" : "꺼짐";
}

function formatCollectorLogStatus(status) {
    if (status === "success") {
        return "정상";
    }
    if (status === "warning") {
        return "경고";
    }
    return "빈 결과";
}

function formatCollectorNotes(notes) {
    const labelMap = {
        auth_required: "인증 쿠키 필요",
        autocomplete_error: "자동완성 오류",
        autocomplete_empty: "자동완성 결과 없음",
        related_error: "연관검색 오류",
        related_empty: "연관검색 결과 없음",
        search_error: "검색 폴백 오류",
        search_empty: "검색 결과 없음",
        topic_not_found: "주제 매핑 실패",
        trend_error: "트렌드 오류",
        trend_empty: "트렌드 결과 없음",
    };

    if (!Array.isArray(notes) || notes.length === 0) {
        return "-";
    }

    return notes.map((item) => {
        if (String(item).startsWith("date:")) {
            return `기준일 ${String(item).slice(5)}`;
        }
        if (String(item).startsWith("requested_date:")) {
            return `요청일 ${String(item).slice(15)}`;
        }
        return labelMap[item] || item;
    }).join(", ");
}

function formatCollectorWarningDetail(detail) {
    if (!detail || typeof detail !== "object") {
        return "-";
    }

    return Object.entries(detail)
        .map(([key, value]) => `${key}: ${String(value)}`)
        .join(" / ");
}

function buildExpandedLiveSubtitle() {
    const streamMeta = state.results.expanded?.stream_meta;
    if (!streamMeta) {
        return "\uc2e4\uc2dc\uac04\uc73c\ub85c \ud655\uc7a5 \ud0a4\uc6cc\ub4dc\ub97c \ubcf4\uc5ec\uc8fc\uace0 \uc788\uc2b5\ub2c8\ub2e4.";
    }

    const parts = [];
    if (streamMeta.depth) {
        parts.push(`${streamMeta.depth}\ub2e8\uacc4`);
    }
    if (streamMeta.currentKeyword) {
        parts.push(streamMeta.currentKeyword);
    }
    if (streamMeta.queueSize) {
        parts.push(`\ub300\uae30 ${streamMeta.queueSize}\uac1c`);
    }

    return parts.length > 0
        ? `${parts.join(" \u00b7 ")} \ud655\uc7a5 \uc911\uc785\ub2c8\ub2e4.`
        : "\uc2e4\uc2dc\uac04\uc73c\ub85c \ud655\uc7a5 \ud0a4\uc6cc\ub4dc\ub97c \ubcf4\uc5ec\uc8fc\uace0 \uc788\uc2b5\ub2c8\ub2e4.";
}

function renderExpandedList(items) {
    const entries = sortExpandedItems(items);
    const previewItems = entries.slice(0, 12);
    const typeSummary = summarizeExpandedTypes(entries);
    const originCount = new Set(entries.map((item) => String(item.origin || "").trim()).filter(Boolean)).size;
    const isStreaming = state.stageStatus.expanded.state === "running";
    const streamMeta = state.results.expanded?.stream_meta || null;
    const stopLabel = state.streamAbortRequested ? "중지 요청됨..." : "중지";

    return `
        <div class="expanded-board">
            ${isStreaming ? `
                <div class="expanded-live-note">
                    <div class="expanded-live-copy">
                        <strong>\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911</strong>
                        <span>${escapeHtml(buildExpandedLiveSubtitle())}</span>
                    </div>
                    <button
                        type="button"
                        class="inline-action-btn ${state.streamAbortRequested ? "requested" : ""}"
                        data-inline-action="stop_expand_stream"
                        ${state.streamAbortRequested ? "disabled" : ""}
                    >${stopLabel}</button>
                </div>
            ` : ""}
            <div class="expanded-stat-strip">
                <div class="collector-stat-card">
                    <span>\ud0a4\uc6cc\ub4dc</span>
                    <strong>${escapeHtml(String(entries.length))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>\uc6d0\ubcf8 \uc218</span>
                    <strong>${escapeHtml(String(originCount))}</strong>
                </div>
                ${typeSummary.map((item) => `
                    <div class="collector-stat-card">
                        <span>${escapeHtml(formatExpandedType(item.type))}</span>
                        <strong>${escapeHtml(String(item.count))}</strong>
                    </div>
                `).join("")}
                ${isStreaming && streamMeta ? `
                    <div class="collector-stat-card">
                        <span>\ud604\uc7ac \ub2e8\uacc4</span>
                        <strong>${escapeHtml(String(streamMeta.depth || 0))}</strong>
                    </div>
                ` : ""}
            </div>
            ${entries.length ? `
                <div class="expanded-table-wrap" data-preserve-scroll-key="expanded-preview-table">
                    <table class="expanded-table compact">
                        <thead>
                            <tr>
                                <th>\ud0a4\uc6cc\ub4dc</th>
                                <th>\uc6d0\ubcf8</th>
                                <th>\uc720\ud615</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${renderExpandedRows(previewItems)}
                        </tbody>
                    </table>
                </div>
            ` : `
                <div class="collector-empty">\ud655\uc7a5 \uc911\uc778 \ud0a4\uc6cc\ub4dc\uac00 \uc544\uc9c1 \uc5c6\uc2b5\ub2c8\ub2e4.</div>
            `}
            ${entries.length > previewItems.length ? `
                <details class="expanded-more" data-preserve-open-key="expanded-more-details">
                    <summary>\uc804\uccb4 ${escapeHtml(String(entries.length))}\uac74 \ud3bc\uccd0\ubcf4\uae30</summary>
                    <div class="expanded-table-wrap full" data-preserve-scroll-key="expanded-full-table">
                        <table class="expanded-table">
                            <thead>
                                <tr>
                                    <th>\ud0a4\uc6cc\ub4dc</th>
                                    <th>\uc6d0\ubcf8</th>
                                    <th>\uc720\ud615</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${renderExpandedRows(entries)}
                            </tbody>
                        </table>
                    </div>
                </details>
            ` : ""}
        </div>
    `;
}

function renderResults() {
    const cards = [];

    if (state.results.collected?.collected_keywords) {
        cards.push(
            resultCard("\uc218\uc9d1 \ud0a4\uc6cc\ub4dc", state.results.collected.collected_keywords, renderCollectedList, {
                limit: "all",
                subtitle: "\uc6d0\ubcf8 \ucffc\ub9ac\ubcc4\ub85c \ubb36\uc5b4\uc11c \ubc14\ub85c \uc120\ud0dd\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
                className: "collector-result-card",
            }),
        );
    }
    if (state.results.expanded?.expanded_keywords) {
        cards.push(
            resultCard("\ud655\uc7a5 \ud0a4\uc6cc\ub4dc", state.results.expanded.expanded_keywords, renderExpandedList, {
                subtitle: state.stageStatus.expanded.state === "running"
                    ? buildExpandedLiveSubtitle()
                    : "\uae30\ubcf8 12\uac74\ub9cc \uba3c\uc800 \ubcf4\uc5ec\uc8fc\uace0, \ud544\uc694\ud558\uba74 \uc804\uccb4\ub97c \ud3bc\uccd0 \ubcfc \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
                className: "expanded-result-card",
            }),
        );
    }
    if (state.results.analyzed?.analyzed_keywords) {
        cards.push(resultCard("\ubd84\uc11d \uacb0\uacfc", state.results.analyzed.analyzed_keywords, renderAnalyzedList));
    }
    if (state.results.selected?.selected_keywords) {
        cards.push(resultCard("\uace8\ub4e0 \ud0a4\uc6cc\ub4dc", state.results.selected.selected_keywords, renderSelectedList));
    }
    if (state.results.titled?.generated_titles) {
        cards.push(resultCard("\uc0dd\uc131\ub41c \uc81c\ubaa9", state.results.titled.generated_titles, renderTitleList));
    }

    elements.resultsGrid.innerHTML = cards.length > 0
        ? cards.join("")
        : `
            <div class="placeholder">
                \uc2e4\ud589 \ubc84\ud2bc\uc744 \ub204\ub974\uba74 \ub2e8\uacc4\ubcc4 \uacb0\uacfc\uc640 \uc9c4\ub2e8 \uc815\ubcf4\uac00 \uc774 \uc601\uc5ed\uc5d0 \ud45c\uc2dc\ub429\ub2c8\ub2e4.<br />
                \uc218\uc9d1 \uacb0\uacfc\ub294 \ucffc\ub9ac\ubcc4\ub85c \ubb36\uc5b4 \ubcf4\uc5ec\uc8fc\uace0, collector \uc9c4\ub2e8\uc740 \ucf54\ub4dc \ub300\uc2e0 \uc77d\uae30 \uc26c\uc6b4 \uc694\uc57d \uce74\ub4dc\ub85c \uc815\ub9ac\ub429\ub2c8\ub2e4.
            </div>
        `;
}

async function executeExpandStageStream(inputData) {
    const stageKey = "expanded";
    const stage = getStage(stageKey);
    const startedAt = Date.now();
    const startedAtLabel = new Date(startedAt).toISOString();

    state.stageStatus[stageKey] = {
        state: "running",
        message: `${stage.label} \uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911`,
        startedAt,
        finishedAt: null,
        durationMs: null,
    };
    state.results.expanded = {
        expanded_keywords: [],
        stream_meta: {
            phase: "starting",
            currentKeyword: "",
            depth: 0,
            totalResults: 0,
            queueSize: 0,
            totalOrigins: 0,
            maxDepth: 0,
        },
    };
    renderAll();

    try {
        const response = await postModuleStream("/expand/stream", inputData, (eventPayload) => {
            applyExpandStreamEvent(eventPayload, startedAt);
        });
        const result = response.result || {};
        result.expanded_keywords = mergeExpandedKeywords(
            state.results.expanded?.expanded_keywords || [],
            result.expanded_keywords || [],
        );

        const durationMs = Date.now() - startedAt;
        state.stageStatus[stageKey] = {
            state: "success",
            message: `${result.expanded_keywords.length}\uac74 \uc644\ub8cc`,
            startedAt,
            finishedAt: Date.now(),
            durationMs,
        };
        state.diagnostics[stageKey] = {
            stageKey,
            stageLabel: stage.label,
            status: "success",
            endpoint: "/expand/stream",
            requestId: response.requestId,
            startedAt: startedAtLabel,
            durationMs,
            request: sanitizeSensitiveData(inputData),
            responseSummary: buildResponseSummary(stageKey, result),
            backendDebug: result.debug || null,
        };

        return result;
    } catch (error) {
        const normalizedError = normalizeError(error, {
            stageKey,
            endpoint: "/expand/stream",
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
            endpoint: "/expand/stream",
            requestId: normalizedError.requestId,
            startedAt: startedAtLabel,
            durationMs: normalizedError.durationMs,
            request: sanitizeSensitiveData(inputData),
            error: normalizedError,
        };
        renderAll();
        throw normalizedError;
    }
}

async function postModuleStream(endpoint, inputData, onEvent) {
    const startedAt = Date.now();
    let response;

    try {
        response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ input_data: inputData }),
        });
    } catch (error) {
        const networkError = new Error("\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc694\uccad\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4. \ub124\ud2b8\uc6cc\ud06c\uc640 \uc11c\ubc84 \uc0c1\ud0dc\ub97c \ud655\uc778\ud574 \uc8fc\uc138\uc694.");
        networkError.code = "network_error";
        networkError.endpoint = endpoint;
        networkError.detail = error instanceof Error ? error.message : String(error);
        networkError.durationMs = Date.now() - startedAt;
        throw networkError;
    }

    const requestId = response.headers.get("X-Request-ID") || "";
    if (!response.ok) {
        const rawText = await response.text();
        const payload = tryParseJson(rawText);
        throw createApiError({
            endpoint,
            requestId,
            statusCode: response.status,
            payload,
            rawText,
            durationMs: Date.now() - startedAt,
        });
    }

    if (!response.body) {
        return {
            requestId,
            result: {},
            durationMs: Date.now() - startedAt,
        };
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = {};

    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

        let newlineIndex = buffer.indexOf("\n");
        while (newlineIndex !== -1) {
            const line = buffer.slice(0, newlineIndex).trim();
            buffer = buffer.slice(newlineIndex + 1);

            if (line) {
                const payload = tryParseJson(line);
                if (payload?.event === "error") {
                    throw createApiError({
                        endpoint,
                        requestId,
                        statusCode: 500,
                        payload: { error: payload.error || {} },
                        rawText: line,
                        durationMs: Date.now() - startedAt,
                    });
                }
                if (payload?.event === "completed") {
                    finalResult = payload.result || {};
                }
                if (payload && typeof onEvent === "function") {
                    onEvent(payload);
                }
            }

            newlineIndex = buffer.indexOf("\n");
        }

        if (done) {
            break;
        }
    }

    const trailingLine = buffer.trim();
    if (trailingLine) {
        const payload = tryParseJson(trailingLine);
        if (payload?.event === "error") {
            throw createApiError({
                endpoint,
                requestId,
                statusCode: 500,
                payload: { error: payload.error || {} },
                rawText: trailingLine,
                durationMs: Date.now() - startedAt,
            });
        }
        if (payload?.event === "completed") {
            finalResult = payload.result || {};
        }
        if (payload && typeof onEvent === "function") {
            onEvent(payload);
        }
    }

    return {
        requestId,
        result: finalResult,
        durationMs: Date.now() - startedAt,
    };
}

function applyExpandStreamEvent(eventPayload, startedAt) {
    if (!eventPayload || eventPayload.event !== "progress") {
        return;
    }

    const progress = eventPayload.data || {};
    const currentResult = state.results.expanded || { expanded_keywords: [] };
    const currentItems = Array.isArray(currentResult.expanded_keywords) ? currentResult.expanded_keywords : [];
    const currentMeta = currentResult.stream_meta || {};

    if (progress.type === "keyword_results" || progress.type === "depth_completed") {
        currentResult.expanded_keywords = mergeExpandedKeywords(currentItems, progress.items || []);
    }

    currentResult.stream_meta = {
        ...currentMeta,
        phase: progress.type || currentMeta.phase || "running",
        currentKeyword: progress.keyword || currentMeta.currentKeyword || "",
        depth: progress.depth || currentMeta.depth || 0,
        totalResults: progress.total_results ?? currentResult.expanded_keywords.length,
        queueSize: progress.queue_size ?? progress.next_queue_size ?? currentMeta.queueSize ?? 0,
        totalOrigins: progress.total_origins ?? currentMeta.totalOrigins ?? 0,
        maxDepth: progress.max_depth ?? currentMeta.maxDepth ?? 0,
        keywordIndex: progress.index ?? currentMeta.keywordIndex ?? 0,
        keywordTotal: progress.total ?? currentMeta.keywordTotal ?? 0,
    };
    state.results.expanded = currentResult;

    if (progress.type === "depth_completed") {
        addLog(`\ud655\uc7a5 ${progress.depth}\ub2e8\uacc4 \uc644\ub8cc: \ub204\uc801 ${currentResult.expanded_keywords.length}\uac74`, "success");
    }

    state.stageStatus.expanded = {
        state: "running",
        message: buildExpandStreamStatusMessage(currentResult.stream_meta),
        startedAt,
        finishedAt: null,
        durationMs: Date.now() - startedAt,
    };
    renderAll();
}

function buildExpandStreamStatusMessage(streamMeta) {
    if (!streamMeta) {
        return "\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911\uc785\ub2c8\ub2e4.";
    }
    if (streamMeta.currentKeyword) {
        return `${streamMeta.depth || "?"}\ub2e8\uacc4 \u00b7 ${streamMeta.currentKeyword} \ud655\uc7a5 \uc911`;
    }
    if (streamMeta.depth) {
        return `${streamMeta.depth}\ub2e8\uacc4 \ud655\uc7a5 \uc911`;
    }
    return "\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911\uc785\ub2c8\ub2e4.";
}

state.streamAbortController = null;
state.streamAbortEndpoint = "";
state.streamAbortRequested = false;
state.requestAbortController = null;
state.requestAbortStageKey = "";
state.requestAbortRequested = false;

function bindElements() {
    elements.categoryInput = document.getElementById("categoryInput");
    elements.categorySourceInput = document.getElementById("categorySourceInput");
    elements.seedInput = document.getElementById("seedInput");
    elements.trendServiceInput = document.getElementById("trendServiceInput");
    elements.trendDateInput = document.getElementById("trendDateInput");
    elements.trendBrowserInput = document.getElementById("trendBrowserInput");
    elements.trendCookieInput = document.getElementById("trendCookieInput");
    elements.trendFallbackInput = document.getElementById("trendFallbackInput");
    elements.trendSourceHelp = document.getElementById("trendSourceHelp");
    elements.launchLoginBrowserButton = document.getElementById("launchLoginBrowserButton");
    elements.loadLocalCookieButton = document.getElementById("loadLocalCookieButton");
    elements.localCookieStatus = document.getElementById("localCookieStatus");
    elements.expanderAnalysisPath = document.getElementById("expanderAnalysisPath");
    elements.optionRelated = document.getElementById("optionRelated");
    elements.optionAutocomplete = document.getElementById("optionAutocomplete");
    elements.optionBulk = document.getElementById("optionBulk");
    elements.optionDebug = document.getElementById("optionDebug");
    elements.expandInputSource = document.getElementById("expandInputSource");
    elements.expandManualInput = document.getElementById("expandManualInput");
    elements.expandOptionRelated = document.getElementById("expandOptionRelated");
    elements.expandOptionAutocomplete = document.getElementById("expandOptionAutocomplete");
    elements.expandOptionSeedFilter = document.getElementById("expandOptionSeedFilter");
    elements.expandMaxResultsInput = document.getElementById("expandMaxResultsInput");
    elements.expandLimitButtons = Array.from(document.querySelectorAll("[data-expand-limit]"));
    elements.expandSourceVisibilityBlocks = Array.from(document.querySelectorAll("[data-expand-source-visibility]"));
    elements.analyzeInputSource = document.getElementById("analyzeInputSource");
    elements.analyzeManualInput = document.getElementById("analyzeManualInput");
    elements.analyzeKeywordStatsInput = document.getElementById("analyzeKeywordStatsInput");
    elements.exportCsvButton = document.getElementById("exportCsvButton");
    elements.exportTitleCsvButton = document.getElementById("exportTitleCsvButton");
    elements.analyzeSourceVisibilityBlocks = Array.from(document.querySelectorAll("[data-analyze-source-visibility]"));
    elements.selectedCollectedCount = document.getElementById("selectedCollectedCount");
    elements.manualAnalyzeCount = document.getElementById("manualAnalyzeCount");
    elements.gradePresetButtons = Array.from(document.querySelectorAll("[data-grade-preset]"));
    elements.gradeToggleButtons = Array.from(document.querySelectorAll("[data-grade-toggle]"));
    elements.runGradeSelectButton = document.getElementById("runGradeSelectButton");
    elements.gradeSelectSummary = document.getElementById("gradeSelectSummary");
    elements.titleMode = document.getElementById("titleMode");
    elements.titleModeSingle = document.getElementById("titleModeSingle");
    elements.titleModeLongtailSelected = document.getElementById("titleModeLongtailSelected");
    elements.titleModeLongtailExploratory = document.getElementById("titleModeLongtailExploratory");
    elements.titleModeLongtailExperimental = document.getElementById("titleModeLongtailExperimental");
    elements.titleKeywordModeSummary = document.getElementById("titleKeywordModeSummary");
    elements.titlePreset = document.getElementById("titlePreset");
    elements.titlePresetDescription = document.getElementById("titlePresetDescription");
    elements.titleProvider = document.getElementById("titleProvider");
    elements.titleModel = document.getElementById("titleModel");
    elements.titleApiKey = document.getElementById("titleApiKey");
    elements.titleTemperature = document.getElementById("titleTemperature");
    elements.titleTemperatureDescription = document.getElementById("titleTemperatureDescription");
    elements.titleFallback = document.getElementById("titleFallback");
    elements.titleSystemPrompt = document.getElementById("titleSystemPrompt");
    elements.titlePromptSummary = document.getElementById("titlePromptSummary");
    elements.openTitlePromptEditorButton = document.getElementById("openTitlePromptEditorButton");
    elements.clearTitlePromptButton = document.getElementById("clearTitlePromptButton");
    elements.titleModeBadge = document.getElementById("titleModeBadge");
    elements.titleModeRadios = Array.from(document.querySelectorAll("input[name='titleModeOption']"));
    elements.titleModeVisibilityBlocks = Array.from(document.querySelectorAll("[data-title-mode-visibility]"));
    elements.statusList = document.getElementById("statusList");
    elements.controlStack = document.getElementById("controlStack");
    elements.controlLauncherColumn = document.querySelector(".control-launcher-column");
    elements.controlPrimaryBlocks = ["collect", "pipeline"]
        .map((key) => document.querySelector(`[data-control-block="${key}"]`))
        .filter(Boolean);
    elements.controlLauncherBlocks = ["expand", "analyze", "title"]
        .map((key) => document.querySelector(`[data-control-block="${key}"]`))
        .filter(Boolean);
    elements.controlBlocks = [
        ...elements.controlPrimaryBlocks,
        ...elements.controlLauncherBlocks,
    ];
    elements.controlCards = elements.controlLauncherBlocks.filter((block) => block.dataset.controlCard);
    elements.resultsRailPanel = document.getElementById("resultsRailPanel");
    elements.resultsRail = document.getElementById("resultsRail");
    elements.resultsGrid = document.getElementById("resultsGrid");
    elements.activityLog = document.getElementById("activityLog");
    elements.pipelineStatus = document.getElementById("pipelineStatus");
    elements.progressBar = document.getElementById("progressBar");
    elements.progressText = document.getElementById("progressText");
    elements.progressDetail = document.getElementById("progressDetail");
    elements.errorConsole = document.getElementById("errorConsole");
    elements.debugPanels = document.getElementById("debugPanels");
    elements.stopStreamButton = document.getElementById("stopStreamButton");
    elements.modeVisibilityBlocks = Array.from(document.querySelectorAll("[data-mode-visibility]"));
    elements.guideTabButtons = Array.from(document.querySelectorAll("[data-guide-tab]"));
    elements.guideTabPanels = Array.from(document.querySelectorAll("[data-guide-panel]"));
    elements.actionButtons = Array.from(document.querySelectorAll("button"));
}

function bindEvents() {
    document.querySelectorAll("input[name='collectorMode']").forEach((element) => {
        element.addEventListener("change", renderInputState);
    });
    document.querySelectorAll("[data-run-action='collect']").forEach((button) => {
        button.addEventListener("click", () => {
            runWithGuard(runFreshCollectFlow, "\uc218\uc9d1 \ub2e8\uacc4 \uc0c8\ub85c \uc2e4\ud589 \uc911");
        });
    });
    document.getElementById("runExpandButton").addEventListener("click", () => {
        runWithGuard(runFreshExpandFlow, "\ud655\uc7a5 \ub2e8\uacc4 \uc0c8\ub85c \uc2e4\ud589 \uc911");
    });
    document.getElementById("runAnalyzeButton").addEventListener("click", () => {
        runWithGuard(runFreshAnalyzeFlow, "\ubd84\uc11d \ub2e8\uacc4 \uc0c8\ub85c \uc2e4\ud589 \uc911");
    });
    document.getElementById("runSelectButton").addEventListener("click", () => {
        runWithGuard(runFreshSelectFlow, "\uc120\ubcc4 \ub2e8\uacc4 \uc0c8\ub85c \uc2e4\ud589 \uc911");
    });
    elements.gradePresetButtons.forEach((button) => {
        button.addEventListener("click", () => {
            applyGradePreset(button.dataset.gradePreset || "");
        });
    });
    elements.gradeToggleButtons.forEach((button) => {
        button.addEventListener("click", () => {
            toggleGradeFilter(button.dataset.profitabilityToggle || "");
        });
    });
    elements.attackabilityToggleButtons.forEach((button) => {
        button.addEventListener("click", () => {
            toggleAttackabilityFilter(button.dataset.attackabilityToggle || "");
        });
    });
    elements.runGradeSelectButton?.addEventListener("click", () => {
        const grades = getSelectedGradeFilters();
        const attackabilityGrades = getSelectedAttackabilityFilters();
        runWithGuard(
            runFreshSelectFlow,
            grades.length && attackabilityGrades.length
                ? `${buildGradeRunLabel(grades, attackabilityGrades)} \uc120\ubcc4 \uc0c8\ub85c \uc2e4\ud589 \uc911`
                : "\uc870\ud569 \uc120\ubcc4 \uc0c8\ub85c \uc2e4\ud589 \uc911",
        );
    });
    document.getElementById("runTitleButton").addEventListener("click", () => {
        runWithGuard(runFreshTitleFlow, "\uc81c\ubaa9 \uc0dd\uc131 \ub2e8\uacc4 \uc0c8\ub85c \uc2e4\ud589 \uc911");
    });
    document.getElementById("runFullButton").addEventListener("click", () => {
        runWithGuard(runFreshFullFlow, "\uc804\uccb4 \ud30c\uc774\ud504\ub77c\uc778 \uc0c8\ub85c \uc2e4\ud589 \uc911");
    });
    document.getElementById("resetButton").addEventListener("click", resetAll);
    document.getElementById("clearDebugButton").addEventListener("click", clearDiagnostics);
    elements.stopStreamButton?.addEventListener("click", cancelActiveStream);
    elements.resultsGrid.addEventListener("click", handleResultsGridClick);
    elements.resultsGrid.addEventListener("change", handleResultsGridChange);
    elements.expandManualInput.addEventListener("input", renderInputState);
    elements.expandInputSource.addEventListener("change", renderInputState);
    elements.analyzeManualInput.addEventListener("input", renderInputState);
    elements.analyzeInputSource.addEventListener("change", renderInputState);
    elements.analyzeKeywordStatsInput?.addEventListener("input", renderInputState);
    elements.expandMaxResultsInput?.addEventListener("input", () => {
        elements.expandLimitButtons.forEach((button) => button.classList.remove("active"));
    });
    [
        elements.categorySourceInput,
        elements.trendServiceInput,
        elements.trendDateInput,
        elements.trendBrowserInput,
        elements.trendCookieInput,
        elements.trendFallbackInput,
    ].forEach((element) => {
        element?.addEventListener("input", handleTrendSettingsChange);
        element?.addEventListener("change", handleTrendSettingsChange);
    });
    elements.loadLocalCookieButton?.addEventListener("click", () => {
        runWithGuard(importLocalNaverCookie, "\ub85c\uceec \ub124\uc774\ubc84 \uc138\uc158 \ubd88\ub7ec\uc624\ub294 \uc911");
    });
    elements.launchLoginBrowserButton?.addEventListener("click", () => {
        runWithGuard(openDedicatedLoginBrowser, "\uc804\uc6a9 \ub85c\uadf8\uc778 \ube0c\ub77c\uc6b0\uc800 \uc5ec\ub294 \uc911");
    });
    [
        elements.titleMode,
        elements.titleModeSingle,
        elements.titleModeLongtailSelected,
        elements.titleModeLongtailExploratory,
        elements.titleModeLongtailExperimental,
        elements.titlePreset,
        elements.titleProvider,
        elements.titleModel,
        elements.titleApiKey,
        elements.titleTemperature,
        elements.titleFallback,
    ].forEach((element) => {
        element?.addEventListener("input", handleTitleSettingsChange);
        element?.addEventListener("change", handleTitleSettingsChange);
    });
    elements.titleModeRadios.forEach((radio) => {
        radio.addEventListener("change", handleTitleSettingsChange);
        radio.addEventListener("input", handleTitleSettingsChange);
    });
    elements.openTitlePromptEditorButton?.addEventListener("click", openTitlePromptEditor);
    elements.clearTitlePromptButton?.addEventListener("click", clearTitleSystemPrompt);
    document.querySelectorAll("[data-preset]").forEach((button) => {
        button.addEventListener("click", () => applyPreset(button.dataset.preset || "finance"));
    });
    elements.expandLimitButtons.forEach((button) => {
        button.addEventListener("click", () => setExpandLimitPreset(button.dataset.expandLimit || "1000"));
    });
    elements.exportCsvButton?.addEventListener("click", downloadAnalyzedCsv);
    elements.exportTitleCsvButton?.addEventListener("click", downloadTitleCsv);
    setExpandLimitPreset(elements.expandMaxResultsInput?.value || "1000");
}

function buildCollectInput() {
    const trendSettings = getTrendSettingsFormState();
    const mode = getCollectorMode();
    const categoryMode = mode === "category";

    return {
        mode,
        category: categoryMode ? elements.categoryInput.value.trim() : "",
        category_source: categoryMode ? (elements.categorySourceInput.value.trim() || "naver_trend") : "preset_search",
        seed_input: categoryMode ? "" : elements.seedInput.value.trim(),
        options: {
            collect_related: elements.optionRelated.checked,
            collect_autocomplete: elements.optionAutocomplete.checked,
            collect_bulk: categoryMode ? elements.optionBulk.checked : false,
        },
        trend_options: {
            service: trendSettings.service,
            content_type: "text",
            date: trendSettings.date,
            auth_cookie: categoryMode ? trendSettings.auth_cookie : "",
            fallback_to_preset_search: categoryMode ? trendSettings.fallback_to_preset_search : false,
        },
        debug: elements.optionDebug.checked,
    };
}

function buildExpandInput() {
    const source = elements.expandInputSource.value;
    const category = getCollectorMode() === "category" ? elements.categoryInput.value.trim() : "";
    const expandOptions = {
        enable_related: elements.expandOptionRelated?.checked ?? true,
        enable_autocomplete: elements.expandOptionAutocomplete?.checked ?? true,
        enable_seed_filter: elements.expandOptionSeedFilter?.checked ?? true,
        max_results: coerceExpandLimitValue(elements.expandMaxResultsInput?.value),
    };

    if (source === "manual_text") {
        const keywordsText = elements.expandManualInput.value.trim();
        const keywords = parseKeywordText(keywordsText);
        if (keywords.length === 0) {
            throw new Error("\ud655\uc7a5\ud560 \ud0a4\uc6cc\ub4dc\ub97c \uc9c1\uc811 \uc785\ub825\ud574 \uc8fc\uc138\uc694.");
        }

        return withAnalyzeKeywordStats({
            keywords_text: keywordsText,
            category,
            source: "manual_input",
            expand_options: expandOptions,
        });
    }

    const collectedKeywords = source === "collector_selected"
        ? getSelectedCollectedItems()
        : state.results.collected?.collected_keywords || [];

    if (collectedKeywords.length === 0) {
        throw new Error(
            source === "collector_selected"
                ? "\ud655\uc7a5\uc5d0 \uc0ac\uc6a9\ud560 \uc218\uc9d1 \ud0a4\uc6cc\ub4dc\ub97c \ucd5c\uc18c 1\uac1c \uc120\ud0dd\ud574 \uc8fc\uc138\uc694."
                : "\uc218\uc9d1 \uacb0\uacfc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4. \uba3c\uc800 \uc218\uc9d1\uc744 \uc2e4\ud589\ud574 \uc8fc\uc138\uc694.",
        );
    }

    return withAnalyzeKeywordStats({
        collected_keywords: collectedKeywords,
        category,
        expand_options: expandOptions,
    });
}

function renderInputState() {
    const mode = getCollectorMode();
    const categoryMode = mode === "category";
    const selectedCount = getSelectedCollectedItems().length;
    const expandCount = parseKeywordText(elements.expandManualInput?.value || "").length;
    const analyzeCount = parseKeywordText(elements.analyzeManualInput?.value || "").length;
    const expandUsesManual = elements.expandInputSource?.value === "manual_text";
    const analyzeUsesManual = elements.analyzeInputSource?.value === "manual_text";
    const usesTrendSource = categoryMode && elements.categorySourceInput?.value === "naver_trend";

    elements.modeVisibilityBlocks.forEach((element) => {
        element.hidden = element.dataset.modeVisibility !== mode;
    });

    if (elements.selectedCollectedCount) {
        elements.selectedCollectedCount.textContent = expandUsesManual
            ? `\uc9c1\uc811 \uc785\ub825 ${expandCount}\uac74`
            : `\uc120\ud0dd ${selectedCount}\uac74`;
    }
    if (elements.manualAnalyzeCount) {
        elements.manualAnalyzeCount.textContent = `\uc9c1\uc811 \uc785\ub825 ${analyzeCount}\uac74`;
    }
    if (elements.expandManualInput) {
        elements.expandManualInput.disabled = !expandUsesManual;
    }
    if (elements.analyzeManualInput) {
        elements.analyzeManualInput.disabled = !analyzeUsesManual;
    }
    if (elements.seedInput) {
        elements.seedInput.disabled = categoryMode;
        elements.seedInput.title = categoryMode ? "\uce74\ud14c\uace0\ub9ac \ubaa8\ub4dc\uc5d0\uc11c\ub294 \uc2dc\ub4dc \ud0a4\uc6cc\ub4dc\ub97c \uc0ac\uc6a9\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4." : "";
    }
    if (elements.categoryInput) {
        elements.categoryInput.disabled = !categoryMode;
        elements.categoryInput.title = categoryMode ? "" : "\uc2dc\ub4dc \ubaa8\ub4dc\uc5d0\uc11c\ub294 \uce74\ud14c\uace0\ub9ac\ub97c \uc0ac\uc6a9\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.";
    }
    if (elements.categorySourceInput) {
        elements.categorySourceInput.disabled = !categoryMode;
    }
    if (elements.optionRelated) {
        elements.optionRelated.title = usesTrendSource ? "\ud2b8\ub80c\ub4dc \uc2e4\ud328 \ud6c4 preset fallback\uc5d0\uc11c\ub9cc \uc801\uc6a9\ub429\ub2c8\ub2e4." : "";
    }
    if (elements.optionAutocomplete) {
        elements.optionAutocomplete.title = usesTrendSource ? "\ud2b8\ub80c\ub4dc \uc2e4\ud328 \ud6c4 preset fallback\uc5d0\uc11c\ub9cc \uc801\uc6a9\ub429\ub2c8\ub2e4." : "";
    }
    if (elements.optionBulk) {
        elements.optionBulk.title = usesTrendSource ? "\ud2b8\ub80c\ub4dc \uc2e4\ud328 \ud6c4 preset fallback\uc5d0\uc11c\ub9cc \uc801\uc6a9\ub429\ub2c8\ub2e4." : "";
    }
    if (elements.stopStreamButton) {
        elements.stopStreamButton.title = state.streamAbortController
            ? "\uc2e4\uc2dc\uac04 \ud655\uc7a5/\ubd84\uc11d \uc2a4\ud2b8\ub9bc\uc744 \uc911\uc9c0\ud569\ub2c8\ub2e4."
            : "";
    }

    renderTrendSettingsState();
}

function renderTrendSettingsState() {
    const categoryMode = getCollectorMode() === "category";
    const usesTrendSource = categoryMode && elements.categorySourceInput.value === "naver_trend";

    elements.trendServiceInput.disabled = !usesTrendSource;
    elements.trendDateInput.disabled = !usesTrendSource;
    elements.trendBrowserInput.disabled = !usesTrendSource;
    elements.trendCookieInput.disabled = !usesTrendSource;
    elements.trendFallbackInput.disabled = !categoryMode;
    elements.launchLoginBrowserButton.disabled = !usesTrendSource;
    if (elements.loadLocalCookieButton) {
        elements.loadLocalCookieButton.disabled = !usesTrendSource;
    }

    if (elements.trendSourceHelp) {
        if (usesTrendSource) {
            const hasCookie = Boolean(elements.trendCookieInput.value.trim());
            const service = elements.trendServiceInput.value || "naver_blog";
            const browser = elements.trendBrowserInput.value || "auto";
            const fallbackLabel = elements.trendFallbackInput.checked ? "\ucf1c\uc9d0" : "\uaebc\uc9d0";
            elements.trendSourceHelp.textContent = hasCookie
                ? `\ud604\uc7ac Creator Advisor ${service} \ud2b8\ub80c\ub4dc\ub97c \uc9c1\uc811 \uc870\ud68c\ud569\ub2c8\ub2e4. \ub85c\uceec \ube0c\ub77c\uc6b0\uc800\ub294 ${browser}, fallback\uc740 ${fallbackLabel} \uc0c1\ud0dc\uc785\ub2c8\ub2e4.`
                : `\ud604\uc7ac Creator Advisor ${service} \uc138\uc158\uc774 \ube44\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. '\uc804\uc6a9 \ub85c\uadf8\uc778 \ube0c\ub77c\uc6b0\uc800 \uc5f4\uae30'\ub85c \ub85c\uceec \uc138\uc158\uc744 \uc900\ube44\ud574 \uc8fc\uc138\uc694.`;
        } else {
            elements.trendSourceHelp.textContent = "\uce74\ud14c\uace0\ub9ac \uc218\uc9d1 \uc18c\uc2a4\uac00 preset fallback\uc774\uba74 \uae30\uc874 \uacf5\uac1c \uac80\uc0c9 \uacbd\ub85c\ub85c \ud0a4\uc6cc\ub4dc\ub97c \uc218\uc9d1\ud569\ub2c8\ub2e4.";
        }
    }

    if (elements.localCookieStatus && !elements.localCookieStatus.dataset.locked) {
        elements.localCookieStatus.textContent = elements.trendCookieInput.value.trim()
            ? "\ube0c\ub77c\uc6b0\uc800\uc5d0\uc11c \ubd88\ub7ec\uc624\uac70\ub098 \uc9c1\uc811 \ubd99\uc5ec\ub123\uc744 \ub85c\uceec \uc138\uc158\uc774 \uc900\ube44\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4."
            : "\uc544\uc9c1 \ubd88\ub7ec\uc628 \ub85c\uceec \uc138\uc158\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.";
    }
}

function syncBusyButtons() {
    elements.actionButtons.forEach((button) => {
        if (button === elements.stopStreamButton) {
            button.disabled = !(state.isBusy && state.streamAbortController && !state.streamAbortRequested);
            return;
        }
        button.disabled = state.isBusy;
    });
}

async function runWithGuard(task, runningMessage) {
    if (state.isBusy) {
        addLog("\uc774\ubbf8 \ub2e4\ub978 \uc791\uc5c5\uc744 \uc2e4\ud589 \uc911\uc785\ub2c8\ub2e4. \ud604\uc7ac \ub2e8\uacc4\uac00 \ub05d\ub09c \ub4a4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.", "error");
        return;
    }

    state.isBusy = true;
    state.lastError = null;
    setGlobalStatus(runningMessage, "running");
    syncBusyButtons();
    renderAll();

    try {
        await task();
        setGlobalStatus("\uc2e4\ud589 \uc644\ub8cc", "success");
    } catch (error) {
        if (isAbortLikeError(error)) {
            state.lastError = null;
            setGlobalStatus("\uc911\uc9c0\ub428", "idle");
            addLog(error.message || "\uc2e4\uc2dc\uac04 \uc791\uc5c5\uc744 \uc911\uc9c0\ud588\uc2b5\ub2c8\ub2e4.", "info");
        } else {
            const normalizedError = normalizeError(error);
            state.lastError = normalizedError;
            setGlobalStatus("\uc624\ub958 \ubc1c\uc0dd", "error");
            addLog(buildErrorHeadline(normalizedError), "error");
        }
    } finally {
        state.isBusy = false;
        syncBusyButtons();
        renderAll();
    }
}

function beginStreamRequest(endpoint) {
    const controller = new AbortController();
    state.streamAbortController = controller;
    state.streamAbortEndpoint = endpoint;
    state.streamAbortRequested = false;
    syncBusyButtons();
    renderAll();
    return controller;
}

function completeStreamRequest(controller) {
    if (state.streamAbortController === controller) {
        state.streamAbortController = null;
        state.streamAbortEndpoint = "";
        state.streamAbortRequested = false;
    }
    syncBusyButtons();
}

function cancelActiveStream() {
    if (state.requestAbortController) {
        if (state.requestAbortRequested) {
            return;
        }
        state.requestAbortRequested = true;
        addLog("현재 작업 중지를 요청했습니다. 지금까지 받은 결과는 유지됩니다.", "info");
        updateStopButtonState();
        state.requestAbortController.abort("user_cancelled");
        renderAll();
        return;
    }

    if (!state.streamAbortController || state.streamAbortRequested) {
        return;
    }
    state.streamAbortRequested = true;
    addLog("\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911\uc9c0\ub97c \uc694\uccad\ud588\uc2b5\ub2c8\ub2e4.", "info");
    state.streamAbortController.abort("user_cancelled");
    syncBusyButtons();
    renderAll();
}

async function executeExpandStageStream(inputData) {
    const stageKey = "expanded";
    const stage = getStage(stageKey);
    const startedAt = Date.now();
    const startedAtLabel = new Date(startedAt).toISOString();
    const streamController = beginStreamRequest("/expand/stream");

    setActiveResultView(stageKey);
    state.stageStatus[stageKey] = {
        state: "running",
        message: `${stage.label} \uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911`,
        startedAt,
        finishedAt: null,
        durationMs: null,
    };
    state.results.expanded = {
        expanded_keywords: [],
        stream_meta: {
            phase: "starting",
            currentKeyword: "",
            depth: 0,
            totalResults: 0,
            queueSize: 0,
            totalOrigins: 0,
            maxDepth: 0,
        },
    };
    renderAll();

    try {
        const response = await postModuleStream(
            "/expand/stream",
            inputData,
            (eventPayload) => {
                applyExpandStreamEvent(eventPayload, startedAt);
            },
            { signal: streamController.signal },
        );
        const result = response.result || {};
        result.expanded_keywords = mergeExpandedKeywords(
            state.results.expanded?.expanded_keywords || [],
            result.expanded_keywords || [],
        );

        const durationMs = Date.now() - startedAt;
        state.stageStatus[stageKey] = {
            state: "success",
            message: `${result.expanded_keywords.length}\uac74 \uc644\ub8cc`,
            startedAt,
            finishedAt: Date.now(),
            durationMs,
        };
        state.diagnostics[stageKey] = {
            stageKey,
            stageLabel: stage.label,
            status: "success",
            endpoint: "/expand/stream",
            requestId: response.requestId,
            startedAt: startedAtLabel,
            durationMs,
            request: sanitizeSensitiveData(inputData),
            responseSummary: buildResponseSummary(stageKey, result),
            backendDebug: result.debug || null,
        };

        return result;
    } catch (error) {
        const durationMs = Date.now() - startedAt;
        if (isAbortLikeError(error)) {
            state.stageStatus[stageKey] = {
                state: "cancelled",
                message: "\uc0ac\uc6a9\uc790 \uc911\uc9c0",
                startedAt,
                finishedAt: Date.now(),
                durationMs,
            };
            state.diagnostics[stageKey] = {
                stageKey,
                stageLabel: stage.label,
                status: "cancelled",
                endpoint: "/expand/stream",
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
            endpoint: "/expand/stream",
            request: inputData,
            startedAt: startedAtLabel,
            durationMs,
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
            endpoint: "/expand/stream",
            requestId: normalizedError.requestId,
            startedAt: startedAtLabel,
            durationMs: normalizedError.durationMs,
            request: sanitizeSensitiveData(inputData),
            error: normalizedError,
        };
        renderAll();
        throw normalizedError;
    } finally {
        completeStreamRequest(streamController);
    }
}

async function executeExpandAnalyzeStageStream(inputData) {
    const expandedStartedAt = Date.now();
    const analyzedStartedAt = expandedStartedAt;
    const startedAtLabel = new Date(expandedStartedAt).toISOString();
    const streamController = beginStreamRequest("/expand/analyze/stream");

    setActiveResultView("analyzed");
    state.stageStatus.expanded = {
        state: "running",
        message: "\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911",
        startedAt: expandedStartedAt,
        finishedAt: null,
        durationMs: null,
    };
    state.stageStatus.analyzed = {
        state: "running",
        message: "\uc2e4\uc2dc\uac04 \ubd84\uc11d \uc911",
        startedAt: analyzedStartedAt,
        finishedAt: null,
        durationMs: null,
    };
    state.results.expanded = {
        expanded_keywords: [],
        stream_meta: {
            phase: "starting",
            currentKeyword: "",
            depth: 0,
            totalResults: 0,
            queueSize: 0,
            totalOrigins: 0,
            maxDepth: 0,
        },
    };
    state.results.analyzed = {
        analyzed_keywords: [],
    };
    renderAll();

    try {
        const response = await postModuleStream(
            "/expand/analyze/stream",
            inputData,
            (eventPayload) => {
                if (eventPayload?.event === "progress") {
                    applyExpandStreamEvent(eventPayload, expandedStartedAt);
                }
                if (eventPayload?.event === "analysis") {
                    applyAnalyzeStreamEvent(eventPayload, analyzedStartedAt);
                }
            },
            { signal: streamController.signal },
        );

        const result = response.result || {};
        result.expanded_keywords = mergeExpandedKeywords(
            state.results.expanded?.expanded_keywords || [],
            result.expanded_keywords || [],
        );
        result.analyzed_keywords = mergeAnalyzedKeywords(
            state.results.analyzed?.analyzed_keywords || [],
            result.analyzed_keywords || [],
        );

        const expandedDurationMs = Date.now() - expandedStartedAt;
        const analyzedDurationMs = Date.now() - analyzedStartedAt;
        state.stageStatus.expanded = {
            state: "success",
            message: `${result.expanded_keywords.length}\uac74 \uc644\ub8cc`,
            startedAt: expandedStartedAt,
            finishedAt: Date.now(),
            durationMs: expandedDurationMs,
        };
        state.stageStatus.analyzed = {
            state: "success",
            message: `${result.analyzed_keywords.length}\uac74 \uc644\ub8cc`,
            startedAt: analyzedStartedAt,
            finishedAt: Date.now(),
            durationMs: analyzedDurationMs,
        };
        state.diagnostics.expanded = {
            stageKey: "expanded",
            stageLabel: getStage("expanded").label,
            status: "success",
            endpoint: "/expand/analyze/stream",
            requestId: response.requestId,
            startedAt: startedAtLabel,
            durationMs: expandedDurationMs,
            request: sanitizeSensitiveData(inputData),
            responseSummary: buildResponseSummary("expanded", result),
            backendDebug: result.debug || null,
        };
        state.diagnostics.analyzed = {
            stageKey: "analyzed",
            stageLabel: getStage("analyzed").label,
            status: "success",
            endpoint: "/expand/analyze/stream",
            requestId: response.requestId,
            startedAt: startedAtLabel,
            durationMs: analyzedDurationMs,
            request: sanitizeSensitiveData(inputData),
            responseSummary: buildResponseSummary("analyzed", result),
            backendDebug: result.debug || null,
        };
        return result;
    } catch (error) {
        const durationMs = Date.now() - analyzedStartedAt;
        if (isAbortLikeError(error)) {
            const finishedAt = Date.now();
            state.stageStatus.expanded = {
                state: "cancelled",
                message: "\uc0ac\uc6a9\uc790 \uc911\uc9c0",
                startedAt: expandedStartedAt,
                finishedAt,
                durationMs,
            };
            state.stageStatus.analyzed = {
                state: "cancelled",
                message: "\uc0ac\uc6a9\uc790 \uc911\uc9c0",
                startedAt: analyzedStartedAt,
                finishedAt,
                durationMs,
            };
            state.diagnostics.expanded = {
                stageKey: "expanded",
                stageLabel: getStage("expanded").label,
                status: "cancelled",
                endpoint: "/expand/analyze/stream",
                requestId: "",
                startedAt: startedAtLabel,
                durationMs,
                request: sanitizeSensitiveData(inputData),
            };
            state.diagnostics.analyzed = {
                stageKey: "analyzed",
                stageLabel: getStage("analyzed").label,
                status: "cancelled",
                endpoint: "/expand/analyze/stream",
                requestId: "",
                startedAt: startedAtLabel,
                durationMs,
                request: sanitizeSensitiveData(inputData),
            };
            renderAll();
            throw error;
        }

        const normalizedError = normalizeError(error, {
            stageKey: "analyzed",
            endpoint: "/expand/analyze/stream",
            request: inputData,
            startedAt: startedAtLabel,
            durationMs,
        });
        state.stageStatus.expanded = {
            state: "error",
            message: normalizedError.message,
            startedAt: expandedStartedAt,
            finishedAt: Date.now(),
            durationMs: normalizedError.durationMs,
        };
        state.stageStatus.analyzed = {
            state: "error",
            message: normalizedError.message,
            startedAt: analyzedStartedAt,
            finishedAt: Date.now(),
            durationMs: normalizedError.durationMs,
        };
        state.diagnostics.expanded = {
            stageKey: "expanded",
            stageLabel: getStage("expanded").label,
            status: "error",
            endpoint: "/expand/analyze/stream",
            requestId: normalizedError.requestId,
            startedAt: startedAtLabel,
            durationMs: normalizedError.durationMs,
            request: sanitizeSensitiveData(inputData),
            error: normalizedError,
        };
        state.diagnostics.analyzed = {
            stageKey: "analyzed",
            stageLabel: getStage("analyzed").label,
            status: "error",
            endpoint: "/expand/analyze/stream",
            requestId: normalizedError.requestId,
            startedAt: startedAtLabel,
            durationMs: normalizedError.durationMs,
            request: sanitizeSensitiveData(inputData),
            error: normalizedError,
        };
        renderAll();
        throw normalizedError;
    } finally {
        completeStreamRequest(streamController);
    }
}

async function postModuleStream(endpoint, inputData, onEvent, options = {}) {
    const startedAt = Date.now();
    const signal = options?.signal;
    let response;

    try {
        response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ input_data: inputData }),
            signal,
        });
    } catch (error) {
        if (isAbortLikeError(error)) {
            throw createStreamAbortError(endpoint, startedAt);
        }
        const networkError = new Error("\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc694\uccad\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4. \ub124\ud2b8\uc6cc\ud06c\uc640 \uc11c\ubc84 \uc0c1\ud0dc\ub97c \ud655\uc778\ud574 \uc8fc\uc138\uc694.");
        networkError.code = "network_error";
        networkError.endpoint = endpoint;
        networkError.detail = error instanceof Error ? error.message : String(error);
        networkError.durationMs = Date.now() - startedAt;
        throw networkError;
    }

    const requestId = response.headers.get("X-Request-ID") || "";
    if (!response.ok) {
        const rawText = await response.text();
        const payload = tryParseJson(rawText);
        throw createApiError({
            endpoint,
            requestId,
            statusCode: response.status,
            payload,
            rawText,
            durationMs: Date.now() - startedAt,
        });
    }

    if (!response.body) {
        return {
            requestId,
            result: {},
            durationMs: Date.now() - startedAt,
        };
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = {};

    try {
        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

            let newlineIndex = buffer.indexOf("\n");
            while (newlineIndex !== -1) {
                const line = buffer.slice(0, newlineIndex).trim();
                buffer = buffer.slice(newlineIndex + 1);

                if (line) {
                    const payload = tryParseJson(line);
                    if (payload?.event === "error") {
                        throw createApiError({
                            endpoint,
                            requestId,
                            statusCode: 500,
                            payload: { error: payload.error || {} },
                            rawText: line,
                            durationMs: Date.now() - startedAt,
                        });
                    }
                    if (payload?.event === "completed") {
                        finalResult = payload.result || {};
                    }
                    if (payload && typeof onEvent === "function") {
                        onEvent(payload);
                    }
                }

                newlineIndex = buffer.indexOf("\n");
            }

            if (done) {
                break;
            }
        }
    } catch (error) {
        if (isAbortLikeError(error)) {
            throw createStreamAbortError(endpoint, startedAt);
        }
        const streamReadError = error instanceof Error
            ? error
            : new Error("실시간 응답을 읽는 중 오류가 발생했습니다.");
        streamReadError.code = streamReadError.code || "stream_read_error";
        streamReadError.endpoint = streamReadError.endpoint || endpoint;
        streamReadError.requestId = streamReadError.requestId || requestId;
        streamReadError.statusCode = streamReadError.statusCode || response?.status || 0;
        streamReadError.detail = streamReadError.detail || (error instanceof Error ? error.message : String(error));
        streamReadError.durationMs = streamReadError.durationMs || (Date.now() - startedAt);
        throw streamReadError;
    } finally {
        try {
            reader.releaseLock();
        } catch (error) {
            // noop
        }
    }

    const trailingLine = buffer.trim();
    if (trailingLine) {
        const payload = tryParseJson(trailingLine);
        if (payload?.event === "error") {
            throw createApiError({
                endpoint,
                requestId,
                statusCode: 500,
                payload: { error: payload.error || {} },
                rawText: trailingLine,
                durationMs: Date.now() - startedAt,
            });
        }
        if (payload?.event === "completed") {
            finalResult = payload.result || {};
        }
        if (payload && typeof onEvent === "function") {
            onEvent(payload);
        }
    }

    return {
        requestId,
        result: finalResult,
        durationMs: Date.now() - startedAt,
    };
}

function buildStageDetail(status) {
    if (status.state === "running") {
        return `${status.message} \u00b7 ${formatElapsed(status)}`;
    }
    if (status.state === "success" || status.state === "error" || status.state === "cancelled") {
        return `${status.message} \u00b7 ${formatDuration(status.durationMs)}`;
    }
    return "\uc544\uc9c1 \uc2e4\ud589\ud558\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4.";
}

function formatStageBadge(status) {
    if (status.state === "running") return "\uc2e4\ud589\uc911";
    if (status.state === "success") return "\uc644\ub8cc";
    if (status.state === "error") return "\uc624\ub958";
    if (status.state === "cancelled") return "\uc911\uc9c0\ub428";
    return "\ub300\uae30";
}

function getStageStatusIcon(stateValue) {
    if (stateValue === "running") return "\u25d4";
    if (stateValue === "success") return "\u25cf";
    if (stateValue === "error") return "\u25b2";
    if (stateValue === "cancelled") return "\u25a0";
    return "\u25cb";
}

function isAbortLikeError(error) {
    return error?.name === "AbortError"
        || error?.code === "abort_error"
        || error?.code === "stream_aborted"
        || error?.code === "cancelled";
}

function createStreamAbortError(endpoint, startedAt) {
    const error = new Error("\uc2e4\uc2dc\uac04 \ud655\uc7a5\uc744 \uc911\uc9c0\ud588\uc2b5\ub2c8\ub2e4.");
    error.name = "AbortError";
    error.code = "abort_error";
    error.endpoint = endpoint;
    error.durationMs = Date.now() - startedAt;
    return error;
}

function createRequestAbortError(endpoint, startedAt) {
    const error = new Error("작업을 중지했습니다.");
    error.name = "AbortError";
    error.code = "abort_error";
    error.endpoint = endpoint;
    error.durationMs = Date.now() - startedAt;
    return error;
}

function setBlocksVisibility(blocks, activeValue, datasetKey) {
    (blocks || []).forEach((block) => {
        const shouldShow = block?.dataset?.[datasetKey] === activeValue;
        block.hidden = !shouldShow;
        block.style.display = shouldShow ? "" : "none";
    });
}

function syncTitleModeInputFromRadios() {
    const selectedMode = (elements.titleModeRadios || []).find((radio) => radio.checked)?.value
        || elements.titleMode?.value
        || "template";
    if (elements.titleMode) {
        elements.titleMode.value = selectedMode;
    }
    return selectedMode;
}

function applyTitleModeSelection(mode) {
    const normalized = mode === "ai" ? "ai" : "template";
    if (elements.titleMode) {
        elements.titleMode.value = normalized;
    }
    (elements.titleModeRadios || []).forEach((radio) => {
        radio.checked = radio.value === normalized;
    });
    return normalized;
}

function loadTitleSettings() {
    const defaults = {
        mode: "template",
        provider: "openai",
        model: TITLE_PROVIDER_DEFAULT_MODELS.openai,
        api_key: "",
        temperature: "0.7",
        fallback_to_template: true,
    };

    const storedSettings = readLocalStorageJson(TITLE_SETTINGS_STORAGE_KEY);
    const settings = { ...defaults, ...(storedSettings || {}) };

    applyTitleModeSelection(settings.mode);
    elements.titleProvider.value = settings.provider;
    elements.titleModel.value = settings.model;
    elements.titleApiKey.value = settings.api_key;
    elements.titleTemperature.value = String(settings.temperature || "0.7");
    elements.titleFallback.checked = Boolean(settings.fallback_to_template);

    renderTitleSettingsState();
}

function handleTitleSettingsChange(event) {
    if (event?.target?.matches?.("input[name='titleModeOption']")) {
        syncTitleModeInputFromRadios();
    }

    if (event?.target === elements.titleProvider && !elements.titleModel.value.trim()) {
        elements.titleModel.value = TITLE_PROVIDER_DEFAULT_MODELS[elements.titleProvider.value] || "gpt-4o-mini";
    }

    if (event?.target === elements.titleProvider) {
        const providerModel = TITLE_PROVIDER_DEFAULT_MODELS[elements.titleProvider.value] || "gpt-4o-mini";
        const currentModel = elements.titleModel.value.trim();
        const knownModels = Object.values(TITLE_PROVIDER_DEFAULT_MODELS);
        if (!currentModel || knownModels.includes(currentModel)) {
            elements.titleModel.value = providerModel;
        }
    }

    persistTitleSettings();
    renderTitleSettingsState();
}

function renderTitleSettingsState() {
    const mode = syncTitleModeInputFromRadios();
    const isAiMode = mode === "ai";

    elements.titleModeVisibilityBlocks.forEach((block) => {
        block.hidden = block.dataset.titleModeVisibility !== mode;
    });

    elements.titleProvider.disabled = !isAiMode;
    elements.titleModel.disabled = !isAiMode;
    elements.titleApiKey.disabled = !isAiMode;
    elements.titleTemperature.disabled = !isAiMode;
    elements.titleFallback.disabled = !isAiMode;
    elements.titleModeBadge.textContent = isAiMode ? `ai:${elements.titleProvider.value}` : "template";
}

function resetAll() {
    clearPipelineResults({
        preserveGlobalStatus: false,
        preserveSelectionFilters: false,
        announce: true,
        message: "결과와 디버그 정보를 초기화했습니다.",
    });
    return;
    state.results = createEmptyResults();
    state.stageStatus = createInitialStageStatus();
    state.diagnostics = createEmptyDiagnostics();
    state.selectedCollectedKeys = [];
    state.selectGradeFilters = [...PROFITABILITY_ORDER];
    state.selectAttackabilityFilters = [...ATTACKABILITY_ORDER];
    state.gradeSelectionTouched = false;
    state.activeResultView = "";
    state.lastError = null;
    state.analyzedFilters = createDefaultAnalyzedFilters();
    state.streamAbortController = null;
    state.streamAbortEndpoint = "";
    state.streamAbortRequested = false;
    state.requestAbortController = null;
    state.requestAbortStageKey = "";
    state.requestAbortEndpoint = "";
    state.requestAbortRequested = false;
    setGlobalStatus("대기 중", "idle");
    renderAll();
    addLog("결과와 디버그 정보를 초기화했습니다.");
}

function renderInputState() {
    const mode = getCollectorMode();
    const categoryMode = mode === "category";
    const selectedCount = getSelectedCollectedItems().length;
    const expandCount = parseKeywordText(elements.expandManualInput?.value || "").length;
    const analyzeCount = parseKeywordText(elements.analyzeManualInput?.value || "").length;
    const expandSource = elements.expandInputSource?.value || "collector_all";
    const analyzeSource = elements.analyzeInputSource?.value || "expanded_results";
    const expandUsesManual = expandSource === "manual_text";
    const analyzeUsesManual = analyzeSource === "manual_text";
    const usesTrendSource = categoryMode && elements.categorySourceInput?.value === "naver_trend";

    setBlocksVisibility(elements.modeVisibilityBlocks, mode, "modeVisibility");
    setBlocksVisibility(elements.expandSourceVisibilityBlocks, expandSource, "expandSourceVisibility");
    setBlocksVisibility(elements.analyzeSourceVisibilityBlocks, analyzeSource, "analyzeSourceVisibility");

    if (elements.selectedCollectedCount) {
        if (expandUsesManual) {
            elements.selectedCollectedCount.textContent = `직접 입력 ${expandCount}건`;
        } else if (expandSource === "collector_selected") {
            elements.selectedCollectedCount.textContent = `선택 ${selectedCount}건`;
        } else {
            elements.selectedCollectedCount.textContent = "수집 결과 전체";
        }
    }

    if (elements.manualAnalyzeCount) {
        elements.manualAnalyzeCount.textContent = analyzeUsesManual
            ? `직접 입력 ${analyzeCount}건`
            : "확장 결과 사용";
    }

    if (elements.expandManualInput) {
        elements.expandManualInput.disabled = !expandUsesManual;
    }
    if (elements.analyzeManualInput) {
        elements.analyzeManualInput.disabled = !analyzeUsesManual;
    }
    if (elements.seedInput) {
        elements.seedInput.disabled = categoryMode;
        elements.seedInput.title = categoryMode ? "카테고리 모드에서는 시드 키워드를 사용하지 않습니다." : "";
    }
    if (elements.categoryInput) {
        elements.categoryInput.disabled = !categoryMode;
        elements.categoryInput.title = categoryMode ? "" : "시드 모드에서는 카테고리를 사용하지 않습니다.";
    }
    if (elements.categorySourceInput) {
        elements.categorySourceInput.disabled = !categoryMode;
    }
    if (elements.optionRelated) {
        elements.optionRelated.title = usesTrendSource ? "트렌드 수집은 preset fallback 설정에서만 적용됩니다." : "";
    }
    if (elements.optionAutocomplete) {
        elements.optionAutocomplete.title = usesTrendSource ? "트렌드 수집은 preset fallback 설정에서만 적용됩니다." : "";
    }
    if (elements.optionBulk) {
        elements.optionBulk.title = usesTrendSource ? "트렌드 수집은 preset fallback 설정에서만 적용됩니다." : "";
    }
    if (elements.stopStreamButton) {
        elements.stopStreamButton.title = (state.streamAbortController || state.requestAbortController)
            ? "실시간 확장/분석 스트림을 중지합니다."
            : "";
    }

    updateGradeFilterUI();
    renderTrendSettingsState();
}

function renderCollectedList(items) {
    const selectedCount = getSelectedCollectedItems().length;
    const groupedQueryCount = new Set(items.map((item) => String(item.raw || item.keyword || "").trim()).filter(Boolean)).size;
    const sourceCounts = summarizeCollectedSources(items);

    return `
        <div class="collector-compact-board">
            <div class="collector-compact-toolbar">
                <div class="collector-compact-stats">
                    <span class="collector-compact-stat"><strong>${escapeHtml(String(items.length))}</strong>수집</span>
                    <span class="collector-compact-stat"><strong>${escapeHtml(String(selectedCount))}</strong>선택</span>
                    <span class="collector-compact-stat"><strong>${escapeHtml(String(groupedQueryCount))}</strong>원본 묶음</span>
                </div>
                <div class="collector-toolbar-actions">
                    <button type="button" class="ghost-btn collector-action-btn" data-collector-action="select_all">전체 선택</button>
                    <button type="button" class="ghost-btn collector-action-btn" data-collector-action="clear_all">선택 해제</button>
                </div>
            </div>
            ${sourceCounts.length ? `
                <div class="collector-compact-sources">
                    ${sourceCounts.map((item) => `
                        <span class="badge">${escapeHtml(formatCollectorSource(item.source))} ${escapeHtml(String(item.count))}건</span>
                    `).join("")}
                </div>
            ` : ""}
            <div class="collector-compact-grid">
                ${items.slice(0, 40).map((item) => {
                    const identity = createCollectedIdentity(item);
                    const selected = state.selectedCollectedKeys.includes(identity);

                    return `
                        <label class="collector-compact-card ${selected ? "selected" : ""}">
                            <div class="collector-compact-head">
                                <strong>${escapeHtml(item.keyword || "-")}</strong>
                                <span class="collector-compact-source">${escapeHtml(formatCollectorSource(item.source))}</span>
                            </div>
                            <div class="collector-compact-meta">
                                <span class="badge">원본 ${escapeHtml(item.raw || "-")}</span>
                                <span class="badge">카테고리 ${escapeHtml(item.category || "미분류")}</span>
                                ${item.rank ? `<span class="badge">순위 ${escapeHtml(String(item.rank))}</span>` : ""}
                                ${item.rank_change !== undefined ? `<span class="badge">${escapeHtml(formatTrendRankChange(item.rank_change))}</span>` : ""}
                            </div>
                            <span class="collector-compact-select">
                                <input
                                    type="checkbox"
                                    data-collected-key="${escapeHtml(identity)}"
                                    ${selected ? "checked" : ""}
                                />
                                <span>확장 입력에 사용</span>
                            </span>
                        </label>
                    `;
                }).join("")}
            </div>
        </div>
    `;
}

function getActiveGuideTab() {
    if (state.activeGuideTab) {
        return state.activeGuideTab;
    }
    return elements.guideTabButtons?.[0]?.dataset.guideTab || "";
}

function setGuideTab(tabKey) {
    if (!tabKey) {
        return;
    }
    state.activeGuideTab = tabKey;
    renderGuideTabs();
}

function renderGuideTabs() {
    const activeTab = getActiveGuideTab();
    elements.guideTabButtons?.forEach((button) => {
        const isActive = (button.dataset.guideTab || "") === activeTab;
        button.classList.toggle("active", isActive);
    });
    elements.guideTabPanels?.forEach((panel) => {
        const isActive = (panel.dataset.guidePanel || "") === activeTab;
        panel.hidden = !isActive;
        panel.classList.toggle("active", isActive);
    });
}

function getTitleSettingsFormState() {
    const mode = syncTitleModeInputFromRadios();
    const provider = elements.titleProvider.value;
    return {
        mode,
        provider,
        model: elements.titleModel.value.trim() || TITLE_PROVIDER_DEFAULT_MODELS[provider] || "gpt-4o-mini",
        api_key: elements.titleApiKey.value.trim(),
        temperature: elements.titleTemperature.value.trim() || "0.7",
        fallback_to_template: elements.titleFallback.checked,
    };
}

function setGlobalStatus(message, kind) {
    elements.pipelineStatus.textContent = message;
    elements.pipelineStatus.classList.remove("running", "error", "cancelled");
    if (kind === "running") {
        elements.pipelineStatus.classList.add("running");
    }
    if (kind === "error") {
        elements.pipelineStatus.classList.add("error");
    }
    if (kind === "cancelled") {
        elements.pipelineStatus.classList.add("cancelled");
    }
}

function renderProgress() {
    const completedCount = STAGES.filter((stage) => state.stageStatus[stage.key].state === "success").length;
    const runningStage = STAGES.find((stage) => state.stageStatus[stage.key].state === "running");
    const cancelledStages = STAGES.filter((stage) => state.stageStatus[stage.key].state === "cancelled");
    const progressUnits = completedCount + (runningStage ? 0.45 : 0);
    const progressPercent = Math.min(100, Math.round((progressUnits / STAGES.length) * 100));

    elements.progressBar.style.width = `${progressPercent}%`;
    elements.progressText.textContent = `${completedCount} / ${STAGES.length} 단계 완료`;

    if (runningStage) {
        elements.progressDetail.textContent = `${runningStage.label} 진행 중 · ${formatElapsed(state.stageStatus[runningStage.key])}`;
        return;
    }
    if (cancelledStages.length > 0) {
        const lastCancelled = cancelledStages[cancelledStages.length - 1];
        elements.progressDetail.textContent = `${lastCancelled.label} 단계에서 중지되었습니다. 현재까지 수집된 결과는 유지됩니다.`;
        return;
    }
    elements.progressDetail.textContent = completedCount === 0
        ? "아직 실행되지 않았습니다."
        : `${completedCount}개 단계가 완료되었습니다.`;
}

function resolveControlFocusStage() {
    if (state.stageStatus.titled.state === "running") {
        return "title";
    }
    if (state.stageStatus.selected.state === "running") {
        return "select";
    }
    if (state.stageStatus.analyzed.state === "running") {
        return "analyze";
    }
    if (state.stageStatus.expanded.state === "running") {
        return "expand";
    }
    if (state.stageStatus.collected.state === "running") {
        return "collect";
    }

    if (state.results.selected?.selected_keywords?.length && !state.results.titled?.generated_titles?.length) {
        return "title";
    }
    if (state.results.analyzed?.analyzed_keywords?.length && !state.results.selected?.selected_keywords?.length) {
        return "select";
    }
    if (state.results.expanded?.expanded_keywords?.length && !state.results.analyzed?.analyzed_keywords?.length) {
        return "analyze";
    }
    if (state.results.collected?.collected_keywords?.length && !state.results.expanded?.expanded_keywords?.length) {
        return "expand";
    }
    return "collect";
}

function reorderControlNodes(container, nodes, order, dataKey) {
    if (!container || !Array.isArray(nodes) || nodes.length === 0) {
        return;
    }

    const orderMap = new Map(order.map((key, index) => [key, index]));
    [...nodes]
        .sort((left, right) => {
            const leftOrder = orderMap.get(left.dataset[dataKey] || "") ?? 99;
            const rightOrder = orderMap.get(right.dataset[dataKey] || "") ?? 99;
            return leftOrder - rightOrder;
        })
        .forEach((node) => container.appendChild(node));
}

function syncControlFocus() {
    const focusStage = resolveControlFocusStage();
    reorderControlNodes(
        elements.controlStack,
        elements.controlPrimaryBlocks,
        ["collect", "pipeline"],
        "controlBlock",
    );
    reorderControlNodes(
        elements.controlLauncherColumn || elements.controlStack,
        elements.controlLauncherBlocks,
        ["expand", "analyze", "title"],
        "controlBlock",
    );

    elements.controlBlocks?.forEach((block) => {
        const key = block.dataset.controlBlock || "";
        const isFocused = key === focusStage
            || (focusStage === "select" && key === "pipeline");
        block.classList.toggle("focus-stage", isFocused);
    });

    elements.controlCards?.forEach((card) => {
        const key = card.dataset.controlCard || "";
        const isFocused = (focusStage === "expand" && key === "expand")
            || (focusStage === "analyze" && key === "analyze");
        card.classList.toggle("focus-stage", isFocused);
    });
}

function beginAbortableRequest(stageKey, endpoint) {
    const controller = new AbortController();
    state.requestAbortController = controller;
    state.requestAbortStageKey = String(stageKey || "");
    state.requestAbortEndpoint = String(endpoint || "");
    state.requestAbortRequested = false;
    syncBusyButtons();
    renderAll();
    return controller;
}

function completeAbortableRequest(controller) {
    if (state.requestAbortController === controller) {
        state.requestAbortController = null;
        state.requestAbortStageKey = "";
        state.requestAbortEndpoint = "";
        state.requestAbortRequested = false;
    }
    syncBusyButtons();
}

function getAbortableStageKeys() {
    if (state.requestAbortController && state.requestAbortStageKey) {
        return [state.requestAbortStageKey];
    }
    if (!state.streamAbortController) {
        return [];
    }
    if (state.streamAbortEndpoint === "/expand/analyze/stream") {
        return ["expanded", "analyzed"];
    }
    if (state.streamAbortEndpoint === "/expand/stream") {
        return ["expanded"];
    }
    return [];
}

function isStageAbortable(stageKey) {
    return getAbortableStageKeys().includes(String(stageKey || ""));
}

function isAbortRequestedForStage(stageKey) {
    const safeStageKey = String(stageKey || "");
    if (state.requestAbortController && state.requestAbortStageKey === safeStageKey) {
        return Boolean(state.requestAbortRequested);
    }
    return isStageAbortable(safeStageKey) && Boolean(state.streamAbortRequested);
}

function renderStageStopAction(stageKey) {
    if (!isStageAbortable(stageKey)) {
        return "";
    }
    const requested = isAbortRequestedForStage(stageKey);
    return `
        <button
            type="button"
            class="inline-action-btn ${requested ? "requested" : ""}"
            data-inline-action="stop_stage_run"
            data-stage-stop="${escapeHtml(String(stageKey || ""))}"
            ${requested ? "disabled" : ""}
        >${requested ? "중지 요청됨..." : "중지"}</button>
    `;
}

function updateStopButtonState() {
    if (!elements.stopStreamButton) {
        return;
    }

    const isActive = Boolean(state.isBusy && (state.streamAbortController || state.requestAbortController));
    const isRequested = Boolean(state.streamAbortRequested || state.requestAbortRequested);
    elements.stopStreamButton.disabled = !isActive || isRequested;
    elements.stopStreamButton.classList.toggle("requested", isRequested);
    elements.stopStreamButton.textContent = isRequested ? "중지 요청됨..." : "중지";
}

function syncBusyButtons() {
    elements.actionButtons.forEach((button) => {
        if (button === elements.stopStreamButton) {
            return;
        }
        button.disabled = state.isBusy;
    });
    updateStopButtonState();
}

async function runWithGuard(task, runningMessage) {
    if (state.isBusy) {
        addLog("\uc774\ubbf8 \ub2e4\ub978 \uc791\uc5c5\uc744 \uc2e4\ud589 \uc911\uc785\ub2c8\ub2e4. \ud604\uc7ac \ub2e8\uacc4\uac00 \ub05d\ub09c \ub4a4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.", "error");
        return;
    }

    state.isBusy = true;
    state.lastError = null;
    setGlobalStatus(runningMessage, "running");
    syncBusyButtons();
    renderAll();

    try {
        await task();
        setGlobalStatus("\uc2e4\ud589 \uc644\ub8cc", "success");
    } catch (error) {
        if (isAbortLikeError(error)) {
            state.lastError = null;
            setGlobalStatus("\uc911\uc9c0\ub428", "cancelled");
            addLog(error.message || "\uc2e4\uc2dc\uac04 \uc791\uc5c5\uc744 \uc911\uc9c0\ud588\uc2b5\ub2c8\ub2e4.", "info");
        } else {
            const normalizedError = normalizeError(error);
            state.lastError = normalizedError;
            setGlobalStatus("\uc624\ub958 \ubc1c\uc0dd", "error");
            addLog(buildErrorHeadline(normalizedError), "error");
        }
    } finally {
        state.isBusy = false;
        syncBusyButtons();
        renderAll();
    }
}

function cancelActiveStream() {
    if (!state.streamAbortController || state.streamAbortRequested) {
        return;
    }
    state.streamAbortRequested = true;
    addLog("\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911\uc9c0\ub97c \uc694\uccad\ud588\uc2b5\ub2c8\ub2e4. \ub9c8\uc9c0\ub9c9 \uc218\uc2e0 \ub370\uc774\ud130\uae4c\uc9c0 \ubcf4\uc874\ud569\ub2c8\ub2e4.", "info");
    updateStopButtonState();
    state.streamAbortController.abort("user_cancelled");
    renderAll();
}

function buildExpandedLiveSubtitle() {
    const streamMeta = state.results.expanded?.stream_meta;
    if (!streamMeta) {
        return "\uc2e4\uc2dc\uac04\uc73c\ub85c \ud655\uc7a5 \ud0a4\uc6cc\ub4dc\ub97c \ubcf4\uc5ec\uc8fc\uace0 \uc788\uc2b5\ub2c8\ub2e4.";
    }

    const parts = [];
    if (streamMeta.depth) {
        parts.push(`${streamMeta.depth}\ub2e8\uacc4`);
    }
    if (streamMeta.currentKeyword) {
        parts.push(streamMeta.currentKeyword);
    }
    if (streamMeta.queueSize) {
        parts.push(`\ub300\uae30 ${streamMeta.queueSize}\uac1c`);
    }
    if (state.streamAbortRequested) {
        parts.push("\uc911\uc9c0 \uc694\uccad\ub428");
    }

    return parts.length > 0
        ? `${parts.join(" \u00b7 ")} \uc0c1\ud0dc\uc785\ub2c8\ub2e4.`
        : "\uc2e4\uc2dc\uac04\uc73c\ub85c \ud655\uc7a5 \ud0a4\uc6cc\ub4dc\ub97c \ubcf4\uc5ec\uc8fc\uace0 \uc788\uc2b5\ub2c8\ub2e4.";
}

function normalizeGradeValue(grade) {
    const safeGrade = String(grade || "").trim().toUpperCase();
    return GRADE_ORDER.includes(safeGrade) ? safeGrade : "";
}

function normalizeGradeList(grades) {
    const gradeSet = new Set(
        (grades || [])
            .map((grade) => normalizeGradeValue(grade))
            .filter(Boolean),
    );
    return GRADE_ORDER.filter((grade) => gradeSet.has(grade));
}

function getSelectedGradeFilters() {
    return normalizeGradeList(state.selectGradeFilters);
}

function buildGradeRunLabel(grades) {
    const normalizedGrades = normalizeGradeList(grades);
    return normalizedGrades.length === GRADE_ORDER.length
        ? "전체 등급"
        : `${normalizedGrades.join(", ")} 등급`;
}

function updateGradeFilterUI() {
    const selectedGrades = getSelectedGradeFilters();
    const selectedSet = new Set(selectedGrades);

    elements.gradeToggleButtons?.forEach((button) => {
        const grade = normalizeGradeValue(button.dataset.gradeToggle || "");
        const isActive = selectedSet.has(grade);
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });

    elements.gradePresetButtons?.forEach((button) => {
        const presetGrades = normalizeGradeList(GRADE_PRESET_MAP[button.dataset.gradePreset || ""] || []);
        const isActive = presetGrades.length === selectedGrades.length
            && presetGrades.every((grade) => selectedSet.has(grade));
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });

    if (elements.gradeSelectSummary) {
        elements.gradeSelectSummary.textContent = selectedGrades.length === GRADE_ORDER.length
            ? "전체 등급 선별"
            : selectedGrades.length
                ? `선택 등급: ${selectedGrades.join(", ")}`
                : "등급을 1개 이상 선택하세요.";
    }

    if (elements.runGradeSelectButton) {
        elements.runGradeSelectButton.disabled = state.isBusy || selectedGrades.length === 0;
    }
}

function applyGradePreset(presetKey) {
    const presetGrades = normalizeGradeList(GRADE_PRESET_MAP[presetKey] || []);
    const selectedGrades = getSelectedGradeFilters();
    const isSamePreset = presetGrades.length === selectedGrades.length
        && presetGrades.every((grade) => selectedGrades.includes(grade));

    state.selectGradeFilters = isSamePreset ? [] : presetGrades;
    state.gradeSelectionTouched = true;
    updateGradeFilterUI();
    renderResults();
}

function toggleGradeFilter(grade) {
    const normalizedGrade = normalizeGradeValue(grade);
    if (!normalizedGrade) {
        return;
    }

    const selectedSet = new Set(getSelectedGradeFilters());
    if (selectedSet.has(normalizedGrade)) {
        selectedSet.delete(normalizedGrade);
    } else {
        selectedSet.add(normalizedGrade);
    }
    state.selectGradeFilters = GRADE_ORDER.filter((item) => selectedSet.has(item));
    state.gradeSelectionTouched = true;
    updateGradeFilterUI();
    renderResults();
}

async function runThroughGradeSelect(allowedGrades) {
    await runSelectStage({ allowedGrades });
}

function getForwardSelectOptions() {
    if (!state.gradeSelectionTouched) {
        return {};
    }

    const allowedGrades = getSelectedGradeFilters();
    return allowedGrades.length ? { allowedGrades } : {};
}

function hasMatchingSelectionProfile(allowedGrades) {
    const normalizedGrades = normalizeGradeList(allowedGrades || []);
    const profile = state.results.selected?.selection_profile || null;

    if (!normalizedGrades.length) {
        return !profile || profile.mode !== "grade_filter";
    }

    const profileGrades = normalizeGradeList(profile?.allowed_grades || []);
    return profile?.mode === "grade_filter"
        && profileGrades.length === normalizedGrades.length
        && normalizedGrades.every((grade) => profileGrades.includes(grade));
}

async function runSelectStage(options = {}) {
    if (!state.results.analyzed?.analyzed_keywords?.length) {
        await runAnalyzeStage();
    } else if (state.stageStatus.analyzed.state === "cancelled") {
        addLog(`중지 전까지 분석된 ${countItems(state.results.analyzed.analyzed_keywords)}건으로 선별을 이어갑니다.`);
    }

    const allowedGrades = normalizeGradeList(options.allowedGrades || []);
    const analyzedKeywords = state.results.analyzed?.analyzed_keywords || [];
    const selectionCandidates = allowedGrades.length
        ? analyzedKeywords.filter((item) => allowedGrades.includes(resolveAnalysisGrade(item)))
        : analyzedKeywords;

    if (!selectionCandidates.length) {
        if (allowedGrades.length) {
            throw new Error(`선택한 등급(${allowedGrades.join(", ")})에 맞는 분석 결과가 없습니다.`);
        }
        throw new Error("선별할 분석 결과가 없습니다.");
    }

    addLog(
        allowedGrades.length
            ? `선별 시작: ${allowedGrades.join(", ")} 등급 ${countItems(selectionCandidates)}건에 골든 기준을 적용합니다.`
            : "선별 시작: 골든 키워드 기준을 적용합니다.",
    );
    clearStageAndDownstream("selected");
    const result = await executeStage({
        stageKey: "selected",
        endpoint: "/select",
        inputData: {
            analyzed_keywords: selectionCandidates,
            select_options: allowedGrades.length
                ? { allowed_grades: allowedGrades, mode: "grade_filter" }
                : {},
        },
    });

    state.results.selected = {
        ...result,
        selection_profile: {
            mode: allowedGrades.length ? "grade_filter" : "default",
            allowed_grades: allowedGrades,
            candidate_count: selectionCandidates.length,
        },
    };
    addLog(
        allowedGrades.length
            ? `선별 완료 (${allowedGrades.join(", ")}): ${countItems(result.selected_keywords)}건`
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
        || !hasMatchingSelectionProfile(forwardSelectOptions.allowedGrades || [])
    ) {
        await runSelectStage(forwardSelectOptions);
    }

    const titleOptions = buildTitleOptions();
    if (state.stageStatus.selected.state === "cancelled") {
        addLog(`중지 전까지 선별된 ${countItems(state.results.selected?.selected_keywords)}건으로 제목 생성을 이어갑니다.`);
    }
    addLog(
        titleOptions.mode === "ai"
            ? `제목 생성 시작: ${titleOptions.provider} / ${titleOptions.model} 모델을 사용합니다.`
            : "제목 생성 시작: template 규칙 기반 제목을 생성합니다.",
    );
    clearStageAndDownstream("titled");
    const result = await executeStage({
        stageKey: "titled",
        endpoint: "/generate-title",
        inputData: {
            selected_keywords: state.results.selected?.selected_keywords || [],
            title_options: titleOptions,
        },
    });

    state.results.titled = result;
    addLog(`제목 생성 완료: ${countItems(result.generated_titles)}세트`, "success");
    renderAll();
    return result;
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

function renderResultStageTabs(resultViews, activeViewKey) {
    return `
        <div class="results-stage-switcher">
            ${resultViews.map((view) => `
                <button
                    type="button"
                    class="results-stage-tab ${escapeHtml(view.state || "pending")}${view.key === activeViewKey ? " active" : ""}"
                    data-result-tab="${escapeHtml(view.key)}"
                    aria-pressed="${view.key === activeViewKey ? "true" : "false"}"
                >
                    <span class="results-stage-step">${escapeHtml(view.stageLabel)}</span>
                    <strong>${escapeHtml(view.tabTitle)}</strong>
                    <span class="results-stage-meta">${escapeHtml(view.countLabel)}</span>
                </button>
            `).join("")}
        </div>
    `;
}

function renderResults() {
    const collectedItems = state.results.collected?.collected_keywords || [];
    const expandedItems = state.results.expanded?.expanded_keywords || [];
    const analyzedItems = state.results.analyzed?.analyzed_keywords || [];
    const selectedItems = state.results.selected?.selected_keywords || [];
    const generatedTitles = state.results.titled?.generated_titles || [];
    const lowQualityTitleCount = countRetryRecommendedTitles(generatedTitles);
    const selectedProfile = state.results.selected?.selection_profile || null;
    const collectedState = state.stageStatus.collected.state;
    const selectedState = state.stageStatus.selected.state;
    const titledState = state.stageStatus.titled.state;
    const expandedRunning = state.stageStatus.expanded.state === "running";
    const analyzedRunning = state.stageStatus.analyzed.state === "running";
    const expandedCancelled = state.stageStatus.expanded.state === "cancelled";
    const analyzedCancelled = state.stageStatus.analyzed.state === "cancelled";
    const workbenchAvailable = (
        expandedItems.length
        || analyzedItems.length
        || expandedRunning
        || analyzedRunning
        || expandedCancelled
        || analyzedCancelled
        || state.stageStatus.expanded.state === "error"
        || state.stageStatus.analyzed.state === "error"
    );
    const analyzedViewAvailable = analyzedItems.length || analyzedRunning || analyzedCancelled || state.stageStatus.analyzed.state === "error";
    const resultViews = [];

    if (collectedItems.length || collectedState !== "pending") {
        resultViews.push({
            key: "collected",
            stageLabel: "1단계 수집",
            tabTitle: "수집",
            countLabel: collectedItems.length
                ? `${countItems(collectedItems)}건`
                : (collectedState === "running" ? "실행 중" : state.stageStatus.collected.message),
            state: collectedState,
            render: () => resultCard("수집 키워드", collectedItems, collectedItems.length ? renderCollectedList : () => '<div class="collector-empty">수집 결과를 준비하는 중입니다.</div>', {
                subtitle: collectedItems.length
                    ? "원본 쿼리별로 묶어서 바로 선택할 수 있습니다."
                    : state.stageStatus.collected.message,
                className: "collector-result-card",
                actionsHtml: renderStageStopAction("collected"),
            }),
        });
    }

    if (workbenchAvailable) {
        resultViews.push({
            key: "expanded",
            stageLabel: "2단계 확장",
            tabTitle: "확장",
            countLabel: expandedItems.length
                ? `확장 ${countItems(expandedItems)}건`
                : (expandedRunning ? "실행 중" : state.stageStatus.expanded.message),
            state: state.stageStatus.expanded.state,
            render: () => renderKeywordWorkbenchCard(expandedItems, analyzedItems, {
                selectedCount: selectedItems.length,
                primaryView: "expanded",
                displayMode: "expanded_only",
            }),
        });
    }

    if (analyzedViewAvailable) {
        resultViews.push({
            key: "analyzed",
            stageLabel: "3단계 분석",
            tabTitle: "분석",
            countLabel: analyzedItems.length
                ? `검증 ${countItems(analyzedItems)}건`
                : (analyzedRunning ? "실행 중" : state.stageStatus.analyzed.message),
            state: state.stageStatus.analyzed.state,
            render: () => renderKeywordWorkbenchCard(expandedItems, analyzedItems, {
                selectedCount: selectedItems.length,
                primaryView: "analyzed",
                displayMode: "analyzed_only",
            }),
        });
    }

    if (selectedItems.length || selectedState !== "pending") {
        const selectedTitle = selectedProfile?.mode === "combo_filter"
            ? "조합 선별 키워드"
            : (selectedProfile?.mode === "grade_filter" ? "등급 선별 키워드" : "골든 후보 키워드");
        const selectedSubtitle = selectedProfile?.mode === "combo_filter"
            ? `${(selectedProfile.allowed_profitability_grades || []).join(", ")} 수익성 · ${(selectedProfile.allowed_attackability_grades || []).join(", ")} 공략성 조합으로 선별한 결과입니다.`
            : (selectedProfile?.allowed_grades?.length
                ? `${selectedProfile.allowed_grades.join(", ")} 등급 키워드를 그대로 다음 단계로 보낸 결과입니다.`
                : (selectedItems.length ? "기본 골든 후보 규칙으로 자동 선별한 결과입니다." : ""));
        resultViews.push({
            key: "selected",
            stageLabel: "4단계 선별",
            tabTitle: "선별",
            countLabel: selectedItems.length
                ? `${countItems(selectedItems)}건`
                : (selectedState === "running" ? "실행 중" : state.stageStatus.selected.message),
            state: selectedState,
            render: () => resultCard(selectedTitle, selectedItems, selectedItems.length ? renderSelectedList : () => '<div class="collector-empty">선별 결과를 준비하는 중입니다.</div>', {
                className: "downstream-result-card",
                subtitle: selectedItems.length ? selectedSubtitle : state.stageStatus.selected.message,
                actionsHtml: [
                    renderStageStopAction("selected"),
                    selectedItems.length && !generatedTitles.length
                        ? `<button type="button" class="inline-action-btn" data-inline-action="continue_title">이 결과로 제목 생성</button>`
                        : "",
                ].join(""),
            }),
        });
    }

    if (generatedTitles.length || titledState !== "pending") {
        resultViews.push({
            key: "titled",
            stageLabel: "5단계 제목 생성",
            tabTitle: "제목",
            countLabel: generatedTitles.length
                ? `${countItems(generatedTitles)}세트`
                : (titledState === "running" ? "실행 중" : state.stageStatus.titled.message),
            state: titledState,
            render: () => resultCard("생성된 제목", generatedTitles, generatedTitles.length ? renderTitleList : () => '<div class="collector-empty">제목 결과를 준비하는 중입니다.</div>', {
                className: "downstream-result-card",
                subtitle: generatedTitles.length
                    ? buildEnhancedTitleGenerationSummaryText(state.results.titled?.generation_meta, generatedTitles)
                    : state.stageStatus.titled.message,
                actionsHtml: [
                    generatedTitles.length ? renderTitleResultControls(generatedTitles) : "",
                    renderStageStopAction("titled"),
                    lowQualityTitleCount
                        ? `<button type="button" class="inline-action-btn" data-inline-action="rerun_title_flagged">기준 미달 ${escapeHtml(String(lowQualityTitleCount))}건만 다시 생성</button>`
                        : "",
                    selectedItems.length
                        ? '<button type="button" class="inline-action-btn" data-inline-action="rerun_title">제목 다시 생성</button>'
                        : "",
                ].join(""),
            }),
        });
    }

    const activeViewKey = resolveActiveResultView(resultViews);
    const activeView = resultViews.find((view) => view.key === activeViewKey) || null;
    const railHtml = activeViewKey === "expanded" || activeViewKey === "analyzed"
        ? renderWorkbenchAside(expandedItems, analyzedItems)
        : "";
    const resultsDomState = typeof captureResultsDomState === "function"
        ? captureResultsDomState()
        : null;

    elements.layoutGrid?.classList.toggle("results-first", Boolean(activeView));
    elements.resultsGrid.innerHTML = activeView
        ? `
            ${renderResultStageTabs(resultViews, activeViewKey)}
            <div class="results-stage-body">${activeView.render()}</div>
        `
        : `
            <div class="placeholder">
                실행 버튼을 누르면 수집 결과와 확장·검증 작업대가 이 영역에 표시됩니다.<br />
                현재 단계 결과가 자동으로 앞으로 오고, 이전 단계는 탭으로 다시 확인할 수 있습니다.
            </div>
        `;

    if (elements.resultsRail && elements.resultsRailPanel) {
        elements.resultsRail.innerHTML = railHtml;
        elements.resultsRailPanel.hidden = !railHtml;
    }
    if (typeof restoreResultsDomState === "function") {
        restoreResultsDomState(resultsDomState);
    }
}

function renderKeywordWorkbenchCard(expandedItems, analyzedItems, options = {}) {
    const expandedRunning = state.stageStatus.expanded.state === "running";
    const analyzedRunning = state.stageStatus.analyzed.state === "running";
    const expandedCancelled = state.stageStatus.expanded.state === "cancelled";
    const analyzedCancelled = state.stageStatus.analyzed.state === "cancelled";
    const primaryView = options.primaryView === "analyzed" ? "analyzed" : "expanded";
    const prioritizeAnalysis = primaryView === "analyzed" && (analyzedItems.length || analyzedRunning || analyzedCancelled);
    const displayMode = options.displayMode === "expanded_only" || options.displayMode === "analyzed_only"
        ? options.displayMode
        : "combined";
    const allOrigins = new Set(
        [...expandedItems, ...analyzedItems]
            .map((item) => String(item.origin || item.raw || item.keyword || "").trim())
            .filter(Boolean),
    );
    const measuredCount = analyzedItems.filter(isMeasuredItem).length;
    const goldenCount = analyzedItems.filter(isGoldenCandidate).length;
    const highBidCount = analyzedItems.filter((item) => Number(item.metrics?.bid || 0) >= 500).length;
    const queueSize = Number(state.results.expanded?.stream_meta?.queueSize || 0);
    const measuredRatio = analyzedItems.length
        ? `${Math.round((measuredCount / analyzedItems.length) * 100)}%`
        : "0%";
    const subtitleClassName = expandedCancelled || analyzedCancelled
        ? "result-subtitle partial"
        : "result-subtitle";
    const actions = [];
    const stopStageKey = primaryView === "analyzed" ? "analyzed" : "expanded";
    const stopActionHtml = renderStageStopAction(stopStageKey);

    if (stopActionHtml && !(stopStageKey === "expanded" && expandedRunning)) {
        actions.push(stopActionHtml);
    }

    if (!analyzedItems.length && expandedItems.length) {
        actions.push('<button type="button" class="inline-action-btn" data-inline-action="continue_analyze">이 결과로 분석 계속</button>');
    }
    if (!options.selectedCount && analyzedItems.length) {
        actions.push('<button type="button" class="inline-action-btn" data-inline-action="continue_select">이 결과로 선별 계속</button>');
    }

    const expandedSection = `
        <section class="workbench-panel">
            <div class="workbench-panel-head">
                <div>
                    <p class="panel-kicker">Live Expansion</p>
                    <h4>실시간 확장</h4>
                </div>
                <span class="badge">원본 ${escapeHtml(String(allOrigins.size || 0))}개</span>
            </div>
            ${(expandedItems.length || expandedRunning || expandedCancelled)
                ? renderExpandedList(expandedItems)
                : '<div class="collector-empty">확장 결과가 쌓이면 이 영역에서 실시간 누적 상태를 바로 볼 수 있습니다.</div>'}
        </section>
    `;
    const analyzedSection = `
        <section class="workbench-panel">
            <div class="workbench-panel-head">
                <div>
                    <p class="panel-kicker">Validation Console</p>
                    <h4>키워드 검증 테이블</h4>
                </div>
                <span class="badge">${escapeHtml(String(measuredCount))}건 실측</span>
            </div>
            ${(analyzedItems.length || analyzedRunning || analyzedCancelled)
                ? renderAnalyzedList(analyzedItems)
                : '<div class="collector-empty">확장 결과가 쌓이면 PC/MO조회, 클릭수, 입찰가 기준으로 바로 검증할 수 있습니다.</div>'}
        </section>
    `;
    const orderedPanels = prioritizeAnalysis
        ? [analyzedSection, expandedSection]
        : [expandedSection, analyzedSection];
    const visiblePanels = displayMode === "expanded_only"
        ? [expandedSection]
        : displayMode === "analyzed_only"
            ? [analyzedSection]
            : orderedPanels;

    return `
        <article class="result-card keyword-workbench-card">
            <div class="workbench-head">
                <div class="result-head">
                    <div class="result-head-copy">
                        <h3>확장 · 검증 작업대</h3>
                        <p class="${subtitleClassName}">${escapeHtml(buildWorkbenchSubtitle({
                            expandedItems,
                            analyzedItems,
                            measuredCount,
                            goldenCount,
                            highBidCount,
                            expandedRunning,
                            analyzedRunning,
                            expandedCancelled,
                            analyzedCancelled,
                        }))}</p>
                    </div>
                    <div class="result-actions">
                        <span class="result-count">확장 ${countItems(expandedItems)}건</span>
                        <span class="result-count">검증 ${countItems(analyzedItems)}건</span>
                        ${actions.join("")}
                    </div>
                </div>
                <div class="workbench-hero-strip">
                    <div class="collector-stat-card">
                        <span>원본 수</span>
                        <strong>${escapeHtml(String(allOrigins.size || 0))}</strong>
                    </div>
                    <div class="collector-stat-card">
                        <span>실측 비중</span>
                        <strong>${escapeHtml(measuredRatio)}</strong>
                    </div>
                    <div class="collector-stat-card">
                        <span>${escapeHtml(getQuickCandidateLabel())}</span>
                        <strong>${escapeHtml(String(goldenCount))}</strong>
                    </div>
                    <div class="collector-stat-card">
                        <span>입찰1 500+</span>
                        <strong>${escapeHtml(String(highBidCount))}</strong>
                    </div>
                    ${(expandedRunning || analyzedRunning) && queueSize
                        ? `
                            <div class="collector-stat-card">
                                <span>대기</span>
                                <strong>${escapeHtml(String(queueSize))}</strong>
                            </div>
                        `
                        : ""}
                </div>
            </div>
            <div class="workbench-shell">
                <div class="workbench-main">
                    ${visiblePanels.join("")}
                </div>
            </div>
        </article>
    `;
}

function buildWorkbenchSubtitle({
    expandedItems,
    analyzedItems,
    measuredCount,
    goldenCount,
    highBidCount,
    expandedRunning,
    analyzedRunning,
    expandedCancelled,
    analyzedCancelled,
}) {
    const parts = [];
    if (expandedRunning) {
        parts.push(buildExpandedLiveSubtitle());
    }
    if (analyzedRunning) {
        parts.push(state.stageStatus.analyzed.message || "실시간 검증 중");
    }
    if (!parts.length && (expandedCancelled || analyzedCancelled)) {
        if (expandedCancelled) {
            parts.push(`중지 전까지 확장 ${countItems(expandedItems)}건이 누적됐습니다.`);
        }
        if (analyzedCancelled) {
            parts.push(`중지 전까지 검증 ${countItems(analyzedItems)}건이 평가됐습니다.`);
        }
    }
    if (!parts.length && analyzedItems.length) {
        parts.push(`실측 ${measuredCount}건 · ${getQuickCandidateLabel()} ${goldenCount}건 · 입찰1위 500원+ ${highBidCount}건`);
    }
    if (!parts.length && expandedItems.length) {
        parts.push(`확장 결과 ${countItems(expandedItems)}건을 바로 검증으로 넘길 수 있습니다.`);
    }
    return parts.join(" · ") || "실시간 확장과 검증 결과를 한 화면에서 이어서 비교합니다.";
}

function renderWorkbenchAside(expandedItems, analyzedItems) {
    const bidLeaders = getTopAnalyzedItems(analyzedItems, (item) => item.metrics?.bid);
    const volumeLeaders = getTopAnalyzedItems(analyzedItems, (item) => item.metrics?.volume);
    const modeSummary = summarizeAnalysisModes(analyzedItems);
    const typeSummary = summarizeExpandedTypes(expandedItems);
    const scoreGuideCard = `
        <section class="workbench-side-card score-guide-card">
            <div class="workbench-side-head">
                <strong>스코어 등급 안내</strong>
                <span>샘플 기준 공식을 현재 검증 화면에 맞춰 바로 볼 수 있게 정리했습니다.</span>
            </div>
            <div class="workbench-guide-list">
                ${[
                    ["S", "85+ 최고 가치"],
                    ["A", "70+ 높은 가치"],
                    ["B", "55+ 양호"],
                    ["C", "40+ 보통"],
                    ["D", "25+ 낮음"],
                    ["F", "25 미만 낮음"],
                ].map(([grade, label]) => `
                    <div class="workbench-guide-row">
                        ${renderGradeBadge(grade)}
                        <span>${escapeHtml(label)}</span>
                    </div>
                `).join("")}
            </div>
            <div class="workbench-guide-note">
                <strong>스코어 = CPC(40%) + 검색량(35%) + 희귀성(25%)</strong><br />
                CPC가 높고, 검색량이 많고, 블로그 글이 적을수록 높은 점수로 봅니다.
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
        ${scoreGuideCard}
    `;
}

function renderWorkbenchFeedCard(title, subtitle, entries, emptyText, metaBuilder) {
    return `
        <section class="workbench-side-card">
            <div class="workbench-side-head">
                <strong>${escapeHtml(title)}</strong>
                <span>${escapeHtml(subtitle)}</span>
            </div>
            ${entries.length
                ? `
                    <div class="workbench-feed-list">
                        ${entries.map(({ item }, index) => `
                            <div class="workbench-feed-row">
                                <span class="workbench-feed-rank ${index < 3 ? "top" : ""}">${escapeHtml(String(index + 1))}</span>
                                <div class="workbench-feed-copy">
                                    <strong>${escapeHtml(item.keyword || "-")}</strong>
                                    <span>${escapeHtml(metaBuilder(item))}</span>
                                </div>
                            </div>
                        `).join("")}
                    </div>
                `
                : `<div class="collector-empty">${escapeHtml(emptyText)}</div>`}
        </section>
    `;
}

function getTopAnalyzedItems(items, valueSelector, limit = 8) {
    return [...(items || [])]
        .map((item) => ({
            item,
            value: Number(valueSelector(item) || 0),
        }))
        .filter((entry) => entry.value > 0)
        .sort((left, right) => {
            if (right.value !== left.value) {
                return right.value - left.value;
            }
            return Number(right.item.score || 0) - Number(left.item.score || 0);
        })
        .slice(0, limit);
}

function summarizeAnalysisModes(items) {
    return (items || []).reduce(
        (summary, item) => {
            if (isMeasuredItem(item)) {
                summary.measured += 1;
            } else {
                summary.estimated += 1;
            }
            return summary;
        },
        { measured: 0, estimated: 0 },
    );
}

function resultCard(title, items, renderer, options = {}) {
    const subtitleClassName = options.subtitleClassName ? `result-subtitle ${options.subtitleClassName}` : "result-subtitle";

    return `
        <article class="result-card ${escapeHtml(options.className || "")}">
            <div class="result-head">
                <h3>${escapeHtml(title)}</h3>
                <div class="result-actions">
                    <span class="result-count">총 ${countItems(items)}건</span>
                    ${options.actionsHtml || ""}
                </div>
            </div>
            ${options.subtitle ? `<p class="${escapeHtml(subtitleClassName)}">${escapeHtml(options.subtitle)}</p>` : ""}
            ${renderer(items)}
        </article>
    `;
}

state.analyzedFilters = state.analyzedFilters || createDefaultAnalyzedFilters();

function createDefaultAnalyzedFilters() {
    return {
        query: "",
        minScore: "",
        minPcSearch: "",
        minMoSearch: "",
        minTotalSearch: "1",
        maxTotalSearch: "",
        minBlog: "",
        minPcClicks: "",
        minMoClicks: "",
        minTotalClicks: "",
        minCpc: "",
        minBid1: "",
        minBid2: "",
        minBid3: "",
        maxCompetition: "",
        priority: "all",
        measured: "all",
    };
}

function getAnalyzedFilters() {
    return {
        ...createDefaultAnalyzedFilters(),
        ...(state.analyzedFilters || {}),
    };
}

function hasActiveAnalyzedFilters(filters = getAnalyzedFilters()) {
    return Object.entries(filters).some(([key, value]) => {
        if (key === "priority" || key === "measured") {
            return value && value !== "all";
        }
        return String(value || "").trim() !== "";
    });
}

function coerceFilterNumber(value) {
    if (value === null || value === undefined) {
        return null;
    }
    if (typeof value === "string" && value.trim() === "") {
        return null;
    }
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

function applyAnalyzedFilters(items) {
    const filters = getAnalyzedFilters();
    const selectedGrades = new Set(getSelectedGradeFilters());
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
        const itemGrade = resolveAnalysisGrade(item);
        if (selectedGrades.size && !selectedGrades.has(itemGrade)) {
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

function isMeasuredItem(item) {
    return String(item?.analysis_mode || "") === "search_metrics";
}

function isGoldenCandidate(item) {
    const volume = Number(item?.metrics?.volume || 0);
    const blogResults = Number(item?.metrics?.blog_results || 0);
    return volume >= 1000 && blogResults > 0 && blogResults <= 10000;
}

function getQuickCandidateLabel() {
    return "샘플식 후보";
}

function summarizeGradeCounts(items) {
    const counts = new Map(GRADE_ORDER.map((grade) => [grade, 0]));
    (items || []).forEach((item) => {
        const grade = resolveAnalysisGrade(item);
        if (!grade) {
            return;
        }
        counts.set(grade, (counts.get(grade) || 0) + 1);
    });
    return GRADE_ORDER.map((grade) => ({
        grade,
        count: counts.get(grade) || 0,
    }));
}

function countItemsByGrades(items, grades) {
    const allowedGrades = new Set(normalizeGradeList(grades));
    if (!allowedGrades.size) {
        return 0;
    }
    return (items || []).filter((item) => allowedGrades.has(resolveAnalysisGrade(item))).length;
}

function renderAnalyzedGradeBoard(items, visibleItems = null) {
    const gradeCounts = summarizeGradeCounts(items);
    const selectedGrades = getSelectedGradeFilters();
    const selectedSet = new Set(selectedGrades);
    const selectedCount = Array.isArray(visibleItems) ? countItems(visibleItems) : countItemsByGrades(items, selectedGrades);
    const allSelected = selectedGrades.length === GRADE_ORDER.length;
    const saSelected = ["S", "A"].every((grade) => selectedSet.has(grade)) && selectedGrades.length === 2;

    return `
        <div class="analysis-grade-board">
            <div class="analysis-grade-head">
                <strong>등급별 개수 및 즉시 필터</strong>
                <span>${escapeHtml(
                    allSelected
                        ? `전체 등급 ${countItems(items)}건이 현재 테이블에 반영되고 있습니다.`
                        : selectedGrades.length
                            ? `선택 등급 ${selectedGrades.join(", ")} ${selectedCount}건이 현재 테이블에 바로 반영됩니다.`
                            : "등급을 1개 이상 선택해 주세요.",
                )}</span>
            </div>
            <div class="analysis-grade-strip">
                ${gradeCounts.map(({ grade, count }) => `
                    <button
                        type="button"
                        class="ghost-chip grade-toggle-chip analysis-grade-chip${selectedSet.has(grade) ? " active" : ""}"
                        data-inline-action="toggle_analysis_grade"
                        data-grade-toggle="${escapeHtml(grade)}"
                        aria-pressed="${selectedSet.has(grade) ? "true" : "false"}"
                    >
                        ${renderGradeBadge(grade)}
                        <span class="analysis-grade-chip-copy">
                            <strong>${escapeHtml(grade)}</strong>
                            <span>${escapeHtml(`${formatNumber(count)}건`)}</span>
                        </span>
                    </button>
                `).join("")}
            </div>
            <div class="analysis-grade-actions">
                <button
                    type="button"
                    class="ghost-chip${allSelected ? " active" : ""}"
                    data-inline-action="apply_analysis_grade_preset"
                    data-grade-preset="all"
                >전체</button>
                <button
                    type="button"
                    class="ghost-chip${saSelected ? " active" : ""}"
                    data-inline-action="apply_analysis_grade_preset"
                    data-grade-preset="sa"
                >S·A</button>
                <button
                    type="button"
                    class="inline-action-btn analysis-grade-run"
                    data-inline-action="run_analysis_grade_select"
                    ${selectedCount > 0 ? "" : "disabled"}
                >선택 등급 선별 실행</button>
            </div>
        </div>
    `;
}

function renderGradeBadge(grade) {
    const safeGrade = String(grade || "-").trim().toUpperCase();
    const tone = /^[SABCDF]$/.test(safeGrade) ? safeGrade.toLowerCase() : "unknown";
    return `<span class="table-grade-badge grade-${escapeHtml(tone)}">${escapeHtml(safeGrade)}</span>`;
}

function renderAnalysisKeywordCell(item) {
    const meta = [];
    if (item.origin && item.origin !== item.keyword) {
        meta.push(`원본 ${item.origin}`);
    }
    if (item.type) {
        meta.push(formatExpandedType(item.type));
    }
    return `
        <div class="analysis-keyword-cell">
            <strong>${escapeHtml(item.keyword || "-")}</strong>
            ${meta.length ? `<span>${escapeHtml(meta.join(" · "))}</span>` : ""}
        </div>
    `;
}

function renderAnalysisSourceCell(item) {
    const badges = [
        `<span class="analysis-source-pill ${isMeasuredItem(item) ? "measured" : "estimated"}">${escapeHtml(formatMeasuredState(item))}</span>`,
    ];
    if (item.type) {
        badges.push(`<span class="analysis-source-pill type">${escapeHtml(formatExpandedType(item.type))}</span>`);
    }
    if (item.origin && item.origin !== item.keyword) {
        badges.push(`<span class="analysis-source-pill origin">${escapeHtml(`원본 ${item.origin}`)}</span>`);
    }
    return `<div class="analysis-source-cell">${badges.join("")}</div>`;
}

function renderAnalyzedList(items) {
    const filters = getAnalyzedFilters();
    const filteredItems = applyAnalyzedFilters(items);
    const measuredCount = filteredItems.filter(isMeasuredItem).length;
    const goldenCount = filteredItems.filter(isGoldenCandidate).length;
    const highBidCount = filteredItems.filter((item) => Number(item.metrics?.bid || 0) >= 500).length;
    const typeCount = new Set(filteredItems.map((item) => String(item.type || "").trim()).filter(Boolean)).size;
    const rows = filteredItems.map((item) => `
        <tr class="${isMeasuredItem(item) ? "measured-row" : "estimated-row"}">
            <td>${renderAnalysisKeywordCell(item)}</td>
            <td>${renderGradeBadge(resolveAnalysisGrade(item))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.score))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.pc_searches))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.mobile_searches))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.volume))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.blog_results))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.pc_clicks))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.mobile_clicks))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.total_clicks))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.cpc))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.bid))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.bid_2))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.bid_3))}</td>
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
                    <span>입찰1 500+</span>
                    <strong>${escapeHtml(String(highBidCount))}</strong>
                </div>
                <div class="collector-stat-card">
                    <span>출처 유형</span>
                    <strong>${escapeHtml(String(typeCount))}</strong>
                </div>
            </div>
            <div class="analysis-filter-tip">
                <strong>필터 팁</strong>
                <span>합계↑에 1을 넣으면 검색량 0 키워드를 먼저 걸러낼 수 있고, 입찰1↑ 500은 광고 단가가 붙는 키워드만 빠르게 남깁니다.</span>
            </div>
            <div class="analysis-filter-tip">
                <strong>참고</strong>
                <span>\`${escapeHtml(getQuickCandidateLabel())}\`는 S등급이 아니라 샘플식 빠른 체크입니다. 기준은 총조회 1,000 이상 + 블로그 10,000 이하이고, 실제 다음 단계 전송은 아래 등급 선택을 기준으로 동작합니다.</span>
            </div>
            ${renderAnalyzedGradeBoard(items, filteredItems)}
            <div class="analysis-filter-stack">
                <div class="analysis-filter-row primary">
                    <input class="analysis-filter-input" type="search" data-analyzed-filter="query" value="${escapeHtml(filters.query)}" placeholder="키워드 검색..." />
                    <select class="analysis-filter-select" data-analyzed-filter="priority">
                        <option value="all"${filters.priority === "all" ? " selected" : ""}>우선순위 전체</option>
                        <option value="high"${filters.priority === "high" ? " selected" : ""}>상</option>
                        <option value="medium"${filters.priority === "medium" ? " selected" : ""}>중</option>
                        <option value="low"${filters.priority === "low" ? " selected" : ""}>하</option>
                    </select>
                    <select class="analysis-filter-select" data-analyzed-filter="measured">
                        <option value="all"${filters.measured === "all" ? " selected" : ""}>측정 전체</option>
                        <option value="measured"${filters.measured === "measured" ? " selected" : ""}>실측만</option>
                        <option value="estimated"${filters.measured === "estimated" ? " selected" : ""}>추정만</option>
                    </select>
                    <button type="button" class="ghost-chip" data-inline-action="reset_analyzed_filters">필터 초기화</button>
                    <span class="analysis-filter-summary">표시 ${filteredItems.length} / 전체 ${countItems(items)}건</span>
                </div>
                <div class="analysis-filter-row metrics">
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minPcSearch" value="${escapeHtml(filters.minPcSearch)}" placeholder="PC조회↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minMoSearch" value="${escapeHtml(filters.minMoSearch)}" placeholder="MO조회↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minTotalSearch" value="${escapeHtml(filters.minTotalSearch)}" placeholder="합계↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="maxTotalSearch" value="${escapeHtml(filters.maxTotalSearch)}" placeholder="합계↓" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minBlog" value="${escapeHtml(filters.minBlog)}" placeholder="블로그↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minScore" value="${escapeHtml(filters.minScore)}" placeholder="점수↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minCpc" value="${escapeHtml(filters.minCpc)}" placeholder="CPC↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="maxCompetition" value="${escapeHtml(filters.maxCompetition)}" placeholder="경쟁↓" />
                </div>
                <div class="analysis-filter-row metrics">
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minPcClicks" value="${escapeHtml(filters.minPcClicks)}" placeholder="PC클릭↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minMoClicks" value="${escapeHtml(filters.minMoClicks)}" placeholder="MO클릭↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minTotalClicks" value="${escapeHtml(filters.minTotalClicks)}" placeholder="클릭합↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minBid1" value="${escapeHtml(filters.minBid1)}" placeholder="입찰1↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minBid2" value="${escapeHtml(filters.minBid2)}" placeholder="입찰2↑" />
                    <input class="analysis-filter-input" type="number" min="0" step="0.1" data-analyzed-filter="minBid3" value="${escapeHtml(filters.minBid3)}" placeholder="입찰3↑" />
                </div>
            </div>
            <div class="expanded-table-wrap full">
                <table class="expanded-table analyzed-table compact">
                    <thead>
                        <tr>
                            <th>키워드</th>
                            <th>등급</th>
                            <th>점수</th>
                            <th>PC조회</th>
                            <th>MO조회</th>
                            <th>총조회</th>
                            <th>블로그</th>
                            <th>PC클릭</th>
                            <th>MO클릭</th>
                            <th>클릭합</th>
                            <th>CPC</th>
                            <th>1위입찰</th>
                            <th>2위입찰</th>
                            <th>3위입찰</th>
                            <th>출처</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="15">조건에 맞는 키워드가 없습니다.</td></tr>`}</tbody>
                </table>
            </div>
        </div>
    `;
}

function renderSelectedList(items) {
    const rows = (items || []).map((item, index) => `
        <tr>
            <td class="num-cell">${escapeHtml(String(index + 1))}</td>
            <td>${renderAnalysisKeywordCell(item)}</td>
            <td>${renderGradeBadge(resolveAnalysisGrade(item))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.score))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.pc_searches))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.mobile_searches))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.volume))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.blog_results))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.cpc))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.bid))}</td>
            <td>${renderAnalysisSourceCell(item)}</td>
        </tr>
    `).join("");

    return `
        <div class="analysis-console">
            <div class="expanded-table-wrap">
                <table class="expanded-table selected-table compact">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>키워드</th>
                            <th>등급</th>
                            <th>점수</th>
                            <th>PC조회</th>
                            <th>MO조회</th>
                            <th>총조회</th>
                            <th>블로그</th>
                            <th>CPC</th>
                            <th>1위입찰</th>
                            <th>출처</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="11">선별 결과가 없습니다.</td></tr>`}</tbody>
                </table>
            </div>
        </div>
    `;
}

function formatMeasuredState(item) {
    const mode = String(item.analysis_mode || "");
    const confidence = Number(item.confidence ?? item.metrics?.confidence ?? 0);
    if (mode === "search_metrics") {
        return `실측 ${formatNumber(confidence)}`;
    }
    return `추정 ${formatNumber(confidence)}`;
}

function updateAnalyzedFilter(name, value) {
    state.analyzedFilters = {
        ...getAnalyzedFilters(),
        [name]: value,
    };
    renderResults();
}

function resetAnalyzedFilters() {
    state.analyzedFilters = createDefaultAnalyzedFilters();
    renderResults();
}

function updateTitleResultControl(name, value) {
    if (name === "mode") {
        state.titleModeFilter = normalizeTitleResultModeFilter(value);
    } else if (name === "sort") {
        state.titleSort = normalizeTitleResultSort(value);
    } else {
        return;
    }
    renderResults();
    scheduleDashboardSessionSave();
}

function handleResultsGridInput(event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) {
        return;
    }

    const filterName = target.dataset.analyzedFilter || "";
    if (!filterName) {
        return;
    }

    updateAnalyzedFilter(filterName, target.value);
}

function handleResultsGridChange(event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) {
        return;
    }

    const filterName = target.dataset.analyzedFilter || "";
    if (filterName) {
        updateAnalyzedFilter(filterName, target.value);
        return;
    }

    const titleResultControl = target.dataset.titleResultControl || "";
    if (titleResultControl) {
        updateTitleResultControl(titleResultControl, target.value);
        return;
    }

    if (!(target instanceof HTMLInputElement) || !target.matches("[data-collected-key]")) {
        return;
    }

    const identity = target.dataset.collectedKey || "";
    if (!identity) {
        return;
    }

    if (target.checked) {
        if (!state.selectedCollectedKeys.includes(identity)) {
            state.selectedCollectedKeys = [...state.selectedCollectedKeys, identity];
        }
    } else {
        state.selectedCollectedKeys = state.selectedCollectedKeys.filter((item) => item !== identity);
    }

    renderInputState();
    renderResults();
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
        if (action === "apply_analysis_grade_preset") {
            applyGradePreset(inlineTrigger.getAttribute("data-grade-preset") || "");
            return;
        }
        if (action === "run_analysis_grade_select") {
            const grades = getSelectedGradeFilters();
            if (!grades.length) {
                return;
            }
            runWithGuard(
                () => runThroughGradeSelect(grades),
                `${buildGradeRunLabel(grades)} 선별 실행 중`,
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

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("resultsGrid")?.addEventListener("input", handleResultsGridInput);
});

function resetAllLegacy() {
    state.results = createEmptyResults();
    state.stageStatus = createInitialStageStatus();
    state.diagnostics = createEmptyDiagnostics();
    state.selectedCollectedKeys = [];
    state.lastError = null;
    state.analyzedFilters = createDefaultAnalyzedFilters();
    setGlobalStatus("대기 중", "idle");
    renderAll();
    addLog("결과와 디버그 정보를 초기화했습니다.");
}

function renderInputStateLegacy() {
    const mode = getCollectorMode();
    const categoryMode = mode === "category";
    const selectedCount = getSelectedCollectedItems().length;
    const expandCount = parseKeywordText(elements.expandManualInput?.value || "").length;
    const analyzeCount = parseKeywordText(elements.analyzeManualInput?.value || "").length;
    const expandSource = elements.expandInputSource?.value || "collector_all";
    const analyzeSource = elements.analyzeInputSource?.value || "expanded_results";
    const expandUsesManual = expandSource === "manual_text";
    const analyzeUsesManual = analyzeSource === "manual_text";
    const usesTrendSource = categoryMode && elements.categorySourceInput?.value === "naver_trend";

    setBlocksVisibility(elements.modeVisibilityBlocks, mode, "modeVisibility");
    setBlocksVisibility(elements.expandSourceVisibilityBlocks, expandSource, "expandSourceVisibility");
    setBlocksVisibility(elements.analyzeSourceVisibilityBlocks, analyzeSource, "analyzeSourceVisibility");

    if (elements.selectedCollectedCount) {
        if (expandUsesManual) {
            elements.selectedCollectedCount.textContent = `직접 입력 ${expandCount}건`;
        } else if (expandSource === "collector_selected") {
            elements.selectedCollectedCount.textContent = `선택 ${selectedCount}건`;
        } else {
            elements.selectedCollectedCount.textContent = "수집 결과 전체";
        }
    }
    if (elements.manualAnalyzeCount) {
        elements.manualAnalyzeCount.textContent = analyzeUsesManual
            ? `직접 입력 ${analyzeCount}건`
            : "확장 결과 사용";
    }
    if (elements.expandManualInput) {
        elements.expandManualInput.disabled = !expandUsesManual;
    }
    if (elements.analyzeManualInput) {
        elements.analyzeManualInput.disabled = !analyzeUsesManual;
    }
    if (elements.seedInput) {
        elements.seedInput.disabled = categoryMode;
        elements.seedInput.title = categoryMode ? "카테고리 모드에서는 시드 키워드를 사용하지 않습니다." : "";
    }
    if (elements.categoryInput) {
        elements.categoryInput.disabled = !categoryMode;
        elements.categoryInput.title = categoryMode ? "" : "시드 모드에서는 카테고리를 사용하지 않습니다.";
    }
    if (elements.categorySourceInput) {
        elements.categorySourceInput.disabled = !categoryMode;
    }
    if (elements.optionRelated) {
        elements.optionRelated.title = usesTrendSource ? "트렌드 실패 후 preset fallback에서만 적용됩니다." : "";
    }
    if (elements.optionAutocomplete) {
        elements.optionAutocomplete.title = usesTrendSource ? "트렌드 실패 후 preset fallback에서만 적용됩니다." : "";
    }
    if (elements.optionBulk) {
        elements.optionBulk.title = usesTrendSource ? "트렌드 실패 후 preset fallback에서만 적용됩니다." : "";
    }
    if (elements.stopStreamButton) {
        elements.stopStreamButton.title = state.streamAbortController
            ? "실시간 확장/분석 스트림을 중지합니다."
            : "";
    }

    renderTrendSettingsState();
}

function normalizeTitleProvider(provider) {
    const normalized = String(provider || "").trim().toLowerCase();
    return TITLE_PROVIDER_MODEL_OPTIONS[normalized] ? normalized : "openai";
}

function formatTitleProviderLabel(provider) {
    const normalized = normalizeTitleProvider(provider);
    if (normalized === "gemini") return "Gemini";
    if (normalized === "anthropic") return "Anthropic";
    return "OpenAI";
}

function getTitleModelOptionsForProvider(provider) {
    return TITLE_PROVIDER_MODEL_OPTIONS[normalizeTitleProvider(provider)] || TITLE_PROVIDER_MODEL_OPTIONS.openai;
}

function normalizeTitleTemperatureValue(rawValue) {
    const normalizedValue = String(rawValue || "").trim();
    if (TITLE_TEMPERATURE_PRESETS.some((preset) => preset.value === normalizedValue)) {
        return normalizedValue;
    }

    const parsedValue = Number(normalizedValue);
    if (Number.isFinite(parsedValue)) {
        return TITLE_TEMPERATURE_PRESETS.reduce((closestPreset, currentPreset) => {
            const closestDistance = Math.abs(Number(closestPreset.value) - parsedValue);
            const currentDistance = Math.abs(Number(currentPreset.value) - parsedValue);
            return currentDistance < closestDistance ? currentPreset : closestPreset;
        }).value;
    }

    return TITLE_TEMPERATURE_DEFAULT;
}

function getTitleTemperaturePreset(value) {
    const normalizedValue = normalizeTitleTemperatureValue(value);
    return TITLE_TEMPERATURE_PRESETS.find((preset) => preset.value === normalizedValue) || TITLE_TEMPERATURE_PRESETS[0];
}

function normalizeTitlePresetKey(presetKey) {
    const normalized = String(presetKey || "").trim();
    if (!normalized || normalized === MANUAL_TITLE_PRESET_KEY) {
        return MANUAL_TITLE_PRESET_KEY;
    }
    return TITLE_PRESET_MAP[normalized] ? normalized : MANUAL_TITLE_PRESET_KEY;
}

function getTitlePresetConfig(presetKey) {
    const normalized = normalizeTitlePresetKey(presetKey);
    if (normalized === MANUAL_TITLE_PRESET_KEY) {
        return null;
    }
    return TITLE_PRESET_MAP[normalized] || null;
}

function findMatchingTitlePresetKey(settings = {}) {
    const provider = normalizeTitleProvider(settings.provider);
    const model = String(settings.model || "").trim();
    const temperature = normalizeTitleTemperatureValue(settings.temperature);
    const matchedPreset = TITLE_PRESET_LIBRARY.find((preset) => (
        !preset?.is_manual
        && normalizeTitleProvider(preset.provider) === provider
        && String(preset.model || "").trim() === model
        && normalizeTitleTemperatureValue(preset.temperature) === temperature
    ));
    return matchedPreset?.key || "";
}

function updateTitleTemperatureDescription() {
    if (!elements.titleTemperatureDescription) {
        return;
    }
    const preset = getTitleTemperaturePreset(elements.titleTemperature?.value);
    elements.titleTemperatureDescription.textContent = `${preset.label}: ${preset.description} (temperature ${preset.value})`;
}

function buildTitlePresetDescription(presetKey) {
    const preset = getTitlePresetConfig(presetKey);
    if (!preset) {
        return "Provider, 모델, temperature를 직접 조합합니다. 추가 프롬프트는 그대로 함께 적용됩니다.";
    }
    return `${preset.label}: ${preset.description} / ${formatTitleProviderLabel(preset.provider)} · ${preset.model} · temperature ${normalizeTitleTemperatureValue(preset.temperature)}`;
}

function updateTitlePresetDescription() {
    if (!elements.titlePresetDescription) {
        return;
    }
    elements.titlePresetDescription.textContent = buildTitlePresetDescription(elements.titlePreset?.value);
}

function getTitleKeywordModeState() {
    return {
        single: Boolean(elements.titleModeSingle?.checked),
        longtail_selected: Boolean(elements.titleModeLongtailSelected?.checked),
        longtail_exploratory: Boolean(elements.titleModeLongtailExploratory?.checked),
        longtail_experimental: Boolean(elements.titleModeLongtailExperimental?.checked),
    };
}

function normalizeTitleKeywordModes(rawModes) {
    const allowedModes = ["single", "longtail_selected", "longtail_exploratory", "longtail_experimental"];
    if (!Array.isArray(rawModes)) {
        return [];
    }
    const seenModes = new Set();
    return rawModes
        .map((mode) => String(mode || "").trim().toLowerCase())
        .filter((mode) => allowedModes.includes(mode) && !seenModes.has(mode) && seenModes.add(mode));
}

function applyTitleKeywordModes(rawModes) {
    const normalizedModes = normalizeTitleKeywordModes(rawModes);
    const nextModes = normalizedModes.length ? normalizedModes : ["single"];
    if (elements.titleModeSingle) {
        elements.titleModeSingle.checked = nextModes.includes("single");
    }
    if (elements.titleModeLongtailSelected) {
        elements.titleModeLongtailSelected.checked = nextModes.includes("longtail_selected");
    }
    if (elements.titleModeLongtailExploratory) {
        elements.titleModeLongtailExploratory.checked = nextModes.includes("longtail_exploratory");
    }
    if (elements.titleModeLongtailExperimental) {
        elements.titleModeLongtailExperimental.checked = nextModes.includes("longtail_experimental");
    }
}

function buildTitleKeywordModeSummary() {
    const modeState = getTitleKeywordModeState();
    const enabledLabels = [];
    if (modeState.single) enabledLabels.push("단일");
    if (modeState.longtail_selected) enabledLabels.push("V1");
    if (modeState.longtail_exploratory) enabledLabels.push("V2");
    if (modeState.longtail_experimental) enabledLabels.push("V3");
    if (!enabledLabels.length) {
        return "최소 1개는 선택해야 합니다. 현재는 자동으로 단일 키워드를 유지합니다.";
    }
    return `현재 생성 대상: ${enabledLabels.join(" + ")} / 단일은 안전형, V1은 선별 기반, V2는 탈락 연계 확장, V3는 저검색량 실험형입니다.`;
}

function updateTitleKeywordModeSummary() {
    if (!elements.titleKeywordModeSummary) {
        return;
    }
    elements.titleKeywordModeSummary.textContent = buildTitleKeywordModeSummary();
}

function setTitleModelOptions(provider, preferredValue = "") {
    if (!elements.titleModel) {
        return;
    }

    const normalizedProvider = normalizeTitleProvider(provider);
    const normalizedPreferredValue = String(preferredValue || "").trim();
    const baseOptions = getTitleModelOptionsForProvider(normalizedProvider).map((option) => ({ ...option }));

    if (normalizedPreferredValue && !baseOptions.some((option) => option.value === normalizedPreferredValue)) {
        baseOptions.unshift({
            value: normalizedPreferredValue,
            label: `[기존 저장 모델] ${normalizedPreferredValue}`,
        });
    }

    elements.titleModel.innerHTML = "";
    baseOptions.forEach((option) => {
        const optionElement = document.createElement("option");
        optionElement.value = option.value;
        optionElement.textContent = option.label;
        elements.titleModel.appendChild(optionElement);
    });

    const fallbackValue = TITLE_PROVIDER_DEFAULT_MODELS[normalizedProvider] || baseOptions[0]?.value || "";
    const targetValue = normalizedPreferredValue || fallbackValue;
    elements.titleModel.value = targetValue;
    if (elements.titleModel.value !== targetValue) {
        elements.titleModel.value = fallbackValue;
    }
}

function applyTitlePresetSelection(presetKey) {
    const normalizedPresetKey = normalizeTitlePresetKey(presetKey);
    const preset = getTitlePresetConfig(normalizedPresetKey);
    if (elements.titlePreset) {
        elements.titlePreset.value = normalizedPresetKey;
    }

    if (preset) {
        const provider = normalizeTitleProvider(preset.provider);
        elements.titleProvider.value = provider;
        setTitleModelOptions(provider, preset.model);
        elements.titleTemperature.value = normalizeTitleTemperatureValue(preset.temperature);
    }

    updateTitlePresetDescription();
    return normalizedPresetKey;
}

function getTitleSystemPromptValue() {
    return String(elements.titleSystemPrompt?.value || "").replace(/\r\n/g, "\n").trim();
}

function setTitleSystemPromptValue(value) {
    if (!elements.titleSystemPrompt) {
        return;
    }
    elements.titleSystemPrompt.value = String(value || "").replace(/\r\n/g, "\n").trim();
}

function buildTitlePromptSummary(prompt) {
    const normalizedPrompt = String(prompt || "").replace(/\s+/g, " ").trim();
    if (!normalizedPrompt) {
        return "기본 시스템 프롬프트만 사용 중입니다.";
    }
    const preview = normalizedPrompt.length > TITLE_PROMPT_PREVIEW_LIMIT
        ? `${normalizedPrompt.slice(0, TITLE_PROMPT_PREVIEW_LIMIT)}...`
        : normalizedPrompt;
    return `추가 지침 사용 중 · ${normalizedPrompt.length}자\n${preview}`;
}

function updateTitlePromptSummary() {
    if (elements.titlePromptSummary) {
        elements.titlePromptSummary.textContent = buildTitlePromptSummary(getTitleSystemPromptValue());
    }
    if (elements.clearTitlePromptButton) {
        elements.clearTitlePromptButton.disabled = !getTitleSystemPromptValue();
    }
}

function syncTitlePromptFromStorage() {
    const settings = readLocalStorageJson(TITLE_SETTINGS_STORAGE_KEY) || {};
    setTitleSystemPromptValue(settings.system_prompt || "");
    updateTitlePromptSummary();
}

function handleTitleSettingsStorageSync(event) {
    if (event.key && event.key !== TITLE_SETTINGS_STORAGE_KEY) {
        return;
    }
    syncTitlePromptFromStorage();
}

function handleTitleSettingsVisibilitySync() {
    if (!document.hidden) {
        syncTitlePromptFromStorage();
    }
}

function openTitlePromptEditor() {
    const openedWindow = window.open("/title-prompt-editor", "keywordForgeTitlePromptEditor");
    if (!openedWindow) {
        addLog("프롬프트 편집 탭을 열지 못했습니다. 팝업 차단 여부를 확인해 주세요.", "error");
    }
}

function clearTitleSystemPrompt() {
    setTitleSystemPromptValue("");
    persistTitleSettings();
    renderTitleSettingsState();
    addLog("제목 생성용 추가 프롬프트를 비웠습니다.", "success");
}

function loadTitleSettings() {
    const defaults = {
        mode: "template",
        keyword_modes: ["single", "longtail_selected"],
        preset_key: DEFAULT_TITLE_PRESET_KEY,
        provider: "openai",
        model: TITLE_PROVIDER_DEFAULT_MODELS.openai,
        api_key: "",
        temperature: TITLE_TEMPERATURE_DEFAULT,
        fallback_to_template: true,
        system_prompt: "",
    };

    const storedSettings = readLocalStorageJson(TITLE_SETTINGS_STORAGE_KEY);
    const hasStoredSettings = Boolean(storedSettings && typeof storedSettings === "object");
    const settings = { ...defaults, ...(hasStoredSettings ? storedSettings : {}) };
    const resolvedPresetKey = hasStoredSettings
        ? (
            Object.prototype.hasOwnProperty.call(storedSettings, "preset_key")
                ? normalizeTitlePresetKey(settings.preset_key)
                : (findMatchingTitlePresetKey(settings) || MANUAL_TITLE_PRESET_KEY)
        )
        : DEFAULT_TITLE_PRESET_KEY;

    applyTitleModeSelection(settings.mode);
    if (resolvedPresetKey !== MANUAL_TITLE_PRESET_KEY) {
        applyTitlePresetSelection(resolvedPresetKey);
    } else {
        const provider = normalizeTitleProvider(settings.provider);
        if (elements.titlePreset) {
            elements.titlePreset.value = MANUAL_TITLE_PRESET_KEY;
        }
        elements.titleProvider.value = provider;
        setTitleModelOptions(provider, settings.model);
        elements.titleTemperature.value = normalizeTitleTemperatureValue(settings.temperature);
        updateTitlePresetDescription();
    }
    elements.titleApiKey.value = settings.api_key || "";
    elements.titleFallback.checked = Boolean(settings.fallback_to_template);
    setTitleSystemPromptValue(settings.system_prompt || "");
    applyTitleKeywordModes(settings.keyword_modes);

    renderTitleSettingsState();
}

function handleTitleSettingsChange(event) {
    if (event?.target?.matches?.("input[name='titleModeOption']")) {
        syncTitleModeInputFromRadios();
    }

    if (event?.target === elements.titlePreset) {
        applyTitlePresetSelection(elements.titlePreset.value);
        persistTitleSettings();
        renderTitleSettingsState();
        return;
    }

    if (event?.target === elements.titleProvider) {
        const provider = normalizeTitleProvider(elements.titleProvider.value);
        const currentModel = String(elements.titleModel?.value || "").trim();
        const modelOptions = getTitleModelOptionsForProvider(provider);
        const shouldResetToDefault = !currentModel
            || modelOptions.some((option) => option.value === currentModel)
            || currentModel.startsWith("[기존 저장 모델]");

        setTitleModelOptions(
            provider,
            shouldResetToDefault ? (TITLE_PROVIDER_DEFAULT_MODELS[provider] || "") : currentModel,
        );
    }

    if (
        event?.target === elements.titleProvider
        || event?.target === elements.titleModel
        || event?.target === elements.titleTemperature
    ) {
        const matchingPresetKey = findMatchingTitlePresetKey({
            provider: elements.titleProvider?.value,
            model: elements.titleModel?.value,
            temperature: elements.titleTemperature?.value,
        });
        if (elements.titlePreset) {
            elements.titlePreset.value = matchingPresetKey || MANUAL_TITLE_PRESET_KEY;
        }
    }

    if (
        event?.target === elements.titleModeSingle
        || event?.target === elements.titleModeLongtailSelected
        || event?.target === elements.titleModeLongtailExploratory
        || event?.target === elements.titleModeLongtailExperimental
    ) {
        const enabledCount = normalizeTitleKeywordModes([
            elements.titleModeSingle?.checked ? "single" : "",
            elements.titleModeLongtailSelected?.checked ? "longtail_selected" : "",
            elements.titleModeLongtailExploratory?.checked ? "longtail_exploratory" : "",
            elements.titleModeLongtailExperimental?.checked ? "longtail_experimental" : "",
        ]).length;
        if (enabledCount === 0 && elements.titleModeSingle) {
            elements.titleModeSingle.checked = true;
        }
    }

    persistTitleSettings();
    renderTitleSettingsState();
}

function renderTitleSettingsState() {
    const mode = syncTitleModeInputFromRadios();
    const isAiMode = mode === "ai";

    setBlocksVisibility(elements.titleModeVisibilityBlocks, mode, "titleModeVisibility");

    if (elements.titlePreset) {
        elements.titlePreset.disabled = !isAiMode;
    }
    elements.titleProvider.disabled = !isAiMode;
    elements.titleModel.disabled = !isAiMode;
    elements.titleApiKey.disabled = !isAiMode;
    elements.titleTemperature.disabled = !isAiMode;
    elements.titleFallback.disabled = !isAiMode;
    if (elements.openTitlePromptEditorButton) {
        elements.openTitlePromptEditorButton.disabled = !isAiMode;
    }
    updateTitleKeywordModeSummary();
    updateTitlePresetDescription();
    updateTitleTemperatureDescription();
    updateTitlePromptSummary();
    elements.titleModeBadge.textContent = isAiMode ? `ai:${elements.titleProvider.value}` : "template";
}

function getTitleSettingsFormState() {
    const mode = syncTitleModeInputFromRadios();
    const presetKey = normalizeTitlePresetKey(elements.titlePreset?.value || "");
    const provider = normalizeTitleProvider(elements.titleProvider.value);
    const model = String(elements.titleModel?.value || "").trim() || TITLE_PROVIDER_DEFAULT_MODELS[provider] || "gpt-4o-mini";
    return {
        mode,
        keyword_modes: normalizeTitleKeywordModes([
            elements.titleModeSingle?.checked ? "single" : "",
            elements.titleModeLongtailSelected?.checked ? "longtail_selected" : "",
            elements.titleModeLongtailExploratory?.checked ? "longtail_exploratory" : "",
            elements.titleModeLongtailExperimental?.checked ? "longtail_experimental" : "",
        ]),
        preset_key: presetKey,
        provider,
        model,
        api_key: String(elements.titleApiKey?.value || "").trim(),
        temperature: normalizeTitleTemperatureValue(elements.titleTemperature?.value || TITLE_TEMPERATURE_DEFAULT),
        fallback_to_template: Boolean(elements.titleFallback?.checked),
        system_prompt: getTitleSystemPromptValue(),
    };
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
                                    추천 글 ${escapeHtml(String(cluster.recommended_article_count || 1))}개
                                </p>
                            </div>
                            <div class="content-map-head-badges">
                                ${cluster.top_grade ? renderGradeBadge(cluster.top_grade) : ""}
                                <span class="badge">
                                    ${escapeHtml(cluster.cluster_type === "multi_article" ? "분리 작성 권장" : "한 글로 묶기 좋음")}
                                </span>
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

function renderSelectedList(items) {
    const rows = (items || []).map((item, index) => `
        <tr>
            <td class="num-cell">${escapeHtml(String(index + 1))}</td>
            <td>${renderAnalysisKeywordCell(item)}</td>
            <td>${renderGradeBadge(resolveAnalysisGrade(item))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.score))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.pc_searches))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.mobile_searches))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.volume))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.blog_results))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.cpc))}</td>
            <td class="num-cell">${escapeHtml(formatNumber(item.metrics?.bid))}</td>
            <td>${renderAnalysisSourceCell(item)}</td>
        </tr>
    `).join("");

    return `
        <div class="analysis-console">
            ${renderContentMapBoard()}
            <div class="expanded-table-wrap">
                <table class="expanded-table selected-table compact">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>키워드</th>
                            <th>등급</th>
                            <th>점수</th>
                            <th>PC조회</th>
                            <th>MO조회</th>
                            <th>총조회</th>
                            <th>블로그</th>
                            <th>CPC</th>
                            <th>1위입찰</th>
                            <th>출처</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="11">선별 결과가 없습니다.</td></tr>`}</tbody>
                </table>
            </div>
        </div>
    `;
}

function getTitleQualityReport(item) {
    const report = item?.quality_report;
    return report && typeof report === "object" ? report : {};
}

function countRetryRecommendedTitles(items) {
    return (items || []).filter((item) => Boolean(getTitleQualityReport(item).retry_recommended)).length;
}

function buildTitleQualitySummaryText(items) {
    const reports = (items || [])
        .map((item) => getTitleQualityReport(item))
        .filter((report) => Object.keys(report).length);
    if (!reports.length) {
        return "제목 품질 점수를 계산하는 중입니다.";
    }

    const averageScore = reports.length
        ? Math.round(reports.reduce((sum, report) => sum + Number(report.bundle_score || 0), 0) / reports.length)
        : 0;
    const goodCount = reports.filter((report) => report.status === "good").length;
    const reviewCount = reports.filter((report) => report.status === "review").length;
    const retryCount = reports.filter((report) => report.status === "retry").length;
    return `평균 ${averageScore}점 · 양호 ${goodCount} · 재검토 ${reviewCount} · 재생성 권장 ${retryCount}`;
}

function buildTitleGenerationSummaryText(meta, items) {
    const qualitySummary = buildTitleQualitySummaryText(items);
    if (!meta || typeof meta !== "object") {
        return qualitySummary;
    }

    const usedMode = String(meta.used_mode || "").trim();
    if (!usedMode) {
        return qualitySummary;
    }
    if (usedMode === "template") {
        return `template 규칙 기반 · ${qualitySummary}`;
    }

    const presetLabel = String(meta.preset_label || "").trim();
    const providerLabel = meta.provider ? formatTitleProviderLabel(meta.provider) : "";
    const modelLabel = String(meta.model || "").trim();
    const modelSummary = [presetLabel, providerLabel, modelLabel].filter(Boolean).join(" · ");
    if (usedMode === "template_fallback") {
        return `${modelSummary || "AI 모드"} 실패 후 template fallback · ${qualitySummary}`;
    }
    if (usedMode === "ai_with_template_fallback") {
        return `${modelSummary || "AI 모드"} 일부 template fallback · ${qualitySummary}`;
    }
    return `${modelSummary || "AI 모드"} · ${qualitySummary}`;
}

function buildEnhancedTitleGenerationSummaryText(meta, items) {
    const qualitySummary = buildTitleQualitySummaryText(items);
    const modeSummary = buildGeneratedTitleModeSummary(meta, items);
    if (!meta || typeof meta !== "object") {
        return [modeSummary, qualitySummary].filter(Boolean).join(" / ");
    }

    const usedMode = String(meta.used_mode || "").trim();
    if (!usedMode) {
        return [modeSummary, qualitySummary].filter(Boolean).join(" / ");
    }
    if (usedMode === "template") {
        return ["template 규칙 기반", modeSummary, qualitySummary].filter(Boolean).join(" / ");
    }

    const presetLabel = String(meta.preset_label || "").trim();
    const providerLabel = meta.provider ? formatTitleProviderLabel(meta.provider) : "";
    const modelLabel = String(meta.model || "").trim();
    const modelSummary = [presetLabel, providerLabel, modelLabel].filter(Boolean).join(" / ");
    if (usedMode === "template_fallback") {
        return [modelSummary || "AI 모드", "template fallback", modeSummary, qualitySummary].filter(Boolean).join(" / ");
    }
    if (usedMode === "ai_with_template_fallback") {
        return [modelSummary || "AI 모드", "partial template fallback", modeSummary, qualitySummary].filter(Boolean).join(" / ");
    }
    return [modelSummary || "AI 모드", modeSummary, qualitySummary].filter(Boolean).join(" / ");
}

function buildGeneratedTitleModeSummary(meta, items) {
    const modeLabelMap = {
        single: "단일",
        longtail_selected: "V1",
        longtail_exploratory: "V2",
        longtail_experimental: "V3",
    };
    const modeOrder = ["single", "longtail_selected", "longtail_exploratory", "longtail_experimental"];
    const safeItems = Array.isArray(items) ? items : [];
    const countLabels = modeOrder
        .map((mode) => {
            const count = safeItems.filter((item) => String(item?.target_mode || "single").trim() === mode).length;
            if (!count) {
                return "";
            }
            return `${modeLabelMap[mode] || mode} ${count}건`;
        })
        .filter(Boolean);
    if (!countLabels.length) {
        return "";
    }

    const requestedModes = typeof normalizeTitleKeywordModes === "function"
        ? normalizeTitleKeywordModes(meta?.target_summary?.requested_modes || [])
        : [];
    const requestedLabels = requestedModes
        .map((mode) => modeLabelMap[mode] || "")
        .filter(Boolean);
    return requestedLabels.length
        ? `모드 ${requestedLabels.join(" + ")} / 결과 ${countLabels.join(", ")}`
        : `모드 ${countLabels.join(", ")}`;
}

function renderTitleQualityIssues(report) {
    const issues = Array.isArray(report?.issues) ? report.issues.slice(0, 3) : [];
    if (!issues.length) {
        return "";
    }
    return `<div class="title-quality-issues">${issues.map((issue) => `<span class="title-quality-pill">${escapeHtml(issue)}</span>`).join("")}</div>`;
}

function renderTitleBulletList(titles, checks) {
    const safeTitles = Array.isArray(titles) ? titles : [];
    const safeChecks = Array.isArray(checks) ? checks : [];
    if (!safeTitles.length) {
        return "<li>결과 없음</li>";
    }
    return safeTitles.map((title, index) => {
        const titleReport = safeChecks[index] || null;
        const status = titleReport?.status || "good";
        const note = Array.isArray(titleReport?.issues) && titleReport.issues.length
            ? titleReport.issues[0]
            : (titleReport?.score ? `품질 ${titleReport.score}점` : "");
        return `
            <li class="title-line ${escapeHtml(status)}">
                <span>${escapeHtml(title)}</span>
                ${note ? `<small>${escapeHtml(note)}</small>` : ""}
            </li>
        `;
    }).join("");
}

function renderTitleList(items) {
    return `<div class="title-list">${(items || []).map((item) => {
        const naverHomeCount = Array.isArray(item.titles?.naver_home) ? item.titles.naver_home.length : 0;
        const blogCount = Array.isArray(item.titles?.blog) ? item.titles.blog.length : 0;
        const qualityReport = getTitleQualityReport(item);
        const qualityStatus = qualityReport.status || "review";
        const qualityLabel = qualityReport.label || "검수 대기";
        const summary = qualityReport.summary || "제목 품질을 확인하는 중입니다.";
        const channelScores = qualityReport.channel_scores || {};
        const titleChecks = qualityReport.title_checks || {};
        const targetIdentity = getTitleTargetIdentity(item);
        return `
            <div class="title-item">
                <div class="title-item-head">
                    <div class="title-keyword">
                        <strong>${escapeHtml(item.keyword || "-")}</strong>
                        <span class="badge">제목 ${escapeHtml(String(naverHomeCount + blogCount))}개</span>
                    </div>
                    <div class="title-item-actions">
                        <span class="title-quality-chip ${escapeHtml(qualityStatus)}">품질 ${escapeHtml(String(qualityReport.bundle_score || 0))}점</span>
                        <span class="title-quality-chip ${escapeHtml(qualityStatus)}">${escapeHtml(qualityLabel)}</span>
                        <button
                            type="button"
                            class="inline-action-btn"
                            data-inline-action="rerun_title_single"
                            data-title-target-id="${escapeHtml(targetIdentity)}"
                        >이 키워드만 다시 생성</button>
                    </div>
                </div>
                ${renderTitleTargetMeta(item)}
                <div class="title-quality-summary ${escapeHtml(qualityStatus)}">
                    <strong>${escapeHtml(summary)}</strong>
                    <span>네이버 홈형 ${escapeHtml(String(channelScores.naver_home || 0))}점 · 블로그형 ${escapeHtml(String(channelScores.blog || 0))}점</span>
                </div>
                ${renderTitleQualityIssues(qualityReport)}
                <div class="title-columns">
                    <div class="title-column">
                        <h4>네이버 홈형</h4>
                        <ul>${renderTitleBulletList(item.titles?.naver_home || [], titleChecks.naver_home || [])}</ul>
                    </div>
                    <div class="title-column">
                        <h4>블로그형</h4>
                        <ul>${renderTitleBulletList(item.titles?.blog || [], titleChecks.blog || [])}</ul>
                    </div>
                </div>
            </div>
        `;
    }).join("")}</div>`;
}

function normalizeTitleResultModeFilter(value) {
    const safeValue = String(value || "all").trim();
    return TITLE_RESULT_MODE_FILTER_OPTIONS.some((option) => option.value === safeValue)
        ? safeValue
        : "all";
}

function normalizeTitleResultSort(value) {
    const safeValue = String(value || "mode_quality_desc").trim();
    return TITLE_RESULT_SORT_OPTIONS.some((option) => option.value === safeValue)
        ? safeValue
        : "mode_quality_desc";
}

function getTitleModeSortRank(mode) {
    const safeMode = String(mode || "single").trim();
    const modeOrder = ["single", "longtail_selected", "longtail_exploratory", "longtail_experimental"];
    const rank = modeOrder.indexOf(safeMode);
    return rank === -1 ? modeOrder.length : rank;
}

function buildTitleListEntries(items) {
    const modeFilter = normalizeTitleResultModeFilter(state.titleModeFilter);
    const sortKey = normalizeTitleResultSort(state.titleSort);
    const safeItems = Array.isArray(items) ? items : [];
    const filtered = safeItems
        .map((item, index) => {
            const qualityReport = getTitleQualityReport(item);
            return {
                item,
                qualityReport,
                bundleScore: Number(qualityReport.bundle_score || 0),
                keyword: String(item?.keyword || "").trim(),
                mode: String(item?.target_mode || "single").trim() || "single",
                originalIndex: index,
            };
        })
        .filter((entry) => modeFilter === "all" || entry.mode === modeFilter);

    filtered.sort((left, right) => {
        if (sortKey === "quality_desc") {
            if (right.bundleScore !== left.bundleScore) {
                return right.bundleScore - left.bundleScore;
            }
        } else if (sortKey === "quality_asc") {
            if (left.bundleScore !== right.bundleScore) {
                return left.bundleScore - right.bundleScore;
            }
        } else if (sortKey === "keyword_asc") {
            const keywordCompare = left.keyword.localeCompare(right.keyword, "ko");
            if (keywordCompare !== 0) {
                return keywordCompare;
            }
        } else {
            const modeRankGap = getTitleModeSortRank(left.mode) - getTitleModeSortRank(right.mode);
            if (modeRankGap !== 0) {
                return modeRankGap;
            }
            if (right.bundleScore !== left.bundleScore) {
                return right.bundleScore - left.bundleScore;
            }
        }

        const keywordCompare = left.keyword.localeCompare(right.keyword, "ko");
        if (keywordCompare !== 0) {
            return keywordCompare;
        }
        return left.originalIndex - right.originalIndex;
    });

    return filtered;
}

function renderTitleResultControls(items) {
    const entries = buildTitleListEntries(items);
    const totalCount = Array.isArray(items) ? items.length : 0;
    const displayedCount = entries.length;
    const currentModeFilter = normalizeTitleResultModeFilter(state.titleModeFilter);
    const currentSort = normalizeTitleResultSort(state.titleSort);
    return `
        <div class="title-sort-controls">
            <label class="title-sort-field">
                <span>버전</span>
                <select data-title-result-control="mode">
                    ${TITLE_RESULT_MODE_FILTER_OPTIONS.map((option) => `
                        <option value="${escapeHtml(option.value)}" ${currentModeFilter === option.value ? "selected" : ""}>
                            ${escapeHtml(option.label)}
                        </option>
                    `).join("")}
                </select>
            </label>
            <label class="title-sort-field">
                <span>정렬</span>
                <select data-title-result-control="sort">
                    ${TITLE_RESULT_SORT_OPTIONS.map((option) => `
                        <option value="${escapeHtml(option.value)}" ${currentSort === option.value ? "selected" : ""}>
                            ${escapeHtml(option.label)}
                        </option>
                    `).join("")}
                </select>
            </label>
            <span class="title-sort-count">표시 ${escapeHtml(String(displayedCount))} / 전체 ${escapeHtml(String(totalCount))}</span>
        </div>
    `;
}

function renderTitleList(items) {
    const entries = buildTitleListEntries(items);
    if (!entries.length) {
        return '<div class="collector-empty">선택한 조건에 맞는 제목 결과가 없습니다.</div>';
    }
    return `<div class="title-list">${entries.map(({ item, qualityReport }) => {
        const naverHomeCount = Array.isArray(item.titles?.naver_home) ? item.titles.naver_home.length : 0;
        const blogCount = Array.isArray(item.titles?.blog) ? item.titles.blog.length : 0;
        const qualityStatus = qualityReport.status || "review";
        const qualityLabel = qualityReport.label || "검수 대기";
        const summary = qualityReport.summary || "제목 문장을 확인하는 중입니다.";
        const channelScores = qualityReport.channel_scores || {};
        const titleChecks = qualityReport.title_checks || {};
        const targetIdentity = getTitleTargetIdentity(item);
        return `
            <div class="title-item">
                <div class="title-item-head">
                    <div class="title-keyword">
                        <strong>${escapeHtml(item.keyword || "-")}</strong>
                        <span class="badge">제목 ${escapeHtml(String(naverHomeCount + blogCount))}개</span>
                    </div>
                    <div class="title-item-actions">
                        <span class="title-quality-chip ${escapeHtml(qualityStatus)}">품질 ${escapeHtml(String(qualityReport.bundle_score || 0))}점</span>
                        <span class="title-quality-chip ${escapeHtml(qualityStatus)}">${escapeHtml(qualityLabel)}</span>
                        <button
                            type="button"
                            class="inline-action-btn"
                            data-inline-action="rerun_title_single"
                            data-title-target-id="${escapeHtml(targetIdentity)}"
                        >이 키워드만 다시 생성</button>
                    </div>
                </div>
                ${renderTitleTargetMeta(item)}
                <div class="title-quality-summary ${escapeHtml(qualityStatus)}">
                    <strong>${escapeHtml(summary)}</strong>
                    <span>네이버 홈형 ${escapeHtml(String(channelScores.naver_home || 0))}점 · 블로그형 ${escapeHtml(String(channelScores.blog || 0))}점</span>
                </div>
                ${renderTitleQualityIssues(qualityReport)}
                <div class="title-columns">
                    <div class="title-column">
                        <h4>네이버 홈형</h4>
                        <ul>${renderTitleBulletList(item.titles?.naver_home || [], titleChecks.naver_home || [])}</ul>
                    </div>
                    <div class="title-column">
                        <h4>블로그형</h4>
                        <ul>${renderTitleBulletList(item.titles?.blog || [], titleChecks.blog || [])}</ul>
                    </div>
                </div>
            </div>
        `;
    }).join("")}</div>`;
}

function getTitleTargetIdentity(item) {
    return String(item?.target_id || item?.keyword || "").trim();
}

function renderTitleTargetMeta(item) {
    const keyword = String(item?.keyword || "").trim();
    const modeLabel = String(item?.target_mode_label || item?.target_mode || "").trim();
    const baseKeyword = String(item?.base_keyword || "").trim();
    const supportKeywords = Array.isArray(item?.support_keywords)
        ? item.support_keywords.map((value) => String(value || "").trim()).filter(Boolean)
        : [];
    const pills = [];

    if (modeLabel) {
        pills.push(`<span class="title-quality-pill">${escapeHtml(modeLabel)}</span>`);
    }
    if (baseKeyword && baseKeyword !== keyword) {
        pills.push(`<span class="title-quality-pill">메인 ${escapeHtml(baseKeyword)}</span>`);
    }
    supportKeywords.forEach((supportKeyword) => {
        pills.push(`<span class="title-quality-pill">보조 ${escapeHtml(supportKeyword)}</span>`);
    });

    const sourceNote = String(item?.source_note || "").trim();
    const pillHtml = pills.length ? `<div class="title-quality-issues">${pills.join("")}</div>` : "";
    const noteHtml = sourceNote
        ? `<div class="title-target-note"><small>${escapeHtml(sourceNote)}</small></div>`
        : "";
    return `${pillHtml}${noteHtml}`;
}

function mergeGeneratedTitleItems(existingItems, replacementItem) {
    const replacementIdentity = getTitleTargetIdentity(replacementItem);
    if (!replacementIdentity) {
        return Array.isArray(existingItems) ? [...existingItems] : [];
    }

    const safeExistingItems = Array.isArray(existingItems) ? existingItems : [];
    const output = [];
    let replaced = false;

    safeExistingItems.forEach((item) => {
        const itemIdentity = getTitleTargetIdentity(item);
        if (itemIdentity === replacementIdentity) {
            if (!replaced) {
                output.push(replacementItem);
                replaced = true;
            }
            return;
        }
        output.push(item);
    });

    if (!replaced) {
        output.push(replacementItem);
    }

    return output;
}

function buildTitleTargetPayload(item) {
    const keyword = String(item?.keyword || "").trim();
    if (!keyword) {
        return null;
    }
    return {
        target_id: String(item?.target_id || "").trim(),
        keyword,
        target_mode: String(item?.target_mode || "single").trim(),
        target_mode_label: String(item?.target_mode_label || "").trim(),
        base_keyword: String(item?.base_keyword || keyword).trim(),
        support_keywords: Array.isArray(item?.support_keywords)
            ? item.support_keywords.map((value) => String(value || "").trim()).filter(Boolean)
            : [],
        source_keywords: Array.isArray(item?.source_keywords)
            ? item.source_keywords.map((value) => String(value || "").trim()).filter(Boolean)
            : [],
        source_kind: String(item?.source_kind || "").trim(),
        source_note: String(item?.source_note || "").trim(),
        cluster_id: String(item?.cluster_id || "").trim(),
        source_suggestion_id: String(item?.source_suggestion_id || "").trim(),
    };
}

function findGeneratedTitleItem(targetIdentity) {
    const normalizedIdentity = String(targetIdentity || "").trim();
    if (!normalizedIdentity) {
        return null;
    }
    return (state.results.titled?.generated_titles || []).find((item) => (
        getTitleTargetIdentity(item) === normalizedIdentity
    )) || null;
}

async function rerunSingleTitle(keyword) {
    const normalizedKeyword = String(keyword || "").trim();
    if (!normalizedKeyword) {
        throw new Error("다시 생성할 키워드를 찾지 못했습니다.");
    }

    const selectedItem = (state.results.selected?.selected_keywords || []).find(
        (item) => String(item?.keyword || "").trim() === normalizedKeyword,
    );
    if (!selectedItem) {
        throw new Error(`선별 결과에서 ${normalizedKeyword} 키워드를 찾지 못했습니다.`);
    }

    const titleOptions = buildTitleOptions();
    addLog(`제목 다시 생성 시작: ${normalizedKeyword}`);

    const result = await executeStage({
        stageKey: "titled",
        endpoint: "/generate-title",
        inputData: {
            selected_keywords: [selectedItem],
            title_options: titleOptions,
        },
    });

    const regeneratedItem = Array.isArray(result.generated_titles) ? result.generated_titles[0] : null;
    if (!regeneratedItem) {
        throw new Error("제목 다시 생성 결과가 비어 있습니다.");
    }

    state.results.titled = {
        ...(state.results.titled || {}),
        ...result,
        generated_titles: mergeGeneratedTitleItems(state.results.titled?.generated_titles || [], regeneratedItem),
    };
    addLog(`제목 다시 생성 완료: ${normalizedKeyword}`, "success");
    renderAll();
    return regeneratedItem;
}

async function rerunFlaggedTitles() {
    const flaggedKeywords = (state.results.titled?.generated_titles || [])
        .filter((item) => Boolean(getTitleQualityReport(item).retry_recommended))
        .map((item) => String(item?.keyword || "").trim())
        .filter(Boolean);
    if (!flaggedKeywords.length) {
        addLog("다시 생성할 기준 미달 제목이 없습니다.");
        return state.results.titled;
    }

    const flaggedKeywordSet = new Set(flaggedKeywords);
    const selectedItems = (state.results.selected?.selected_keywords || []).filter((item) => (
        flaggedKeywordSet.has(String(item?.keyword || "").trim())
    ));
    if (!selectedItems.length) {
        throw new Error("기준 미달 제목과 연결된 선별 키워드를 찾지 못했습니다.");
    }

    const titleOptions = buildTitleOptions();
    addLog(`기준 미달 제목 ${flaggedKeywords.length}건 다시 생성 시작`);

    const result = await executeStage({
        stageKey: "titled",
        endpoint: "/generate-title",
        inputData: {
            selected_keywords: selectedItems,
            title_options: titleOptions,
        },
    });

    const regeneratedItems = Array.isArray(result.generated_titles) ? result.generated_titles : [];
    if (!regeneratedItems.length) {
        throw new Error("기준 미달 제목 재생성 결과가 비어 있습니다.");
    }

    let mergedTitles = state.results.titled?.generated_titles || [];
    regeneratedItems.forEach((regeneratedItem) => {
        mergedTitles = mergeGeneratedTitleItems(mergedTitles, regeneratedItem);
    });

    state.results.titled = {
        ...(state.results.titled || {}),
        ...result,
        generated_titles: mergedTitles,
    };
    addLog(`기준 미달 제목 다시 생성 완료: ${regeneratedItems.length}건`, "success");
    renderAll();
    return state.results.titled;
}

async function rerunTitleTarget(targetIdentity) {
    const normalizedIdentity = String(targetIdentity || "").trim();
    if (!normalizedIdentity) {
        throw new Error("?ㅼ떆 ?앹꽦????? target??李얠? 紐삵뻽?듬땲??");
    }

    const targetItem = findGeneratedTitleItem(normalizedIdentity);
    const titleTarget = buildTitleTargetPayload(targetItem);
    if (!titleTarget) {
        throw new Error("?쒕ぉ ?ㅼ떆 ?앹꽦????? target payload瑜?留뚮뱾吏 紐삵뻽?듬땲??");
    }

    const titleOptions = buildTitleOptions();
    addLog(`?쒕ぉ ?ㅼ떆 ?앹꽦 ?쒖옉: ${titleTarget.keyword}`);

    const result = await executeStage({
        stageKey: "titled",
        endpoint: "/generate-title",
        inputData: {
            title_targets: [titleTarget],
            title_options: titleOptions,
        },
    });

    const regeneratedItem = Array.isArray(result.generated_titles) ? result.generated_titles[0] : null;
    if (!regeneratedItem) {
        throw new Error("?쒕ぉ ?ㅼ떆 ?앹꽦 寃곌낵媛 鍮꾩뼱 ?덉뒿?덈떎.");
    }

    const mergedGenerationMeta = {
        ...(state.results.titled?.generation_meta || {}),
        ...(result.generation_meta || {}),
    };
    state.results.titled = {
        ...(state.results.titled || {}),
        ...result,
        generation_meta: mergedGenerationMeta,
        generated_titles: mergeGeneratedTitleItems(state.results.titled?.generated_titles || [], regeneratedItem),
    };
    addLog(`?쒕ぉ ?ㅼ떆 ?앹꽦 ?꾨즺: ${titleTarget.keyword}`, "success");
    renderAll();
    return regeneratedItem;
}

async function rerunFlaggedTitleTargets() {
    const flaggedItems = (state.results.titled?.generated_titles || [])
        .filter((item) => Boolean(getTitleQualityReport(item).retry_recommended));
    if (!flaggedItems.length) {
        addLog("?ㅼ떆 ?앹꽦??湲곗? 誘몃떖 ?쒕ぉ???놁뒿?덈떎.");
        return state.results.titled;
    }

    const titleTargets = flaggedItems
        .map((item) => buildTitleTargetPayload(item))
        .filter(Boolean);
    if (!titleTargets.length) {
        throw new Error("湲곗? 誘몃떖 ?쒕ぉ??target payload瑜?留뚮뱾吏 紐삵뻽?듬땲??");
    }

    const titleOptions = buildTitleOptions();
    addLog(`湲곗? 誘몃떖 ?쒕ぉ ${titleTargets.length}嫄??ㅼ떆 ?앹꽦 ?쒖옉`);

    const result = await executeStage({
        stageKey: "titled",
        endpoint: "/generate-title",
        inputData: {
            title_targets: titleTargets,
            title_options: titleOptions,
        },
    });

    const regeneratedItems = Array.isArray(result.generated_titles) ? result.generated_titles : [];
    if (!regeneratedItems.length) {
        throw new Error("湲곗? 誘몃떖 ?쒕ぉ ?ъ깮??寃곌낵媛 鍮꾩뼱 ?덉뒿?덈떎.");
    }

    let mergedTitles = state.results.titled?.generated_titles || [];
    regeneratedItems.forEach((regeneratedItem) => {
        mergedTitles = mergeGeneratedTitleItems(mergedTitles, regeneratedItem);
    });

    const mergedGenerationMeta = {
        ...(state.results.titled?.generation_meta || {}),
        ...(result.generation_meta || {}),
    };
    state.results.titled = {
        ...(state.results.titled || {}),
        ...result,
        generation_meta: mergedGenerationMeta,
        generated_titles: mergedTitles,
    };
    addLog(`湲곗? 誘몃떖 ?쒕ぉ ?ㅼ떆 ?앹꽦 ?꾨즺: ${regeneratedItems.length}嫄?`, "success");
    renderAll();
    return state.results.titled;
}

function handleTitleResultInlineClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-inline-action]");
    if (!trigger) {
        return;
    }
    const action = trigger.getAttribute("data-inline-action") || "";
    if (action === "rerun_title") {
        runWithGuard(runThroughTitle, "제목 다시 생성 중");
        return;
    }
    if (action === "rerun_title_flagged") {
        runWithGuard(rerunFlaggedTitles, "기준 미달 제목 다시 생성 중");
        return;
    }
    if (action === "rerun_title_single") {
        const keyword = trigger.getAttribute("data-title-keyword") || "";
        runWithGuard(() => rerunSingleTitle(keyword), `${keyword || "선택 키워드"} 제목 다시 생성 중`);
    }
}

/*
function handleTitleResultInlineClickV2(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-inline-action]");
    if (!trigger) {
        return;
    }
    const action = trigger.getAttribute("data-inline-action") || "";
    if (action === "rerun_title") {
        runWithGuard(runThroughTitle, "?쒕ぉ ?ㅼ떆 ?앹꽦 以?);
        return;
    }
    if (action === "rerun_title_flagged") {
        runWithGuard(rerunFlaggedTitleTargets, "湲곗? 誘몃떖 ?쒕ぉ ?ㅼ떆 ?앹꽦 以?);
        return;
    }
    if (action === "rerun_title_single") {
        const targetIdentity = trigger.getAttribute("data-title-target-id") || "";
        const targetItem = findGeneratedTitleItem(targetIdentity);
        const keyword = String(targetItem?.keyword || "").trim();
        runWithGuard(() => rerunTitleTarget(targetIdentity), `${keyword || "?좏깮 ?ㅼ썙??} ?쒕ぉ ?ㅼ떆 ?앹꽦 以?);
    }
}

*/

function handleTitleResultInlineClickV3(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-inline-action]");
    if (!trigger) {
        return;
    }
    const action = trigger.getAttribute("data-inline-action") || "";
    if (action === "rerun_title") {
        runWithGuard(runThroughTitle, "title rerun");
        return;
    }
    if (action === "rerun_title_flagged") {
        runWithGuard(rerunFlaggedTitleTargets, "flagged title rerun");
        return;
    }
    if (action === "rerun_title_single") {
        const targetIdentity = trigger.getAttribute("data-title-target-id") || "";
        const targetItem = findGeneratedTitleItem(targetIdentity);
        const keyword = String(targetItem?.keyword || "").trim();
        runWithGuard(() => rerunTitleTarget(targetIdentity), `${keyword || "title"} rerun`);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("resultsGrid")?.addEventListener("click", handleTitleResultInlineClickV3);
});

function openTitlePromptEditor() {
    const openedWindow = window.open("/title-prompt-editor", "keywordForgeTitlePromptEditor");
    if (!openedWindow) {
        window.location.href = "/title-prompt-editor";
        return;
    }
    openedWindow.focus?.();
}
