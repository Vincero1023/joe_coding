const 상태 = {
    collected: null,
    expanded: null,
    analyzed: null,
    selected: null,
    titled: null,
};

const 단계설정 = [
    { key: "collected", 제목: "1단계 수집", 설명: "카테고리 또는 시드 기준으로 원본 키워드를 모읍니다." },
    { key: "expanded", 제목: "2단계 확장", 설명: "자동완성과 규칙 엔진으로 확장 키워드를 만듭니다." },
    { key: "analyzed", 제목: "3단계 분석", 설명: "CPC, 입찰가, 경쟁도, 기회 점수로 수익성을 평가합니다." },
    { key: "selected", 제목: "4단계 선별", 설명: "실제 수익 가능성이 있는 골든 키워드만 남깁니다." },
    { key: "titled", 제목: "5단계 제목 생성", 설명: "네이버 홈형과 블로그형 제목을 각각 2개씩 만듭니다." },
];

const 요소 = {};

document.addEventListener("DOMContentLoaded", () => {
    요소.categoryInput = document.getElementById("categoryInput");
    요소.seedInput = document.getElementById("seedInput");
    요소.collectorAnalysisPath = document.getElementById("collectorAnalysisPath");
    요소.expanderAnalysisPath = document.getElementById("expanderAnalysisPath");
    요소.optionRelated = document.getElementById("optionRelated");
    요소.optionAutocomplete = document.getElementById("optionAutocomplete");
    요소.optionBulk = document.getElementById("optionBulk");
    요소.statusList = document.getElementById("statusList");
    요소.resultsGrid = document.getElementById("resultsGrid");
    요소.activityLog = document.getElementById("activityLog");
    요소.pipelineStatus = document.getElementById("pipelineStatus");

    document.getElementById("runCollectButton").addEventListener("click", () => 실행보호(수집실행, "수집 단계 실행 중"));
    document.getElementById("runExpandButton").addEventListener("click", () => 실행보호(확장까지실행, "확장 단계 실행 중"));
    document.getElementById("runAnalyzeButton").addEventListener("click", () => 실행보호(분석까지실행, "분석 단계 실행 중"));
    document.getElementById("runSelectButton").addEventListener("click", () => 실행보호(선별까지실행, "골든 키워드 선별 중"));
    document.getElementById("runTitleButton").addEventListener("click", () => 실행보호(제목까지실행, "제목 생성 단계 실행 중"));
    document.getElementById("runFullButton").addEventListener("click", () => 실행보호(전체실행, "전체 파이프라인 실행 중"));
    document.getElementById("resetButton").addEventListener("click", 결과초기화);

    document.querySelectorAll("[data-preset]").forEach((button) => {
        button.addEventListener("click", () => 예시설정(button.dataset.preset || "finance"));
    });

    로그추가("웹 인터페이스가 준비되었습니다. 전체 흐름 실행 또는 단계별 실행을 선택하세요.", "success");
    상태렌더();
});

async function 실행보호(작업함수, 상태문구) {
    try {
        상태표시(상태문구, "running");
        await 작업함수();
        상태표시("실행 완료", "success");
    } catch (error) {
        console.error(error);
        상태표시("오류 발생", "error");
        로그추가(error.message || "알 수 없는 오류가 발생했습니다.", "error");
    }
}

function 결과초기화() {
    상태.collected = null;
    상태.expanded = null;
    상태.analyzed = null;
    상태.selected = null;
    상태.titled = null;
    상태렌더();
    상태표시("대기 중", "idle");
    로그추가("화면의 결과를 비웠습니다.");
}

function 예시설정(종류) {
    const 예시맵 = {
        finance: { mode: "category", category: "비즈니스경제", seed: "보험" },
        travel: { mode: "seed", category: "", seed: "제주 여행" },
        food: { mode: "seed", category: "", seed: "성심당" },
    };

    const 예시 = 예시맵[종류] || 예시맵.finance;
    const 선택기 = `input[name="collectorMode"][value="${예시.mode}"]`;
    const 라디오 = document.querySelector(선택기);
    if (라디오) 라디오.checked = true;
    요소.categoryInput.value = 예시.category;
    요소.seedInput.value = 예시.seed;

    document.querySelectorAll("[data-preset]").forEach((button) => {
        button.classList.toggle("active", button.dataset.preset === 종류);
    });

    로그추가(`${표시용예시이름(종류)} 예시를 입력값에 반영했습니다.`, "success");
}

