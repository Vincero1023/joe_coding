const originalBindElements = typeof window.bindElements === "function" ? window.bindElements : null;
const originalBindEvents = typeof window.bindEvents === "function" ? window.bindEvents : null;
const originalRunWithGuard = typeof window.runWithGuard === "function"
    ? window.runWithGuard
    : (typeof runWithGuard === "function" ? runWithGuard : null);
const originalRenderTitleSettingsState = typeof window.renderTitleSettingsState === "function"
    ? window.renderTitleSettingsState
    : null;
const QUEUE_UTILITY_TABS = ["settings", "history", "vault", "queue", "diagnostics", "logs"];
const QUEUE_WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];
const QUEUE_AUTO_REFRESH_INTERVAL_MS = 15000;
const EXECUTION_HISTORY_STORAGE_KEY = "keyword_forge_execution_history_v1";
const EXECUTION_HISTORY_VERSION = 1;
const EXECUTION_HISTORY_MAX_ENTRIES = 60;
const KEYWORD_VAULT_STORAGE_KEY = "keyword_forge_keyword_vault_v1";
const KEYWORD_VAULT_VERSION = 1;
const KEYWORD_VAULT_STATUS_OPTIONS = [
    { value: "saved", label: "보관" },
    { value: "draft", label: "초안 예정" },
    { value: "published", label: "발행 완료" },
    { value: "hold", label: "보류" },
];
const KEYWORD_VAULT_STATUS_LABELS = KEYWORD_VAULT_STATUS_OPTIONS.reduce((map, option) => {
    map[option.value] = option.label;
    return map;
}, {});
const TOPIC_SEED_INTENT_LABELS = {
    balanced: "균형형",
    need: "정보형",
    profit: "수익형",
};
const SECTION_NAV_LINK_SELECTOR = ".app-topbar-link[href^='#section-'], .workspace-nav-link[href^='#section-']";

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
    elements.toggleTitleAdvancedButton = document.getElementById("toggleTitleAdvancedButton");
    elements.titleAdvancedSettings = document.getElementById("titleAdvancedSettings");
    elements.refreshQueueSnapshotButton = document.getElementById("refreshQueueSnapshotButton");
    elements.pauseQueueRunnerButton = document.getElementById("pauseQueueRunnerButton");
    elements.resumeQueueRunnerButton = document.getElementById("resumeQueueRunnerButton");
    elements.queueRunnerStateLabel = document.getElementById("queueRunnerStateLabel");
    elements.queueRunnerJobLabel = document.getElementById("queueRunnerJobLabel");
    elements.queueJobCountLabel = document.getElementById("queueJobCountLabel");
    elements.queueOutputDirLabel = document.getElementById("queueOutputDirLabel");
    elements.queueSeedBatchNameInput = document.getElementById("queueSeedBatchNameInput");
    elements.queueSeedBatchScheduleInput = document.getElementById("queueSeedBatchScheduleInput");
    elements.queueSeedBatchSeedsInput = document.getElementById("queueSeedBatchSeedsInput");
    elements.queueSeedBatchHint = document.getElementById("queueSeedBatchHint");
    elements.queueSeedBatchCountLabel = document.getElementById("queueSeedBatchCountLabel");
    elements.submitQueueSeedBatchButton = document.getElementById("submitQueueSeedBatchButton");
    elements.queueRoutineNameInput = document.getElementById("queueRoutineNameInput");
    elements.queueRoutineTimeInput = document.getElementById("queueRoutineTimeInput");
    elements.queueRoutineWeekdayInputs = Array.from(document.querySelectorAll("[data-queue-weekday]"));
    elements.queueRoutineCategoryInputs = Array.from(document.querySelectorAll("[data-queue-category]"));
    elements.queueRoutineHint = document.getElementById("queueRoutineHint");
    elements.queueRoutineCountLabel = document.getElementById("queueRoutineCountLabel");
    elements.submitQueueRoutineButton = document.getElementById("submitQueueRoutineButton");
    elements.queueJobsList = document.getElementById("queueJobsList");
    elements.queueRoutinesList = document.getElementById("queueRoutinesList");
    elements.queueSnapshotStatus = document.getElementById("queueSnapshotStatus");
    elements.refreshExecutionHistoryButton = document.getElementById("refreshExecutionHistoryButton");
    elements.clearExecutionHistoryButton = document.getElementById("clearExecutionHistoryButton");
    elements.executionHistorySearchInput = document.getElementById("executionHistorySearchInput");
    elements.executionHistoryLimitInput = document.getElementById("executionHistoryLimitInput");
    elements.executionHistoryStatus = document.getElementById("executionHistoryStatus");
    elements.executionHistoryList = document.getElementById("executionHistoryList");
    elements.executionHistoryCountLabel = document.getElementById("executionHistoryCountLabel");
    elements.executionHistoryLatestLabel = document.getElementById("executionHistoryLatestLabel");
    elements.executionHistoryStageLabel = document.getElementById("executionHistoryStageLabel");
    elements.executionHistoryFilterLabel = document.getElementById("executionHistoryFilterLabel");
    elements.refreshKeywordVaultButton = document.getElementById("refreshKeywordVaultButton");
    elements.clearKeywordVaultButton = document.getElementById("clearKeywordVaultButton");
    elements.keywordVaultQuickAddInput = document.getElementById("keywordVaultQuickAddInput");
    elements.keywordVaultQuickAddButton = document.getElementById("keywordVaultQuickAddButton");
    elements.keywordVaultQuickAddCountLabel = document.getElementById("keywordVaultQuickAddCountLabel");
    elements.keywordVaultSearchInput = document.getElementById("keywordVaultSearchInput");
    elements.keywordVaultStatusFilter = document.getElementById("keywordVaultStatusFilter");
    elements.keywordVaultStatus = document.getElementById("keywordVaultStatus");
    elements.keywordVaultList = document.getElementById("keywordVaultList");
    elements.keywordVaultCountLabel = document.getElementById("keywordVaultCountLabel");
    elements.keywordVaultPublishedCountLabel = document.getElementById("keywordVaultPublishedCountLabel");
    elements.keywordVaultDraftCountLabel = document.getElementById("keywordVaultDraftCountLabel");
    elements.keywordVaultFilterLabel = document.getElementById("keywordVaultFilterLabel");
    elements.topicSeedInput = document.getElementById("topicSeedInput");
    elements.topicSeedIntent = document.getElementById("topicSeedIntent");
    elements.topicSeedCount = document.getElementById("topicSeedCount");
    elements.generateTopicSeedsButton = document.getElementById("generateTopicSeedsButton");
    elements.topicSeedStatus = document.getElementById("topicSeedStatus");
    elements.topicSeedSuggestionList = document.getElementById("topicSeedSuggestionList");
    elements.resultStageDockPanel = document.getElementById("resultStageDockPanel");
    elements.resultStageDock = document.getElementById("resultStageDock");
    elements.workspaceNav = document.querySelector(".workspace-nav");
    elements.sectionNavLinks = Array.from(document.querySelectorAll(SECTION_NAV_LINK_SELECTOR));
    elements.workspaceSectionNavLinks = Array.from(document.querySelectorAll(".workspace-nav-link[href^='#section-']"));
};

