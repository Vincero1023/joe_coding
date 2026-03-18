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
const TITLE_PROVIDER_DEFAULT_MODELS = {
    openai: "gpt-4o-mini",
    gemini: "gemini-2.5-flash",
    anthropic: "claude-sonnet-4-0",
};

const state = {
    results: createEmptyResults(),
    stageStatus: createInitialStageStatus(),
    diagnostics: createEmptyDiagnostics(),
    selectedCollectedKeys: [],
    lastError: null,
    isBusy: false,
    tickerId: null,
};

const elements = {};

document.addEventListener("DOMContentLoaded", () => {
    bindElements();
    loadTrendSettings();
    loadTitleSettings();
    bindEvents();
    startTicker();
    addLog("대시보드가 준비되었습니다. 단계별 실행과 디버그 정보를 바로 확인할 수 있습니다.", "success");
    renderAll();
});

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
    elements.titleModeBadge = document.getElementById("titleModeBadge");
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
        runWithGuard(runCollectStage, "수집 단계 실행 중");
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
    await runSelectStage();
    await runTitleStage();
    addLog("전체 파이프라인 실행이 완료되었습니다.", "success");
}

async function runThroughExpand() {
    await runExpandStage();
}

async function runThroughAnalyze() {
    await runAnalyzeStage();
}

async function runThroughSelect() {
    await runSelectStage();
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

    state.stageStatus[stageKey] = {
        state: "running",
        message: `${stage.label} 실행 중`,
        startedAt,
        finishedAt: null,
        durationMs: null,
    };
    renderAll();

    try {
        const response = await postModule(endpoint, inputData);
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

async function postModule(endpoint, inputData) {
    const startedAt = Date.now();
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
        });
    } catch (error) {
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

        return {
            keywords_text: keywordsText,
        };
    }

    const expandedKeywords = state.results.expanded?.expanded_keywords || [];
    if (expandedKeywords.length === 0) {
        throw new Error("확장 결과가 없습니다. 먼저 확장을 실행하거나 직접 입력으로 전환해 주세요.");
    }

    return {
        expanded_keywords: expandedKeywords,
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
        provider,
        model,
        api_key: apiKey,
        temperature: formState.temperature,
        fallback_to_template: formState.fallback_to_template,
    };
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

function resetAll() {
    state.results = createEmptyResults();
    state.stageStatus = createInitialStageStatus();
    state.diagnostics = createEmptyDiagnostics();
    state.selectedCollectedKeys = [];
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

function renderAll() {
    renderCounts();
    renderProgress();
    renderStageList();
    renderInputState();
    renderTrendSettingsState();
    renderTitleSettingsState();
    renderResults();
    renderDiagnostics();
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
    return number.toFixed(2).replace(/\.00$/, "");
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

    return `
        <div class="expanded-board">
            ${isStreaming ? `
                <div class="expanded-live-note">
                    <strong>\uc2e4\uc2dc\uac04 \ud655\uc7a5 \uc911</strong>
                    <span>${escapeHtml(buildExpandedLiveSubtitle())}</span>
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
                <div class="expanded-table-wrap">
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
                <details class="expanded-more">
                    <summary>\uc804\uccb4 ${escapeHtml(String(entries.length))}\uac74 \ud3bc\uccd0\ubcf4\uae30</summary>
                    <div class="expanded-table-wrap full">
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