function 표시용예시이름(종류) {
    if (종류 === "travel") return "여행";
    if (종류 === "food") return "맛집";
    return "금융";
}

async function 전체실행() {
    await 수집실행();
    await 확장실행();
    await 분석실행();
    await 선별실행();
    await 제목실행();
    로그추가("전체 파이프라인이 모두 끝났습니다.", "success");
}

async function 확장까지실행() {
    await 수집실행();
    await 확장실행();
}

async function 분석까지실행() {
    await 수집실행();
    await 확장실행();
    await 분석실행();
}

async function 선별까지실행() {
    await 수집실행();
    await 확장실행();
    await 분석실행();
    await 선별실행();
}

async function 제목까지실행() {
    await 수집실행();
    await 확장실행();
    await 분석실행();
    await 선별실행();
    await 제목실행();
}

async function 수집실행() {
    const 입력값 = 수집입력구성();
    const 기준 = 입력값.mode === "category"
        ? `카테고리 ${입력값.category || "미입력"}`
        : `시드 ${입력값.seed_input || "미입력"}`;

    로그추가(`수집 시작: ${기준}`);
    상태.collected = await 모듈호출("/collect", 입력값);
    상태.expanded = null;
    상태.analyzed = null;
    상태.selected = null;
    상태.titled = null;
    상태렌더();
    로그추가(`수집 완료: ${개수읽기(상태.collected.collected_keywords)}건`, "success");
}

async function 확장실행() {
    if (!상태.collected) await 수집실행();
    로그추가("확장 시작: 수집된 키워드를 바탕으로 확장합니다.");
    상태.expanded = await 모듈호출("/expand", {
        collected_keywords: 상태.collected.collected_keywords || [],
        analysis_json_path: 요소.expanderAnalysisPath.value.trim(),
    });
    상태.analyzed = null;
    상태.selected = null;
    상태.titled = null;
    상태렌더();
    로그추가(`확장 완료: ${개수읽기(상태.expanded.expanded_keywords)}건`, "success");
}

async function 분석실행() {
    if (!상태.expanded) await 확장실행();
    로그추가("분석 시작: 수익성과 기회 점수를 계산합니다.");
    상태.analyzed = await 모듈호출("/analyze", {
        expanded_keywords: 상태.expanded.expanded_keywords || [],
    });
    상태.selected = null;
    상태.titled = null;
    상태렌더();
    로그추가(`분석 완료: ${개수읽기(상태.analyzed.analyzed_keywords)}건`, "success");
}

async function 선별실행() {
    if (!상태.analyzed) await 분석실행();
    로그추가("선별 시작: 골든 키워드 조건을 적용합니다.");
    상태.selected = await 모듈호출("/select", {
        analyzed_keywords: 상태.analyzed.analyzed_keywords || [],
    });
    상태.titled = null;
    상태렌더();
    로그추가(`선별 완료: ${개수읽기(상태.selected.selected_keywords)}건`, "success");
}

async function 제목실행() {
    if (!상태.selected) await 선별실행();
    로그추가("제목 생성 시작: CTR 중심 제목을 만듭니다.");
    상태.titled = await 모듈호출("/generate-title", {
        selected_keywords: 상태.selected.selected_keywords || [],
    });
    상태렌더();
    로그추가(`제목 생성 완료: ${개수읽기(상태.titled.generated_titles)}세트`, "success");
}

async function 모듈호출(주소, 입력값) {
    const 응답 = await fetch(주소, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_data: 입력값 }),
    });

    if (!응답.ok) {
        const 본문 = await 응답.text();
        throw new Error(`요청 실패 (${응답.status}): ${본문}`);
    }

    const 데이터 = await 응답.json();
    return 데이터.result || {};
}