window.bindEvents = function bindEventsOverride() {
    originalBindEvents?.();
    ensureWorkflowUtilityState();

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
    if (elements.toggleTitleAdvancedButton && elements.toggleTitleAdvancedButton.dataset.boundClick !== "true") {
        elements.toggleTitleAdvancedButton.dataset.boundClick = "true";
        elements.toggleTitleAdvancedButton.addEventListener("click", () => {
            state.titleAdvancedOpen = !Boolean(state.titleAdvancedOpen);
            renderTitleAdvancedState();
        });
    }

    if (elements.refreshQueueSnapshotButton && elements.refreshQueueSnapshotButton.dataset.boundClick !== "true") {
        elements.refreshQueueSnapshotButton.dataset.boundClick = "true";
        elements.refreshQueueSnapshotButton.addEventListener("click", () => {
            void refreshQueueSnapshot();
        });
    }
    if (elements.pauseQueueRunnerButton && elements.pauseQueueRunnerButton.dataset.boundClick !== "true") {
        elements.pauseQueueRunnerButton.dataset.boundClick = "true";
        elements.pauseQueueRunnerButton.addEventListener("click", () => {
            void pauseQueueRunner();
        });
    }
    if (elements.resumeQueueRunnerButton && elements.resumeQueueRunnerButton.dataset.boundClick !== "true") {
        elements.resumeQueueRunnerButton.dataset.boundClick = "true";
        elements.resumeQueueRunnerButton.addEventListener("click", () => {
            void resumeQueueRunner();
        });
    }
    if (elements.submitQueueSeedBatchButton && elements.submitQueueSeedBatchButton.dataset.boundClick !== "true") {
        elements.submitQueueSeedBatchButton.dataset.boundClick = "true";
        elements.submitQueueSeedBatchButton.addEventListener("click", () => {
            void submitQueueSeedBatch();
        });
    }
    if (elements.submitQueueRoutineButton && elements.submitQueueRoutineButton.dataset.boundClick !== "true") {
        elements.submitQueueRoutineButton.dataset.boundClick = "true";
        elements.submitQueueRoutineButton.addEventListener("click", () => {
            void submitQueueRoutine();
        });
    }
    if (elements.queueSeedBatchSeedsInput && elements.queueSeedBatchSeedsInput.dataset.boundInput !== "true") {
        elements.queueSeedBatchSeedsInput.dataset.boundInput = "true";
        elements.queueSeedBatchSeedsInput.addEventListener("input", renderQueuePanel);
    }
    if (elements.refreshExecutionHistoryButton && elements.refreshExecutionHistoryButton.dataset.boundClick !== "true") {
        elements.refreshExecutionHistoryButton.dataset.boundClick = "true";
        elements.refreshExecutionHistoryButton.addEventListener("click", renderExecutionHistoryPanel);
    }
    if (elements.clearExecutionHistoryButton && elements.clearExecutionHistoryButton.dataset.boundClick !== "true") {
        elements.clearExecutionHistoryButton.dataset.boundClick = "true";
        elements.clearExecutionHistoryButton.addEventListener("click", clearExecutionHistory);
    }
    if (elements.executionHistorySearchInput && elements.executionHistorySearchInput.dataset.boundInput !== "true") {
        elements.executionHistorySearchInput.dataset.boundInput = "true";
        elements.executionHistorySearchInput.addEventListener("input", renderExecutionHistoryPanel);
    }
    if (elements.executionHistoryLimitInput && elements.executionHistoryLimitInput.dataset.boundChange !== "true") {
        elements.executionHistoryLimitInput.dataset.boundChange = "true";
        elements.executionHistoryLimitInput.addEventListener("change", renderExecutionHistoryPanel);
    }
    if (elements.executionHistoryList && elements.executionHistoryList.dataset.boundClick !== "true") {
        elements.executionHistoryList.dataset.boundClick = "true";
        elements.executionHistoryList.addEventListener("click", handleExecutionHistoryActionClick);
    }
    if (elements.refreshKeywordVaultButton && elements.refreshKeywordVaultButton.dataset.boundClick !== "true") {
        elements.refreshKeywordVaultButton.dataset.boundClick = "true";
        elements.refreshKeywordVaultButton.addEventListener("click", renderKeywordVaultPanel);
    }
    if (elements.clearKeywordVaultButton && elements.clearKeywordVaultButton.dataset.boundClick !== "true") {
        elements.clearKeywordVaultButton.dataset.boundClick = "true";
        elements.clearKeywordVaultButton.addEventListener("click", clearKeywordVault);
    }
    if (elements.keywordVaultQuickAddInput && elements.keywordVaultQuickAddInput.dataset.boundInput !== "true") {
        elements.keywordVaultQuickAddInput.dataset.boundInput = "true";
        elements.keywordVaultQuickAddInput.addEventListener("input", renderKeywordVaultPanel);
    }
    if (elements.keywordVaultQuickAddButton && elements.keywordVaultQuickAddButton.dataset.boundClick !== "true") {
        elements.keywordVaultQuickAddButton.dataset.boundClick = "true";
        elements.keywordVaultQuickAddButton.addEventListener("click", handleKeywordVaultQuickAdd);
    }
    if (elements.keywordVaultSearchInput && elements.keywordVaultSearchInput.dataset.boundInput !== "true") {
        elements.keywordVaultSearchInput.dataset.boundInput = "true";
        elements.keywordVaultSearchInput.addEventListener("input", renderKeywordVaultPanel);
    }
    if (elements.keywordVaultStatusFilter && elements.keywordVaultStatusFilter.dataset.boundChange !== "true") {
        elements.keywordVaultStatusFilter.dataset.boundChange = "true";
        elements.keywordVaultStatusFilter.addEventListener("change", renderKeywordVaultPanel);
    }
    if (elements.keywordVaultList && elements.keywordVaultList.dataset.boundClick !== "true") {
        elements.keywordVaultList.dataset.boundClick = "true";
        elements.keywordVaultList.addEventListener("click", handleKeywordVaultListClick);
    }
    if (elements.keywordVaultList && elements.keywordVaultList.dataset.boundChange !== "true") {
        elements.keywordVaultList.dataset.boundChange = "true";
        elements.keywordVaultList.addEventListener("change", handleKeywordVaultListChange);
    }
    if (elements.keywordVaultList && elements.keywordVaultList.dataset.boundInput !== "true") {
        elements.keywordVaultList.dataset.boundInput = "true";
        elements.keywordVaultList.addEventListener("input", handleKeywordVaultListInput);
    }
    if (elements.generateTopicSeedsButton && elements.generateTopicSeedsButton.dataset.boundClick !== "true") {
        elements.generateTopicSeedsButton.dataset.boundClick = "true";
        elements.generateTopicSeedsButton.addEventListener("click", () => {
            void generateTopicSeedSuggestions();
        });
    }
    if (elements.topicSeedSuggestionList && elements.topicSeedSuggestionList.dataset.boundClick !== "true") {
        elements.topicSeedSuggestionList.dataset.boundClick = "true";
        elements.topicSeedSuggestionList.addEventListener("click", handleTopicSeedSuggestionClick);
    }
    if (elements.resultsGrid && elements.resultsGrid.dataset.vaultActionBound !== "true") {
        elements.resultsGrid.dataset.vaultActionBound = "true";
        elements.resultsGrid.addEventListener("click", handleVaultResultActionClick);
    }
    if (elements.resultStageDock && elements.resultStageDock.dataset.boundClick !== "true") {
        elements.resultStageDock.dataset.boundClick = "true";
        elements.resultStageDock.addEventListener("click", handleResultStageDockClick);
    }
    elements.queueRoutineWeekdayInputs?.forEach((input) => {
        if (input.dataset.boundChange === "true") {
            return;
        }
        input.dataset.boundChange = "true";
        input.addEventListener("change", renderQueuePanel);
    });
    elements.queueRoutineCategoryInputs?.forEach((input) => {
        if (input.dataset.boundChange === "true") {
            return;
        }
        input.dataset.boundChange = "true";
        input.addEventListener("change", renderQueuePanel);
    });
    if (elements.queueJobsList && elements.queueJobsList.dataset.boundClick !== "true") {
        elements.queueJobsList.dataset.boundClick = "true";
        elements.queueJobsList.addEventListener("click", handleQueueJobActionClick);
    }
    if (elements.queueRoutinesList && elements.queueRoutinesList.dataset.boundClick !== "true") {
        elements.queueRoutinesList.dataset.boundClick = "true";
        elements.queueRoutinesList.addEventListener("click", handleQueueRoutineActionClick);
    }
    if (!document.body.dataset.queueAutoRefreshBound) {
        document.body.dataset.queueAutoRefreshBound = "true";
        window.setInterval(() => {
            if (elements.utilityDrawer?.hidden || getUtilityDrawerTab() !== "queue") {
                return;
            }
            void refreshQueueSnapshot({ silent: true, background: true });
        }, QUEUE_AUTO_REFRESH_INTERVAL_MS);
    }
    if (!state.queueSnapshotInitialized) {
        state.queueSnapshotInitialized = true;
        void refreshQueueSnapshot({ silent: true, background: true });
    }
    if (!Array.isArray(state.longtailOptionalSuffixKeys)) {
        state.longtailOptionalSuffixKeys = [];
    }
    if (typeof state.titleAdvancedOpen !== "boolean") {
        state.titleAdvancedOpen = false;
    }
    bindSectionNavigationSync();
    renderTitleAdvancedState();
    renderQueuePanel();
    renderExecutionHistoryPanel();
    renderKeywordVaultPanel();
    renderTopicSeedSuggestions();
    queueSectionNavigationRefresh(resolveCurrentSectionNavId());
};

