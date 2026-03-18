from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.collector.categories import (
    CATEGORY_CHOICES,
    CATEGORY_GROUPS,
    CATEGORY_SOURCE_CHOICES,
    DEFAULT_CATEGORY,
    DEFAULT_CATEGORY_SOURCE,
    DEFAULT_TREND_SERVICE,
    TREND_SERVICE_CHOICES,
)


router = APIRouter()
_ASSET_VERSION = "20260318-expand-live-preview"


def _render_category_options() -> str:
    rendered_groups: list[str] = []
    for group_name, categories in CATEGORY_GROUPS:
        options = "".join(
            f'<option value="{category}"{" selected" if category == DEFAULT_CATEGORY else ""}>{category}</option>'
            for category in categories
        )
        rendered_groups.append(f'<optgroup label="{group_name}">{options}</optgroup>')

    return "".join(rendered_groups)


def _render_home() -> str:
    category_options = _render_category_options()
    category_source_options = "".join(
        (
            f'<option value="{source}"{" selected" if source == DEFAULT_CATEGORY_SOURCE else ""}>'
            f'{"네이버 트렌드" if source == "naver_trend" else "검색 preset fallback"}'
            f"</option>"
        )
        for source in CATEGORY_SOURCE_CHOICES
    )
    trend_service_options = "".join(
        (
            f'<option value="{service}"{" selected" if service == DEFAULT_TREND_SERVICE else ""}>'
            f'{"네이버 블로그" if service == "naver_blog" else "인플루언서"}'
            f"</option>"
        )
        for service in TREND_SERVICE_CHOICES
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>키워드 포지</title>
    <meta
        name="description"
        content="키워드 수집, 확장, 분석, 선별, 제목 생성을 단계별로 실행하고 실시간 상태와 오류 진단을 확인할 수 있는 대시보드입니다."
    />
    <link rel="stylesheet" href="/assets/app.css?v={_ASSET_VERSION}" />
    <script src="/assets/app.js?v={_ASSET_VERSION}" defer></script>
</head>
<body>
    <div class="bg-orb bg-orb-a"></div>
    <div class="bg-orb bg-orb-b"></div>
    <div class="bg-grid"></div>
    <div class="page-shell">
        <header class="hero">
            <div class="hero-copy">
                <p class="eyebrow">Keyword Forge Studio</p>
                <h1>수익형 키워드 파이프라인을<br />단계별로 추적하면서 실행합니다.</h1>
                <p class="hero-text">
                    수집부터 제목 생성까지 각 단계가 어디까지 진행됐는지 바로 확인하고,
                    실패하면 request id, 응답 오류, collector 진단 로그까지 한 화면에서 확인할 수 있습니다.
                </p>
                <div class="hero-actions">
                    <button type="button" class="primary-btn" id="runFullButton">전체 흐름 실행</button>
                    <a class="secondary-link" href="/api-docs" target="_blank" rel="noopener noreferrer">API 문서 보기</a>
                </div>
            </div>
            <aside class="hero-panel">
                <div class="hero-stat"><span>수집</span><strong id="countCollected">0</strong></div>
                <div class="hero-stat"><span>확장</span><strong id="countExpanded">0</strong></div>
                <div class="hero-stat"><span>분석</span><strong id="countAnalyzed">0</strong></div>
                <div class="hero-stat"><span>선별</span><strong id="countSelected">0</strong></div>
                <div class="hero-stat"><span>제목</span><strong id="countTitled">0</strong></div>
            </aside>
        </header>

        <main class="layout-grid">
            <section class="panel control-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">입력 설정</p>
                        <h2>실행 조건</h2>
                    </div>
                    <div class="preset-group">
                        <button type="button" class="ghost-chip" data-preset="finance">금융 예시</button>
                        <button type="button" class="ghost-chip" data-preset="travel">여행 예시</button>
                        <button type="button" class="ghost-chip" data-preset="food">맛집 예시</button>
                    </div>
                </div>

                <div class="form-grid">
                    <div class="field-block mode-block">
                        <span class="field-label">수집 모드</span>
                        <label class="mode-card">
                            <input type="radio" name="collectorMode" value="category" checked />
                            <span>
                                <strong>카테고리 모드</strong>
                                <em>고정 카테고리 프리셋을 기준으로 공개 검색 키워드를 수집합니다.</em>
                            </span>
                        </label>
                        <label class="mode-card">
                            <input type="radio" name="collectorMode" value="seed" />
                            <span>
                                <strong>시드 모드</strong>
                                <em>입력한 시드 키워드를 중심으로 자동완성/연관 확장을 수집합니다.</em>
                            </span>
                        </label>
                    </div>

                    <label class="field-block">
                        <span class="field-label">카테고리</span>
                        <select id="categoryInput">
                            {category_options}
                        </select>
                    </label>

                    <label class="field-block">
                        <span class="field-label">카테고리 수집 소스</span>
                        <select id="categorySourceInput">
                            {category_source_options}
                        </select>
                    </label>

                    <label class="field-block">
                        <span class="field-label">시드 키워드</span>
                        <input id="seedInput" type="text" value="보험" placeholder="예: 보험" />
                    </label>

                    <label class="field-block">
                        <span class="field-label">Creator Advisor 서비스</span>
                        <select id="trendServiceInput">
                            {trend_service_options}
                        </select>
                    </label>

                    <label class="field-block">
                        <span class="field-label">트렌드 날짜</span>
                        <input id="trendDateInput" type="date" />
                    </label>

                    <label class="field-block">
                        <span class="field-label">로컬 브라우저</span>
                        <select id="trendBrowserInput">
                            <option value="auto">자동 감지</option>
                            <option value="edge">Microsoft Edge</option>
                            <option value="chrome">Google Chrome</option>
                            <option value="firefox">Mozilla Firefox</option>
                        </select>
                    </label>

                    <label class="field-block field-block-wide">
                        <span class="field-label">Creator Advisor 쿠키</span>
                        <input
                            id="trendCookieInput"
                            type="password"
                            placeholder="NID_AUT=...; NID_SES=... 형태로 붙여넣기"
                        />
                    </label>

                    <div class="field-block field-block-wide local-action-block">
                        <span class="field-label">로컬 세션 도우미</span>
                        <div class="local-action-row">
                            <button type="button" class="primary-btn" id="launchLoginBrowserButton">전용 로그인 브라우저 열기</button>
                            <button type="button" class="ghost-btn" id="loadLocalCookieButton">브라우저에서 쿠키 불러오기</button>
                            <span id="localCookieStatus" class="input-help compact-help">아직 불러온 로컬 세션이 없습니다.</span>
                        </div>
                    </div>

                    <label class="field-block">
                        <span class="field-label">확장 분석 파일 경로</span>
                        <input id="expanderAnalysisPath" type="text" value="app/expander/sample/site_analysis.json" />
                    </label>
                </div>

                <p class="input-help" id="trendSourceHelp">
                    category 모드에서 `네이버 트렌드`를 고르면 Creator Advisor의 주제별 인기 유입 검색어를 먼저 조회합니다.
                    인증 쿠키가 없거나 실패하면 아래 fallback 옵션에 따라 기존 검색 preset으로 내려갑니다.
                </p>

                <div class="option-row">
                    <label class="check-chip"><input id="optionRelated" type="checkbox" checked />연관 키워드 수집</label>
                    <label class="check-chip"><input id="optionAutocomplete" type="checkbox" checked />자동완성 우선 사용</label>
                    <label class="check-chip"><input id="optionBulk" type="checkbox" checked />카테고리 다중 쿼리 사용</label>
                    <label class="check-chip"><input id="optionDebug" type="checkbox" checked />디버그 정보 포함</label>
                    <label class="check-chip"><input id="trendFallbackInput" type="checkbox" />트렌드 실패 시 preset fallback</label>
                </div>

                <div class="launcher-grid">
                    <section class="launcher-card">
                        <div class="launcher-head">
                            <div>
                                <p class="panel-kicker">Expand Entry</p>
                                <h3>확장 시작점</h3>
                            </div>
                            <span class="badge" id="selectedCollectedCount">선택 0건</span>
                        </div>
                        <label class="field-block">
                            <span class="field-label">확장 입력 소스</span>
                            <select id="expandInputSource">
                                <option value="collector_all">수집 결과 전체</option>
                                <option value="collector_selected">수집 결과 중 선택한 항목</option>
                                <option value="manual_text">직접 붙여넣기</option>
                            </select>
                        </label>
                        <label class="field-block">
                            <span class="field-label">직접 붙여넣을 키워드</span>
                            <textarea
                                id="expandManualInput"
                                rows="5"
                                placeholder="예: 보험&#10;카드 비교&#10;대출 추천"
                            ></textarea>
                        </label>
                        <p class="input-help">줄바꿈, 콤마, 세미콜론으로 여러 키워드를 나눌 수 있습니다.</p>
                    </section>

                    <section class="launcher-card">
                        <div class="launcher-head">
                            <div>
                                <p class="panel-kicker">Analyze Entry</p>
                                <h3>분석 시작점</h3>
                            </div>
                            <span class="badge" id="manualAnalyzeCount">직접 입력 0건</span>
                        </div>
                        <label class="field-block">
                            <span class="field-label">분석 입력 소스</span>
                            <select id="analyzeInputSource">
                                <option value="expanded_results">확장 결과 사용</option>
                                <option value="manual_text">직접 붙여넣기</option>
                            </select>
                        </label>
                        <label class="field-block">
                            <span class="field-label">직접 붙여넣을 키워드</span>
                            <textarea
                                id="analyzeManualInput"
                                rows="5"
                                placeholder="예: 보험 추천, 카드 비교, 대출 금리"
                            ></textarea>
                        </label>
                        <p class="input-help">확장 없이 분석만 시작할 때 사용합니다.</p>
                    </section>
                </div>

                <section class="title-settings-card">
                    <div class="launcher-head">
                        <div>
                            <p class="panel-kicker">Title AI</p>
                            <h3>제목 생성 설정</h3>
                        </div>
                        <span class="badge" id="titleModeBadge">template</span>
                    </div>
                    <div class="form-grid">
                        <label class="field-block">
                            <span class="field-label">제목 생성 모드</span>
                            <select id="titleMode">
                                <option value="template">Template</option>
                                <option value="ai">AI</option>
                            </select>
                        </label>

                        <label class="field-block">
                            <span class="field-label">AI Provider</span>
                            <select id="titleProvider">
                                <option value="openai">OpenAI</option>
                                <option value="gemini">Gemini</option>
                                <option value="anthropic">Anthropic</option>
                            </select>
                        </label>

                        <label class="field-block">
                            <span class="field-label">Model</span>
                            <input id="titleModel" type="text" value="gpt-4o-mini" placeholder="예: gpt-4o-mini" />
                        </label>

                        <label class="field-block">
                            <span class="field-label">API Key</span>
                            <input id="titleApiKey" type="password" placeholder="브라우저에만 저장됩니다." />
                        </label>

                        <label class="field-block">
                            <span class="field-label">Temperature</span>
                            <input id="titleTemperature" type="text" value="0.7" />
                        </label>

                        <label class="field-block">
                            <span class="field-label">Fallback</span>
                            <label class="check-chip"><input id="titleFallback" type="checkbox" checked />AI 실패 시 template 사용</label>
                        </label>
                    </div>
                    <p class="input-help">
                        API 키는 서버에 저장하지 않고 현재 브라우저 `localStorage`에만 기억합니다.
                        AI 모드를 켜도 키가 없거나 호출이 실패하면 fallback 설정에 따라 template 모드로 내려갑니다.
                    </p>
                </section>

                <div class="action-row">
                    <button type="button" class="subtle-btn" id="runCollectButton">수집만 실행</button>
                    <button type="button" class="subtle-btn" id="runExpandButton">확장까지 실행</button>
                    <button type="button" class="subtle-btn" id="runAnalyzeButton">분석까지 실행</button>
                    <button type="button" class="subtle-btn" id="runSelectButton">골든 키워드 선별</button>
                    <button type="button" class="subtle-btn" id="runTitleButton">제목 생성까지 실행</button>
                    <button type="button" class="ghost-btn" id="resetButton">결과 초기화</button>
                </div>
            </section>

            <section class="panel summary-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">진행 현황</p>
                        <h2>실시간 상태</h2>
                    </div>
                    <span class="status-pill" id="pipelineStatus">대기 중</span>
                </div>

                <div class="progress-card">
                    <div class="progress-track">
                        <div id="progressBar" class="progress-bar"></div>
                    </div>
                    <div class="progress-meta">
                        <strong id="progressText">0 / 5 단계 완료</strong>
                        <span id="progressDetail">아직 실행되지 않았습니다.</span>
                    </div>
                </div>

                <div class="status-list" id="statusList"></div>

                <div class="log-box">
                    <div class="log-head">실행 로그</div>
                    <div id="activityLog" class="activity-log"></div>
                </div>

                <div class="debug-box">
                    <div class="debug-box-head">
                        <div>
                            <p class="panel-kicker">디버그</p>
                            <h3>오류 및 진단</h3>
                        </div>
                        <button type="button" class="ghost-btn debug-clear-btn" id="clearDebugButton">진단 초기화</button>
                    </div>
                    <div id="errorConsole" class="error-console empty">오류가 발생하지 않았습니다.</div>
                    <div id="debugPanels" class="debug-panels"></div>
                </div>
            </section>

            <section class="panel results-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">결과 미리보기</p>
                        <h2>단계별 출력</h2>
                    </div>
                </div>
                <div id="resultsGrid" class="results-grid"></div>
            </section>
        </main>
    </div>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> HTMLResponse:
    return HTMLResponse(_render_home())