function 수집입력구성() {
    return {
        mode: 현재모드읽기(),
        category: 요소.categoryInput.value.trim(),
        seed_input: 요소.seedInput.value.trim(),
        options: {
            collect_related: 요소.optionRelated.checked,
            collect_autocomplete: 요소.optionAutocomplete.checked,
            collect_bulk: 요소.optionBulk.checked,
        },
        analysis_json_path: 요소.collectorAnalysisPath.value.trim(),
    };
}

function 현재모드읽기() {
    const 선택 = document.querySelector("input[name='collectorMode']:checked");
    return 선택 ? 선택.value : "category";
}

function 상태렌더() {
    상태카운트반영();
    상태목록렌더();
    결과렌더();
}

function 상태카운트반영() {
    document.getElementById("countCollected").textContent = 개수읽기(상태.collected?.collected_keywords);
    document.getElementById("countExpanded").textContent = 개수읽기(상태.expanded?.expanded_keywords);
    document.getElementById("countAnalyzed").textContent = 개수읽기(상태.analyzed?.analyzed_keywords);
    document.getElementById("countSelected").textContent = 개수읽기(상태.selected?.selected_keywords);
    document.getElementById("countTitled").textContent = 개수읽기(상태.titled?.generated_titles);
}

function 상태목록렌더() {
    const 맵 = {
        collected: 개수읽기(상태.collected?.collected_keywords),
        expanded: 개수읽기(상태.expanded?.expanded_keywords),
        analyzed: 개수읽기(상태.analyzed?.analyzed_keywords),
        selected: 개수읽기(상태.selected?.selected_keywords),
        titled: 개수읽기(상태.titled?.generated_titles),
    };

    요소.statusList.innerHTML = 단계설정.map((단계) => {
        const 완료 = 맵[단계.key] > 0;
        const 텍스트 = 완료 ? `${맵[단계.key]}건 준비됨` : "아직 실행 전";
        return `
            <div class="status-item">
                <div>
                    <strong>${단계.제목}</strong>
                    <span>${단계.설명}</span>
                </div>
                <div class="badge">${텍스트}</div>
            </div>
        `;
    }).join("");
}

function 결과렌더() {
    const 카드목록 = [];

    if (상태.collected?.collected_keywords) 카드목록.push(결과카드("수집 키워드", 상태.collected.collected_keywords, 수집목록HTML));
    if (상태.expanded?.expanded_keywords) 카드목록.push(결과카드("확장 키워드", 상태.expanded.expanded_keywords, 확장목록HTML));
    if (상태.analyzed?.analyzed_keywords) 카드목록.push(결과카드("분석 결과", 상태.analyzed.analyzed_keywords, 분석목록HTML));
    if (상태.selected?.selected_keywords) 카드목록.push(결과카드("골든 키워드", 상태.selected.selected_keywords, 선별목록HTML));
    if (상태.titled?.generated_titles) 카드목록.push(결과카드("생성된 제목", 상태.titled.generated_titles, 제목목록HTML));

    요소.resultsGrid.innerHTML = 카드목록.length > 0
        ? 카드목록.join("")
        : `
            <div class="placeholder">
                입력값을 조정한 뒤 실행 버튼을 누르면 여기에서 단계별 결과를 확인할 수 있습니다.<br />
                카테고리 모드는 트렌드 섹션 기반 수집에 적합하고, 시드 모드는 특정 키워드를 중심으로 흐름을 좁혀 볼 때 적합합니다.
            </div>
        `;
}

function 결과카드(제목, 목록, 렌더함수) {
    return `
        <article class="result-card">
            <div class="result-head">
                <h3>${제목}</h3>
                <span class="result-count">총 ${개수읽기(목록)}건</span>
            </div>
            ${렌더함수(목록.slice(0, 8))}
        </article>
    `;
}