window.renderTitleSettingsState = function renderTitleSettingsStateOverride(...args) {
    const result = originalRenderTitleSettingsState?.(...args);
    renderTitleAdvancedState();
    return result;
};
renderTitleSettingsState = window.renderTitleSettingsState;

function renderTitleAdvancedState() {
    const isOpen = Boolean(state.titleAdvancedOpen);
    if (elements.titleAdvancedSettings) {
        elements.titleAdvancedSettings.hidden = !isOpen;
    }
    if (elements.toggleTitleAdvancedButton) {
        elements.toggleTitleAdvancedButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
        elements.toggleTitleAdvancedButton.textContent = isOpen ? "추가설정 닫기" : "추가설정";
        elements.toggleTitleAdvancedButton.classList.toggle("active", isOpen);
    }
}

function handleResultStageDockClick(event) {
    const resultTabTrigger = event.target.closest("[data-result-tab]");
    if (!resultTabTrigger || resultTabTrigger.disabled || resultTabTrigger.getAttribute("aria-disabled") === "true") {
        return;
    }
    setActiveResultView(resultTabTrigger.getAttribute("data-result-tab") || "");
    if (typeof renderResults === "function") {
        renderResults();
    }
    if (window.matchMedia("(max-width: 1120px)").matches) {
        document.getElementById("section-results")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }
}

function getSectionNavigationScrollOffset() {
    const rootStyles = window.getComputedStyle(document.documentElement);
    const navHeight = Number.parseFloat(rootStyles.getPropertyValue("--nav-height")) || 68;
    return navHeight + 120;
}

function resolveSectionNavLinks() {
    if (!Array.isArray(elements.sectionNavLinks) || !elements.sectionNavLinks.length) {
        elements.sectionNavLinks = Array.from(document.querySelectorAll(SECTION_NAV_LINK_SELECTOR));
    }
    return elements.sectionNavLinks;
}

function resolveSectionNavTargets() {
    const seen = new Set();
    return resolveSectionNavLinks()
        .map((link) => String(link.getAttribute("href") || "").trim())
        .filter((href) => href.startsWith("#section-"))
        .map((href) => href.slice(1))
        .filter((targetId) => {
            if (!targetId || seen.has(targetId)) {
                return false;
            }
            seen.add(targetId);
            return true;
        })
        .map((targetId) => document.getElementById(targetId))
        .filter(Boolean);
}

function keepWorkspaceNavLinkVisible(activeId) {
    if (!activeId || !elements.workspaceNav || !Array.isArray(elements.workspaceSectionNavLinks)) {
        return;
    }
    const activeLink = elements.workspaceSectionNavLinks.find((link) => {
        const href = String(link.getAttribute("href") || "").trim();
        return href === `#${activeId}`;
    });
    if (!activeLink) {
        return;
    }
    const navBounds = elements.workspaceNav.getBoundingClientRect();
    const linkBounds = activeLink.getBoundingClientRect();
    const outOfView = linkBounds.left < navBounds.left + 12 || linkBounds.right > navBounds.right - 12;
    if (outOfView) {
        activeLink.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
            inline: "center",
        });
    }
}