function 수집목록HTML(목록) {
    return `<div class="keyword-list">${목록.map((항목) => `
        <div class="keyword-item">
            <div class="keyword-main">
                <strong>${항목.keyword || "-"}</strong>
                <span class="score-line">${항목.source || "출처 없음"}</span>
            </div>
            <div class="keyword-meta">
                <span class="badge">카테고리 ${항목.category || "미분류"}</span>
                <span class="badge">원문 ${항목.raw || "-"}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function 확장목록HTML(목록) {
    return `<div class="keyword-list">${목록.map((항목) => `
        <div class="keyword-item">
            <div class="keyword-main">
                <strong>${항목.keyword || "-"}</strong>
                <span class="score-line">원본 ${항목.origin || "-"}</span>
            </div>
            <div class="keyword-meta">
                <span class="badge">유형 ${항목.type || "미정"}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function 분석목록HTML(목록) {
    return `<div class="metric-list">${목록.map((항목) => `
        <div class="metric-item">
            <div class="keyword-main">
                <strong>${항목.keyword || "-"}</strong>
                <span class="badge priority-${항목.priority || "low"}">${우선순위이름(항목.priority)}</span>
            </div>
            <div class="metric-meta">
                <span class="badge">점수 ${숫자포맷(항목.score)}</span>
                <span class="badge">CPC ${숫자포맷(항목.metrics?.cpc)}</span>
                <span class="badge">입찰 ${숫자포맷(항목.metrics?.bid)}</span>
                <span class="badge">경쟁 ${숫자포맷(항목.metrics?.competition)}</span>
                <span class="badge">기회 ${숫자포맷(항목.metrics?.opportunity)}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function 선별목록HTML(목록) {
    return `<div class="keyword-list">${목록.map((항목) => `
        <div class="keyword-item">
            <div class="keyword-main">
                <strong>${항목.keyword || "-"}</strong>
                <span class="score-line">수익 점수 ${숫자포맷(항목.score)}</span>
            </div>
            <div class="keyword-meta">
                <span class="badge">CPC ${숫자포맷(항목.metrics?.cpc)}</span>
                <span class="badge">입찰 ${숫자포맷(항목.metrics?.bid)}</span>
                <span class="badge">조회 ${숫자포맷(항목.metrics?.volume)}</span>
                <span class="badge">경쟁 ${숫자포맷(항목.metrics?.competition)}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function 제목목록HTML(목록) {
    return `<div class="title-list">${목록.map((항목) => `
        <div class="title-item">
            <div class="title-keyword">
                <strong>${항목.keyword || "-"}</strong>
                <span class="badge">제목 4개 세트</span>
            </div>
            <div class="title-columns">
                <div class="title-column">
                    <h4>네이버 홈형</h4>
                    <ul>${(항목.titles?.naver_home || []).map((제목) => `<li>${제목}</li>`).join("") || "<li>생성 결과 없음</li>"}</ul>
                </div>
                <div class="title-column">
                    <h4>블로그형</h4>
                    <ul>${(항목.titles?.blog || []).map((제목) => `<li>${제목}</li>`).join("") || "<li>생성 결과 없음</li>"}</ul>
                </div>
            </div>
        </div>
    `).join("")}</div>`;
}

function 우선순위이름(값) {
    if (값 === "high") return "높음";
    if (값 === "medium") return "중간";
    return "낮음";
}

function 숫자포맷(값) {
    const 숫자 = Number(값 ?? 0);
    if (!Number.isFinite(숫자)) return "0";
    return 숫자.toFixed(2).replace(/\.00$/, "");
}

function 개수읽기(목록) {
    return Array.isArray(목록) ? 목록.length : 0;
}

function 상태표시(문구, 종류) {
    요소.pipelineStatus.textContent = 문구;
    요소.pipelineStatus.classList.remove("running", "error");
    if (종류 === "running") 요소.pipelineStatus.classList.add("running");
    if (종류 === "error") 요소.pipelineStatus.classList.add("error");
}

function 로그추가(문구, 종류 = "info") {
    const 시간 = new Date().toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });

    const 줄 = document.createElement("div");
    줄.className = `log-entry ${종류}`.trim();
    줄.textContent = `[${시간}] ${문구}`;
    요소.activityLog.prepend(줄);
}