function applySectionNavigationState(activeId) {
    const safeActiveId = String(activeId || "").trim().replace(/^#/, "");
    resolveSectionNavLinks().forEach((link) => {
        const href = String(link.getAttribute("href") || "").trim();
        const targetId = href.startsWith("#") ? href.slice(1) : "";
        const isActive = targetId && safeActiveId === targetId;
        link.classList.toggle("active", isActive);
        if (isActive) {
            link.setAttribute("aria-current", "location");
        } else {
            link.removeAttribute("aria-current");
        }
    });
    keepWorkspaceNavLinkVisible(safeActiveId);
    state.activeSectionNavId = safeActiveId;
}

function resolveCurrentSectionNavId() {
    const targets = resolveSectionNavTargets();
    if (!targets.length) {
        return "";
    }
    const hashTargetId = String(window.location.hash || "").trim().replace(/^#/, "");
    const threshold = window.scrollY + getSectionNavigationScrollOffset();
    let activeId = targets[0].id;
    targets.forEach((section) => {
        if (section.offsetTop <= threshold) {
            activeId = section.id;
        }
    });
    if (hashTargetId && targets.some((section) => section.id === hashTargetId)) {
        const hashTarget = document.getElementById(hashTargetId);
        if (hashTarget && hashTarget.offsetTop <= threshold + 160) {
            return hashTargetId;
        }
    }
    return activeId;
}

function refreshSectionNavigationState(forcedId = "") {
    const nextActiveId = String(forcedId || resolveCurrentSectionNavId() || "").trim().replace(/^#/, "");
    if (!nextActiveId) {
        return;
    }
    if (state.activeSectionNavId === nextActiveId) {
        return;
    }
    applySectionNavigationState(nextActiveId);
}

function queueSectionNavigationRefresh(forcedId = "") {
    const nextForcedId = String(forcedId || "").trim().replace(/^#/, "");
    if (nextForcedId) {
        state.pendingSectionNavId = nextForcedId;
    }
    if (state.sectionNavFrameRequested) {
        return;
    }
    state.sectionNavFrameRequested = true;
    window.requestAnimationFrame(() => {
        state.sectionNavFrameRequested = false;
        const pendingId = String(state.pendingSectionNavId || "").trim();
        state.pendingSectionNavId = "";
        refreshSectionNavigationState(pendingId);
    });
}

function bindSectionNavigationSync() {
    if (document.body.dataset.sectionNavBound === "true") {
        return;
    }
    document.body.dataset.sectionNavBound = "true";
    resolveSectionNavLinks().forEach((link) => {
        if (link.dataset.sectionNavClickBound === "true") {
            return;
        }
        link.dataset.sectionNavClickBound = "true";
        link.addEventListener("click", () => {
            const href = String(link.getAttribute("href") || "").trim();
            if (href.startsWith("#section-")) {
                queueSectionNavigationRefresh(href);
            }
        });
    });
    window.addEventListener("scroll", () => {
        queueSectionNavigationRefresh();
    }, { passive: true });
    window.addEventListener("resize", () => {
        queueSectionNavigationRefresh();
    });
    window.addEventListener("hashchange", () => {
        queueSectionNavigationRefresh(String(window.location.hash || "").trim());
    });
}

function ensureWorkflowUtilityState() {
    if (!state.executionHistory || typeof state.executionHistory !== "object") {
        state.executionHistory = readExecutionHistory();
    }
    if (!state.keywordVault || typeof state.keywordVault !== "object") {
        state.keywordVault = readKeywordVault();
    }
    if (!Array.isArray(state.topicSeedSuggestions)) {
        state.topicSeedSuggestions = [];
    }
    if (!state.topicSeedMeta || typeof state.topicSeedMeta !== "object") {
        state.topicSeedMeta = {};
    }
    if (typeof state.topicSeedRequestPending !== "boolean") {
        state.topicSeedRequestPending = false;
    }
}

function createEmptyExecutionHistory() {
    return {
        version: EXECUTION_HISTORY_VERSION,
        entries: [],
    };
}

function formatHistoryStageLabel(stageKey) {
    const stage = typeof getStage === "function" ? getStage(stageKey) : null;
    return stage?.label || String(stageKey || "실행");
}

function buildExecutionInputLabel(formState = {}) {
    const collectorMode = String(formState.collectorMode || getCollectorMode?.() || "category").trim();
    if (collectorMode === "category") {
        const category = String(formState.categoryInput || elements.categoryInput?.value || "").trim();
        return category ? `카테고리 / ${category}` : "카테고리 실행";
    }
    const seedInput = String(formState.seedInput || elements.seedInput?.value || "").trim();
    return seedInput ? `시드 / ${seedInput}` : "시드 실행";
}

function sanitizeExecutionTitleSettings(rawSettings) {
    if (!rawSettings || typeof rawSettings !== "object") {
        return {};
    }
    const nextSettings = { ...rawSettings };
    delete nextSettings.api_key;
    return nextSettings;
}

function normalizeExecutionHistoryEntry(rawEntry, index = 0) {
    if (!rawEntry || typeof rawEntry !== "object") {
        return null;
    }

    const stageKey = String(
        rawEntry.finished_stage_key
        || rawEntry.stage_key
        || rawEntry.last_stage_key
        || "collected",
    ).trim();
    const recordedAt = Number.parseInt(String(rawEntry.recorded_at ?? rawEntry.recordedAt ?? Date.now()), 10) || Date.now();
    const resultCounts = rawEntry.result_counts && typeof rawEntry.result_counts === "object"
        ? rawEntry.result_counts
        : {};

    return {
        id: String(rawEntry.id || `history-${recordedAt}-${index}`).trim(),
        recorded_at: recordedAt,
        started_at: Number.parseInt(String(rawEntry.started_at ?? rawEntry.startedAt ?? recordedAt), 10) || recordedAt,
        finished_stage_key: stageKey,
        finished_stage_label: String(rawEntry.finished_stage_label || rawEntry.stage_label || formatHistoryStageLabel(stageKey)).trim(),
        running_message: String(rawEntry.running_message || "").trim(),
        collector_mode: String(rawEntry.collector_mode || rawEntry.form_state?.collectorMode || "category").trim(),
        category: String(rawEntry.category || rawEntry.form_state?.categoryInput || "").trim(),
        seed_input: String(rawEntry.seed_input || rawEntry.form_state?.seedInput || "").trim(),
        input_label: String(rawEntry.input_label || buildExecutionInputLabel(rawEntry.form_state || {})).trim(),
        form_state: rawEntry.form_state && typeof rawEntry.form_state === "object" ? rawEntry.form_state : {},
        selection_filters: rawEntry.selection_filters && typeof rawEntry.selection_filters === "object"
            ? rawEntry.selection_filters
            : {},
        title_settings: rawEntry.title_settings && typeof rawEntry.title_settings === "object"
            ? rawEntry.title_settings
            : {},
        longtail_optional_suffix_keys: Array.isArray(rawEntry.longtail_optional_suffix_keys)
            ? [...rawEntry.longtail_optional_suffix_keys]
            : [],
        result_counts: {
            collected: Number(resultCounts.collected || 0),
            expanded: Number(resultCounts.expanded || 0),
            analyzed: Number(resultCounts.analyzed || 0),
            selected: Number(resultCounts.selected || 0),
            titled: Number(resultCounts.titled || 0),
        },
        selection_label: String(rawEntry.selection_label || "").trim(),
        title_summary: String(rawEntry.title_summary || "").trim(),
    };
}

function normalizeExecutionHistory(rawHistory) {
    const entries = Array.isArray(rawHistory?.entries)
        ? rawHistory.entries
        : Array.isArray(rawHistory)
            ? rawHistory
            : [];
    const normalizedEntries = entries
        .map((entry, index) => normalizeExecutionHistoryEntry(entry, index))
        .filter(Boolean)
        .sort((left, right) => right.recorded_at - left.recorded_at)
        .slice(0, EXECUTION_HISTORY_MAX_ENTRIES);

    return {
        version: EXECUTION_HISTORY_VERSION,
        entries: normalizedEntries,
    };
}

function readExecutionHistory() {
    return normalizeExecutionHistory(readLocalStorageJson(EXECUTION_HISTORY_STORAGE_KEY));
}

function writeExecutionHistory(history) {
    const normalized = normalizeExecutionHistory(history);
    state.executionHistory = normalized;
    try {
        window.localStorage.setItem(EXECUTION_HISTORY_STORAGE_KEY, JSON.stringify(normalized));
    } catch (error) {
        addLog("브라우저 저장소에 실행 기록을 저장하지 못했습니다.", "error");
    }
    if (getUtilityDrawerTab() === "history") {
        renderExecutionHistoryPanel();
    }
}

function getExecutionHistoryEntries() {
    return Array.isArray(state.executionHistory?.entries) ? state.executionHistory.entries : [];
}

function buildSelectionHistoryLabel() {
    if (state.results.selected?.selection_profile) {
        if (typeof buildSelectionProfileSummary === "function") {
            return String(buildSelectionProfileSummary(state.results.selected.selection_profile) || "").trim();
        }
        return String(state.results.selected.selection_profile.preset_label || "").trim();
    }
    return "";
}

function buildExecutionHistoryEntry(startedAt, stageKey, runningMessage = "") {
    const formState = typeof buildDashboardFormSnapshot === "function"
        ? buildDashboardFormSnapshot()
        : {};
    const titleSettings = typeof getTitleSettingsFormState === "function"
        ? sanitizeExecutionTitleSettings(getTitleSettingsFormState())
        : {};
    const generationMeta = state.results.titled?.generation_meta || {};
    return normalizeExecutionHistoryEntry({
        id: `history-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        recorded_at: Date.now(),
        started_at: startedAt,
        finished_stage_key: stageKey,
        finished_stage_label: formatHistoryStageLabel(stageKey),
        running_message: runningMessage,
        collector_mode: getCollectorMode?.() || "category",
        category: String(elements.categoryInput?.value || "").trim(),
        seed_input: String(elements.seedInput?.value || "").trim(),
        input_label: buildExecutionInputLabel(formState),
        form_state: formState,
        selection_filters: {
            profitability: typeof getSelectedGradeFilters === "function" ? getSelectedGradeFilters() : [],
            attackability: typeof getSelectedAttackabilityFilters === "function" ? getSelectedAttackabilityFilters() : [],
            touched: Boolean(state.gradeSelectionTouched),
        },
        title_settings: titleSettings,
        longtail_optional_suffix_keys: Array.isArray(state.longtailOptionalSuffixKeys)
            ? [...state.longtailOptionalSuffixKeys]
            : [],
        result_counts: {
            collected: countItems(state.results.collected?.collected_keywords || []),
            expanded: countItems(state.results.expanded?.expanded_keywords || []),
            analyzed: countItems(state.results.analyzed?.analyzed_keywords || []),
            selected: countItems(state.results.selected?.selected_keywords || []),
            titled: countItems(state.results.titled?.generated_titles || []),
        },
        selection_label: buildSelectionHistoryLabel(),
        title_summary: typeof buildTitleGenerationHistorySummary === "function"
            ? buildTitleGenerationHistorySummary(generationMeta, " / ")
            : (typeof buildTitleGenerationModelSummary === "function"
                ? buildTitleGenerationModelSummary(generationMeta, " / ")
                : "")
    });
}

function recordExecutionHistory(entry) {
    if (!entry) {
        return;
    }
    const entries = getExecutionHistoryEntries().filter((item) => item.id !== entry.id);
    writeExecutionHistory({
        entries: [entry, ...entries].slice(0, EXECUTION_HISTORY_MAX_ENTRIES),
    });
}

function findExecutionHistoryEntry(entryId) {
    const normalizedId = String(entryId || "").trim();
    return getExecutionHistoryEntries().find((entry) => entry.id === normalizedId) || null;
}

function clearExecutionHistory() {
    writeExecutionHistory(createEmptyExecutionHistory());
    addLog("실행 기록을 비웠습니다.", "success");
}

function applyExecutionHistoryEntry(entry) {
    if (!entry) {
        return;
    }
    if (typeof applyDashboardFormSnapshot === "function") {
        applyDashboardFormSnapshot(entry.form_state || {});
    }

    const selectionFilters = entry.selection_filters || {};
    state.selectGradeFilters = normalizeProfitabilityList(selectionFilters.profitability || PROFITABILITY_ORDER);
    state.selectAttackabilityFilters = normalizeAttackabilityList(selectionFilters.attackability || ATTACKABILITY_ORDER);
    state.gradeSelectionTouched = Boolean(selectionFilters.touched);
    if (Array.isArray(entry.longtail_optional_suffix_keys)) {
        state.longtailOptionalSuffixKeys = normalizeLongtailOptionalSuffixKeys(entry.longtail_optional_suffix_keys);
    }

    try {
        const existingSettings = readLocalStorageJson(TITLE_SETTINGS_STORAGE_KEY) || {};
        const nextSettings = {
            ...existingSettings,
            ...sanitizeExecutionTitleSettings(entry.title_settings || {}),
        };
        window.localStorage.setItem(TITLE_SETTINGS_STORAGE_KEY, JSON.stringify(nextSettings));
    } catch (error) {
        addLog("실행 기록의 제목 설정을 복원하지 못했습니다.", "error");
    }

    if (typeof loadTitleSettings === "function") {
        loadTitleSettings();
    }
    if (typeof updateGradeFilterUI === "function") {
        updateGradeFilterUI();
    }
    renderAll();
}

function formatHistoryDateTime(timestamp) {
    const numericValue = Number(timestamp || 0);
    if (!numericValue) {
        return "-";
    }
    return new Date(numericValue).toLocaleString("ko-KR", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function getFilteredExecutionHistoryEntries() {
    const search = String(elements.executionHistorySearchInput?.value || "").trim().toLowerCase();
    const limit = Number.parseInt(String(elements.executionHistoryLimitInput?.value || "20"), 10) || 20;
    const filteredEntries = getExecutionHistoryEntries().filter((entry) => {
        if (!search) {
            return true;
        }
        return [
            entry.input_label,
            entry.finished_stage_label,
            entry.category,
            entry.seed_input,
            entry.selection_label,
            entry.title_summary,
        ]
            .join(" ")
            .toLowerCase()
            .includes(search);
    });
    return filteredEntries.slice(0, Math.max(1, limit));
}

function renderExecutionHistoryCard(entry) {
    const counts = entry.result_counts || {};
    return `
        <article class="queue-item-card">
            <div class="queue-item-head">
                <div class="queue-item-title">
                    <h4>${escapeHtml(entry.input_label || "실행 기록")}</h4>
                    <p>${escapeHtml(entry.finished_stage_label || formatHistoryStageLabel(entry.finished_stage_key))}</p>
                </div>
                <span class="queue-status-pill completed">${escapeHtml(formatHistoryDateTime(entry.recorded_at))}</span>
            </div>
            <div class="queue-item-meta">
                <span>${escapeHtml(entry.collector_mode === "category" ? "카테고리 실행" : "시드 실행")}</span>
                ${entry.selection_label ? `<span>${escapeHtml(entry.selection_label)}</span>` : ""}
                ${entry.title_summary ? `<span>${escapeHtml(entry.title_summary)}</span>` : ""}
            </div>
            <div class="queue-mini-grid">
                <div class="queue-mini-stat">
                    <span>수집</span>
                    <strong>${escapeHtml(String(counts.collected || 0))}</strong>
                </div>
                <div class="queue-mini-stat">
                    <span>확장</span>
                    <strong>${escapeHtml(String(counts.expanded || 0))}</strong>
                </div>
                <div class="queue-mini-stat">
                    <span>분석</span>
                    <strong>${escapeHtml(String(counts.analyzed || 0))}</strong>
                </div>
                <div class="queue-mini-stat">
                    <span>선별</span>
                    <strong>${escapeHtml(String(counts.selected || 0))}</strong>
                </div>
            </div>
            <div class="queue-path-note">제목 ${escapeHtml(String(counts.titled || 0))}건 · ${escapeHtml(entry.running_message || "사용자 실행")}</div>
            <div class="queue-item-actions">
                <button
                    type="button"
                    class="ghost-chip"
                    data-history-action="restore"
                    data-history-id="${escapeQueueAttr(entry.id)}"
                >설정 복원</button>
                <button
                    type="button"
                    class="ghost-chip"
                    data-history-action="rerun"
                    data-history-id="${escapeQueueAttr(entry.id)}"
                >같은 단계 다시 실행</button>
                <button
                    type="button"
                    class="ghost-btn"
                    data-history-action="delete"
                    data-history-id="${escapeQueueAttr(entry.id)}"
                >삭제</button>
            </div>
        </article>
    `;
}

function renderExecutionHistoryPanel() {
    ensureWorkflowUtilityState();
    const filteredEntries = getFilteredExecutionHistoryEntries();
    const allEntries = getExecutionHistoryEntries();
    const latestEntry = allEntries[0] || null;
    const search = String(elements.executionHistorySearchInput?.value || "").trim();

    if (elements.executionHistoryCountLabel) {
        elements.executionHistoryCountLabel.textContent = `${allEntries.length}건`;
    }
    if (elements.executionHistoryLatestLabel) {
        elements.executionHistoryLatestLabel.textContent = latestEntry ? formatHistoryDateTime(latestEntry.recorded_at) : "없음";
    }
    if (elements.executionHistoryStageLabel) {
        elements.executionHistoryStageLabel.textContent = latestEntry?.finished_stage_label || "-";
    }
    if (elements.executionHistoryFilterLabel) {
        elements.executionHistoryFilterLabel.textContent = search ? `검색 ${search}` : "전체";
    }
    if (elements.executionHistoryStatus) {
        elements.executionHistoryStatus.textContent = latestEntry
            ? `마지막 기록: ${latestEntry.input_label} / ${latestEntry.finished_stage_label}`
            : "실행이 끝나면 자동으로 저장됩니다.";
    }
    if (elements.executionHistoryList) {
        elements.executionHistoryList.innerHTML = filteredEntries.length
            ? filteredEntries.map(renderExecutionHistoryCard).join("")
            : `<div class="collector-empty">${search ? "검색 조건에 맞는 실행 기록이 없습니다." : "저장된 실행 기록이 없습니다."}</div>`;
    }
}

function getHistoryRerunTask(stageKey) {
    if (stageKey === "collected" && typeof runFreshCollectFlow === "function") return runFreshCollectFlow;
    if (stageKey === "expanded" && typeof runFreshExpandFlow === "function") return runFreshExpandFlow;
    if (stageKey === "analyzed" && typeof runFreshAnalyzeFlow === "function") return runFreshAnalyzeFlow;
    if (stageKey === "selected" && typeof runFreshSelectFlow === "function") return runFreshSelectFlow;
    if (stageKey === "titled" && typeof runFreshTitleFlow === "function") return runFreshTitleFlow;
    return typeof runFreshFullFlow === "function" ? runFreshFullFlow : null;
}

async function handleExecutionHistoryActionClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-history-action]");
    if (!trigger) {
        return;
    }

    const action = String(trigger.getAttribute("data-history-action") || "").trim();
    const entry = findExecutionHistoryEntry(trigger.getAttribute("data-history-id") || "");
    if (!entry) {
        addLog("실행 기록을 찾지 못했습니다.", "error");
        return;
    }

    if (action === "restore") {
        applyExecutionHistoryEntry(entry);
        addLog(`실행 기록 설정을 복원했습니다: ${entry.input_label}`, "success");
        return;
    }

    if (action === "delete") {
        writeExecutionHistory({
            entries: getExecutionHistoryEntries().filter((item) => item.id !== entry.id),
        });
        addLog(`실행 기록을 삭제했습니다: ${entry.input_label}`, "success");
        return;
    }

    if (action === "rerun") {
        const task = getHistoryRerunTask(entry.finished_stage_key);
        if (!task) {
            addLog("이 실행 기록은 다시 실행할 수 없습니다.", "error");
            return;
        }
        applyExecutionHistoryEntry(entry);
        addLog(`실행 기록 기준으로 다시 실행합니다: ${entry.input_label}`, "info");
        await runWithGuard(task, `${entry.finished_stage_label} 다시 실행 중`);
    }
}

window.runWithGuard = async function runWithGuardOverride(task, runningMessage) {
    const startedAt = Date.now();
    const beforeFinishedAt = STAGES.reduce((map, stage) => {
        map[stage.key] = Number(state.stageStatus?.[stage.key]?.finishedAt || 0);
        return map;
    }, {});
    await originalRunWithGuard?.(task, runningMessage);
    const latestSuccess = STAGES
        .map((stage) => ({
            key: stage.key,
            finishedAt: Number(state.stageStatus?.[stage.key]?.finishedAt || 0),
            status: state.stageStatus?.[stage.key]?.state || "",
        }))
        .filter((stage) => stage.status === "success" && stage.finishedAt >= startedAt && stage.finishedAt > Number(beforeFinishedAt[stage.key] || 0))
        .sort((left, right) => right.finishedAt - left.finishedAt)[0];
    if (latestSuccess) {
        recordExecutionHistory(buildExecutionHistoryEntry(startedAt, latestSuccess.key, runningMessage));
    }
};
runWithGuard = window.runWithGuard;

function createEmptyKeywordVault() {
    return {
        version: KEYWORD_VAULT_VERSION,
        items: {},
    };
}

function normalizeKeywordVaultStatus(value) {
    const normalized = String(value || "").trim().toLowerCase();
    return KEYWORD_VAULT_STATUS_LABELS[normalized] ? normalized : "saved";
}

function normalizeKeywordVaultItem(rawItem) {
    if (!rawItem || typeof rawItem !== "object") {
        return null;
    }
    const keyword = normalizeKeywordLabel(rawItem.keyword);
    const lookupKey = normalizeKeywordLookupKey(keyword);
    if (!lookupKey) {
        return null;
    }

    return {
        keyword,
        lookup_key: lookupKey,
        status: normalizeKeywordVaultStatus(rawItem.status),
        note: String(rawItem.note || "").trim(),
        source_stage: String(rawItem.source_stage || "").trim(),
        source_label: String(rawItem.source_label || "").trim(),
        origin: String(rawItem.origin || "").trim(),
        type: String(rawItem.type || "").trim(),
        score: Number(rawItem.score || 0),
        volume: Number(rawItem.volume || 0),
        cpc: Number(rawItem.cpc || 0),
        profitability: String(rawItem.profitability || "").trim(),
        attackability: String(rawItem.attackability || "").trim(),
        saved_at: Number.parseInt(String(rawItem.saved_at ?? Date.now()), 10) || Date.now(),
        updated_at: Number.parseInt(String(rawItem.updated_at ?? Date.now()), 10) || Date.now(),
    };
}

function normalizeKeywordVault(rawVault) {
    const itemEntries = Array.isArray(rawVault?.items)
        ? rawVault.items
        : rawVault?.items && typeof rawVault.items === "object"
            ? Object.values(rawVault.items)
            : Array.isArray(rawVault)
                ? rawVault
                : [];
    const items = {};
    itemEntries.forEach((entry) => {
        const normalizedEntry = normalizeKeywordVaultItem(entry);
        if (!normalizedEntry) {
            return;
        }
        items[normalizedEntry.lookup_key] = normalizedEntry;
    });
    return {
        version: KEYWORD_VAULT_VERSION,
        items,
    };
}

function readKeywordVault() {
    return normalizeKeywordVault(readLocalStorageJson(KEYWORD_VAULT_STORAGE_KEY));
}

function writeKeywordVault(vault) {
    const normalized = normalizeKeywordVault(vault);
    state.keywordVault = normalized;
    try {
        window.localStorage.setItem(KEYWORD_VAULT_STORAGE_KEY, JSON.stringify(normalized));
    } catch (error) {
        addLog("브라우저 저장소에 키워드 보관함을 저장하지 못했습니다.", "error");
    }
    if (getUtilityDrawerTab() === "vault") {
        renderKeywordVaultPanel();
    }
}

function getKeywordVaultItems() {
    const items = state.keywordVault?.items && typeof state.keywordVault.items === "object"
        ? Object.values(state.keywordVault.items)
        : [];
    return items.sort((left, right) => Number(right.updated_at || 0) - Number(left.updated_at || 0));
}

function findKeywordItemForVault(keyword, sourceStage = "") {
    const normalizedKeyword = normalizeKeywordLabel(keyword);
    if (!normalizedKeyword) {
        return null;
    }
    const selectors = [];
    if (sourceStage === "selected") {
        selectors.push(state.results.selected?.selected_keywords || []);
    }
    if (sourceStage === "analyzed") {
        selectors.push(state.results.analyzed?.analyzed_keywords || []);
    }
    selectors.push(state.results.selected?.selected_keywords || []);
    selectors.push(state.results.analyzed?.analyzed_keywords || []);

    for (const items of selectors) {
        const matched = (items || []).find((item) => normalizeKeywordLabel(item?.keyword) === normalizedKeyword);
        if (matched) {
            return matched;
        }
    }
    return null;
}

function buildKeywordVaultEntry(keyword, sourceStage = "", explicitItem = null) {
    const sourceItem = explicitItem || findKeywordItemForVault(keyword, sourceStage);
    const normalizedKeyword = normalizeKeywordLabel(sourceItem?.keyword || keyword);
    const existingEntry = state.keywordVault?.items?.[normalizeKeywordLookupKey(normalizedKeyword)] || null;
    const now = Date.now();
    return normalizeKeywordVaultItem({
        keyword: normalizedKeyword,
        status: existingEntry?.status || "saved",
        note: existingEntry?.note || "",
        source_stage: sourceStage || existingEntry?.source_stage || "",
        source_label: formatHistoryStageLabel(sourceStage || existingEntry?.source_stage || ""),
        origin: String(sourceItem?.origin || existingEntry?.origin || "").trim(),
        type: String(sourceItem?.type || existingEntry?.type || "").trim(),
        score: Number(sourceItem?.score || existingEntry?.score || 0),
        volume: Number(sourceItem?.metrics?.volume || existingEntry?.volume || 0),
        cpc: Number(sourceItem?.metrics?.cpc || existingEntry?.cpc || 0),
        profitability: typeof resolveProfitabilityGrade === "function"
            ? resolveProfitabilityGrade(sourceItem || {})
            : (existingEntry?.profitability || ""),
        attackability: typeof resolveAttackabilityGrade === "function"
            ? resolveAttackabilityGrade(sourceItem || {})
            : (existingEntry?.attackability || ""),
        saved_at: existingEntry?.saved_at || now,
        updated_at: now,
    });
}

function saveKeywordToVault(keyword, sourceStage = "", explicitItem = null) {
    const entry = buildKeywordVaultEntry(keyword, sourceStage, explicitItem);
    if (!entry) {
        return null;
    }
    writeKeywordVault({
        items: {
            ...(state.keywordVault?.items || {}),
            [entry.lookup_key]: entry,
        },
    });
    return entry;
}

function saveKeywordsToVault(items, sourceStage = "") {
    const safeItems = Array.isArray(items) ? items : [];
    let savedCount = 0;
    const nextItems = { ...(state.keywordVault?.items || {}) };
    safeItems.forEach((item) => {
        const entry = buildKeywordVaultEntry(item?.keyword, sourceStage, item);
        if (!entry) {
            return;
        }
        nextItems[entry.lookup_key] = entry;
        savedCount += 1;
    });
    if (savedCount > 0) {
        writeKeywordVault({ items: nextItems });
    }
    return savedCount;
}

function clearKeywordVault() {
    writeKeywordVault(createEmptyKeywordVault());
    addLog("키워드 보관함을 비웠습니다.", "success");
}

function getFilteredKeywordVaultItems() {
    const search = String(elements.keywordVaultSearchInput?.value || "").trim().toLowerCase();
    const statusFilter = String(elements.keywordVaultStatusFilter?.value || "all").trim().toLowerCase();
    return getKeywordVaultItems().filter((item) => {
        if (statusFilter !== "all" && item.status !== statusFilter) {
            return false;
        }
        if (!search) {
            return true;
        }
        return [
            item.keyword,
            item.note,
            item.source_label,
            item.origin,
            item.type,
        ].join(" ").toLowerCase().includes(search);
    });
}

function renderVaultStatusOptions(selectedValue) {
    const normalizedValue = normalizeKeywordVaultStatus(selectedValue);
    return KEYWORD_VAULT_STATUS_OPTIONS.map((option) => `
        <option value="${escapeHtml(option.value)}"${option.value === normalizedValue ? " selected" : ""}>${escapeHtml(option.label)}</option>
    `).join("");
}

function renderKeywordVaultCard(item) {
    const metaParts = [
        item.source_label || "",
        item.profitability ? `수익성 ${item.profitability}` : "",
        item.attackability ? `노출도 ${item.attackability}` : "",
        item.cpc ? `CPC ${formatNumber(item.cpc)}` : "",
        item.volume ? `검색량 ${formatNumber(item.volume)}` : "",
    ].filter(Boolean);
    return `
        <article class="queue-item-card">
            <div class="queue-item-head">
                <div class="queue-item-title">
                    <h4>${escapeHtml(item.keyword)}</h4>
                    <p>${escapeHtml(metaParts.join(" / ") || "보관된 키워드")}</p>
                </div>
                <span class="queue-status-pill ${escapeQueueAttr(item.status)}">${escapeHtml(KEYWORD_VAULT_STATUS_LABELS[item.status] || "보관")}</span>
            </div>
            <div class="queue-item-meta">
                <span>저장 ${escapeHtml(formatHistoryDateTime(item.saved_at))}</span>
                <span>수정 ${escapeHtml(formatHistoryDateTime(item.updated_at))}</span>
                ${item.origin ? `<span>원본 ${escapeHtml(item.origin)}</span>` : ""}
            </div>
            <div class="settings-form-grid keyword-vault-edit-grid">
                <label class="field-block">
                    <span class="field-label">상태</span>
                    <select data-vault-status="${escapeQueueAttr(item.lookup_key)}">
                        ${renderVaultStatusOptions(item.status)}
                    </select>
                </label>
                <label class="field-block field-block-wide">
                    <span class="field-label">메모</span>
                    <input
                        type="text"
                        value="${escapeHtml(item.note)}"
                        placeholder="예: 자동 발행 전 수동 확인"
                        data-vault-note="${escapeQueueAttr(item.lookup_key)}"
                    />
                </label>
            </div>
            <div class="queue-item-actions">
                <button
                    type="button"
                    class="ghost-chip"
                    data-vault-action="use-seed"
                    data-vault-key="${escapeQueueAttr(item.lookup_key)}"
                >시드 입력</button>
                <button
                    type="button"
                    class="ghost-chip"
                    data-vault-action="run-seed"
                    data-vault-key="${escapeQueueAttr(item.lookup_key)}"
                >시드로 수집</button>
                <button
                    type="button"
                    class="ghost-btn"
                    data-vault-action="delete"
                    data-vault-key="${escapeQueueAttr(item.lookup_key)}"
                >삭제</button>
            </div>
        </article>
    `;
}

function renderKeywordVaultPanel() {
    ensureWorkflowUtilityState();
    const filteredItems = getFilteredKeywordVaultItems();
    const allItems = getKeywordVaultItems();
    const quickAddCount = parseQueueListText(elements.keywordVaultQuickAddInput?.value || "").length;
    const publishedCount = allItems.filter((item) => item.status === "published").length;
    const draftCount = allItems.filter((item) => item.status === "draft" || item.status === "hold").length;
    const search = String(elements.keywordVaultSearchInput?.value || "").trim();
    const statusFilter = String(elements.keywordVaultStatusFilter?.value || "all").trim();

    if (elements.keywordVaultCountLabel) {
        elements.keywordVaultCountLabel.textContent = `${allItems.length}건`;
    }
    if (elements.keywordVaultPublishedCountLabel) {
        elements.keywordVaultPublishedCountLabel.textContent = `${publishedCount}건`;
    }
    if (elements.keywordVaultDraftCountLabel) {
        elements.keywordVaultDraftCountLabel.textContent = `${draftCount}건`;
    }
    if (elements.keywordVaultFilterLabel) {
        elements.keywordVaultFilterLabel.textContent = search || statusFilter !== "all"
            ? `${statusFilter === "all" ? "검색" : KEYWORD_VAULT_STATUS_LABELS[statusFilter] || statusFilter}${search ? ` / ${search}` : ""}`
            : "전체";
    }
    if (elements.keywordVaultQuickAddCountLabel) {
        elements.keywordVaultQuickAddCountLabel.textContent = `${quickAddCount}건 준비`;
    }
    if (elements.keywordVaultStatus) {
        elements.keywordVaultStatus.textContent = allItems.length
            ? `보관함 ${allItems.length}건 / 현재 표시 ${filteredItems.length}건`
            : "결과 표의 `보관` 버튼이나 직접 입력으로 키워드를 추가해 주세요.";
    }
    if (elements.keywordVaultList) {
        elements.keywordVaultList.innerHTML = filteredItems.length
            ? filteredItems.map(renderKeywordVaultCard).join("")
            : `<div class="collector-empty">${allItems.length ? "검색 조건에 맞는 키워드가 없습니다." : "보관된 키워드가 없습니다."}</div>`;
    }
}

function handleKeywordVaultQuickAdd() {
    const keywords = parseQueueListText(elements.keywordVaultQuickAddInput?.value || "");
    if (!keywords.length) {
        addLog("보관함에 추가할 키워드를 1개 이상 입력해 주세요.", "error");
        return;
    }
    const nextItems = { ...(state.keywordVault?.items || {}) };
    keywords.forEach((keyword) => {
        const entry = buildKeywordVaultEntry(keyword, "manual");
        if (!entry) {
            return;
        }
        nextItems[entry.lookup_key] = entry;
    });
    writeKeywordVault({ items: nextItems });
    if (elements.keywordVaultQuickAddInput) {
        elements.keywordVaultQuickAddInput.value = "";
    }
    renderKeywordVaultPanel();
    addLog(`키워드 ${keywords.length}건을 보관함에 추가했습니다.`, "success");
}

function findKeywordVaultItem(lookupKey) {
    const normalizedKey = String(lookupKey || "").trim();
    return state.keywordVault?.items?.[normalizedKey] || null;
}

function useKeywordVaultItemAsSeed(item, runCollect = false) {
    if (!item) {
        return;
    }
    document.querySelectorAll("input[name='collectorMode']").forEach((radio) => {
        radio.checked = radio.value === "seed";
    });
    if (elements.seedInput) {
        elements.seedInput.value = item.keyword;
    }
    renderInputState();
    renderAll();
    if (runCollect) {
        void runWithGuard(runFreshCollectFlow, `시드 ${item.keyword} 수집 실행 중`);
    }
}

function handleKeywordVaultListClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-vault-action]");
    if (!trigger) {
        return;
    }

    const action = String(trigger.getAttribute("data-vault-action") || "").trim();
    const item = findKeywordVaultItem(trigger.getAttribute("data-vault-key") || "");
    if (!item) {
        addLog("보관함 항목을 찾지 못했습니다.", "error");
        return;
    }

    if (action === "delete") {
        const nextItems = { ...(state.keywordVault?.items || {}) };
        delete nextItems[item.lookup_key];
        writeKeywordVault({ items: nextItems });
        addLog(`보관함에서 삭제했습니다: ${item.keyword}`, "success");
        return;
    }

    if (action === "use-seed") {
        useKeywordVaultItemAsSeed(item, false);
        addLog(`시드 입력으로 가져왔습니다: ${item.keyword}`, "success");
        return;
    }

    if (action === "run-seed") {
        useKeywordVaultItemAsSeed(item, true);
    }
}

function handleKeywordVaultListChange(event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) {
        return;
    }

    const vaultStatusKey = target.dataset.vaultStatus || "";
    if (vaultStatusKey) {
        const item = findKeywordVaultItem(vaultStatusKey);
        if (!item) {
            return;
        }
        const nextItem = normalizeKeywordVaultItem({
            ...item,
            status: target.value,
            updated_at: Date.now(),
        });
        writeKeywordVault({
            items: {
                ...(state.keywordVault?.items || {}),
                [nextItem.lookup_key]: nextItem,
            },
        });
        if (nextItem.status === "published") {
            setKeywordStatus(nextItem.keyword, "published");
        }
        addLog(`보관함 상태를 바꿨습니다: ${nextItem.keyword} / ${KEYWORD_VAULT_STATUS_LABELS[nextItem.status]}`, "success");
    }
}

function handleKeywordVaultListInput(event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
        return;
    }
    const vaultNoteKey = target.dataset.vaultNote || "";
    if (!vaultNoteKey) {
        return;
    }
    const item = findKeywordVaultItem(vaultNoteKey);
    if (!item) {
        return;
    }
    const nextItem = normalizeKeywordVaultItem({
        ...item,
        note: target.value,
        updated_at: Date.now(),
    });
    writeKeywordVault({
        items: {
            ...(state.keywordVault?.items || {}),
            [nextItem.lookup_key]: nextItem,
        },
    });
}

function renderVaultInlineAction(keyword, sourceStage) {
    return `
        <button
            type="button"
            class="ghost-chip keyword-vault-inline-btn"
            data-inline-action="save_to_vault"
            data-keyword="${escapeHtml(String(keyword || "").trim())}"
            data-vault-stage="${escapeHtml(String(sourceStage || "").trim())}"
        >보관</button>
    `;
}

function handleVaultResultActionClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-inline-action]");
    if (!trigger) {
        return;
    }
    const action = String(trigger.getAttribute("data-inline-action") || "").trim();
    if (action === "save_to_vault") {
        const keyword = String(trigger.getAttribute("data-keyword") || "").trim();
        const sourceStage = String(trigger.getAttribute("data-vault-stage") || "").trim();
        const entry = saveKeywordToVault(keyword, sourceStage);
        if (entry) {
            addLog(`키워드를 보관함에 저장했습니다: ${entry.keyword}`, "success");
        }
        return;
    }
    if (action === "save_visible_analyzed_to_vault") {
        const items = applyAnalyzedFilters(state.results.analyzed?.analyzed_keywords || []);
        const savedCount = saveKeywordsToVault(items, "analyzed");
        addLog(`분석 표의 표시 목록 ${savedCount}건을 보관함에 저장했습니다.`, "success");
        return;
    }
    if (action === "save_selected_to_vault") {
        const items = state.results.selected?.selected_keywords || [];
        const savedCount = saveKeywordsToVault(items, "selected");
        addLog(`선별 결과 ${savedCount}건을 보관함에 저장했습니다.`, "success");
    }
}

function renderTopicSeedSuggestions() {
    const suggestions = Array.isArray(state.topicSeedSuggestions) ? state.topicSeedSuggestions : [];
    const meta = state.topicSeedMeta || {};
    const pending = Boolean(state.topicSeedRequestPending);
    if (elements.generateTopicSeedsButton) {
        elements.generateTopicSeedsButton.disabled = pending || state.isBusy;
        elements.generateTopicSeedsButton.textContent = pending ? "생성 중..." : "시드 만들기";
    }
    if (elements.topicSeedStatus) {
        if (pending) {
            elements.topicSeedStatus.textContent = "주제에서 시작용 시드를 만드는 중입니다.";
        } else if (suggestions.length) {
            const providerLabel = meta.provider ? formatTitleProviderLabel(meta.provider) : "AI";
            elements.topicSeedStatus.textContent = `${TOPIC_SEED_INTENT_LABELS[meta.intent] || "균형형"} / ${providerLabel} / ${meta.model || ""} 기준으로 ${suggestions.length}개를 만들었습니다.`;
        } else if (meta.error_message) {
            elements.topicSeedStatus.textContent = String(meta.error_message);
        } else {
            elements.topicSeedStatus.textContent = "아직 주제 시드를 만들지 않았습니다.";
        }
    }
    if (elements.topicSeedSuggestionList) {
        elements.topicSeedSuggestionList.innerHTML = suggestions.length
            ? suggestions.map((seedKeyword, index) => `
                <div class="topic-seed-suggestion-card">
                    <strong>${escapeHtml(seedKeyword)}</strong>
                    <div class="topic-seed-suggestion-actions">
                        <button
                            type="button"
                            class="ghost-chip"
                            data-topic-seed-action="use"
                            data-topic-seed="${escapeHtml(seedKeyword)}"
                        >시드 입력</button>
                        <button
                            type="button"
                            class="ghost-chip"
                            data-topic-seed-action="collect"
                            data-topic-seed="${escapeHtml(seedKeyword)}"
                        >바로 수집</button>
                        ${index < 5 ? `
                            <button
                                type="button"
                                class="ghost-chip"
                                data-topic-seed-action="vault"
                                data-topic-seed="${escapeHtml(seedKeyword)}"
                            >보관</button>
                        ` : ""}
                    </div>
                </div>
            `).join("")
            : "";
    }
}

function buildTopicSeedTitleOptions() {
    const registry = readTitleApiRegistry();
    const formState = typeof getTitleSettingsFormState === "function" ? getTitleSettingsFormState() : {};
    const provider = ensureRegisteredTitleProvider(formState.provider, registry);
    if (!provider) {
        throw new Error("먼저 운영 설정에서 AI API를 등록해 주세요.");
    }
    return {
        mode: "ai",
        provider,
        model: String(formState.model || TITLE_PROVIDER_DEFAULT_MODELS[provider] || "").trim() || TITLE_PROVIDER_DEFAULT_MODELS[provider],
        api_key: getTitleApiKeyForProvider(provider, registry),
        temperature: String(formState.temperature || TITLE_TEMPERATURE_DEFAULT),
    };
}

async function generateTopicSeedSuggestions() {
    const topic = String(elements.topicSeedInput?.value || "").trim();
    if (!topic) {
        addLog("주제 시드를 만들 주제를 입력해 주세요.", "error");
        return;
    }
    const requestedCount = Number.parseInt(String(elements.topicSeedCount?.value || "12"), 10) || 12;
    const intent = String(elements.topicSeedIntent?.value || "balanced").trim();
    const titleOptions = buildTopicSeedTitleOptions();

    state.topicSeedRequestPending = true;
    state.topicSeedMeta = { topic, intent, provider: titleOptions.provider, model: titleOptions.model, error_message: "" };
    renderTopicSeedSuggestions();
    try {
        const response = await postModule("/topic-seeds", {
            topic,
            intent,
            count: requestedCount,
            title_options: titleOptions,
        });
        const result = response.result || {};
        const keywords = Array.isArray(result.seed_keywords)
            ? result.seed_keywords.map((value) => String(value || "").trim()).filter(Boolean)
            : [];
        if (!keywords.length) {
            throw new Error("주제에서 시드 후보를 만들지 못했습니다.");
        }
        state.topicSeedSuggestions = keywords;
        state.topicSeedMeta = {
            topic,
            intent,
            provider: String(result.provider || titleOptions.provider).trim(),
            model: String(result.model || titleOptions.model).trim(),
            error_message: "",
        };
        addLog(`주제 시드 ${keywords.length}건을 만들었습니다: ${topic}`, "success");
    } catch (error) {
        const normalizedError = normalizeError(error, { endpoint: "/topic-seeds" });
        state.topicSeedSuggestions = [];
        state.topicSeedMeta = {
            ...state.topicSeedMeta,
            error_message: normalizedError.message,
        };
        addLog(normalizedError.message, "error");
    } finally {
        state.topicSeedRequestPending = false;
        renderTopicSeedSuggestions();
    }
}

function useTopicSeedKeyword(seedKeyword, shouldCollect = false) {
    const keyword = String(seedKeyword || "").trim();
    if (!keyword) {
        return;
    }
    document.querySelectorAll("input[name='collectorMode']").forEach((radio) => {
        radio.checked = radio.value === "seed";
    });
    if (elements.seedInput) {
        elements.seedInput.value = keyword;
    }
    renderInputState();
    renderAll();
    if (shouldCollect) {
        void runWithGuard(runFreshCollectFlow, `주제 시드 ${keyword} 수집 실행 중`);
    }
}

function handleTopicSeedSuggestionClick(event) {
    if (!(event.target instanceof Element)) {
        return;
    }
    const trigger = event.target.closest("[data-topic-seed-action]");
    if (!trigger) {
        return;
    }
    const action = String(trigger.getAttribute("data-topic-seed-action") || "").trim();
    const seedKeyword = String(trigger.getAttribute("data-topic-seed") || "").trim();
    if (!seedKeyword) {
        return;
    }
    if (action === "use") {
        useTopicSeedKeyword(seedKeyword, false);
        addLog(`주제 시드를 시드 입력으로 넣었습니다: ${seedKeyword}`, "success");
        return;
    }
    if (action === "collect") {
        useTopicSeedKeyword(seedKeyword, true);
        return;
    }
    if (action === "vault") {
        const entry = saveKeywordToVault(seedKeyword, "topic_seed");
        if (entry) {
            addLog(`주제 시드를 보관함에 저장했습니다: ${seedKeyword}`, "success");
        }
    }
}


