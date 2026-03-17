from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()
_ASSET_VERSION = "20260318"


def _render_home() -> str:
    return f"""<!DOCTYPE html>
<html lang=\"ko\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>키워드 포지</title>
    <meta name=\"description\" content=\"키워드 수집부터 확장, 분석, 선별, 제목 생성까지 한 번에 실행하는 한국어 웹 인터페이스\" />
    <link rel=\"stylesheet\" href=\"/assets/app.css?v={_ASSET_VERSION}\" />
    <script src=\"/assets/app.js?v={_ASSET_VERSION}\" defer></script>
</head>
<body>
    <div class=\"bg-orb bg-orb-a\"></div>
    <div class=\"bg-orb bg-orb-b\"></div>
    <div class=\"bg-grid\"></div>
    <div class=\"page-shell\">
        <header class=\"hero\">
            <div class=\"hero-copy\">
                <p class=\"eyebrow\">키워드 포지 웹 스튜디오</p>
                <h1>수익형 키워드 파이프라인을<br />깔끔한 웹 화면에서 바로 실행합니다</h1>
                <p class=\"hero-text\">기본 문서 화면 대신, 수집부터 제목 생성까지 한 흐름으로 볼 수 있는 한국어 대시보드입니다. 단계별 실행도 가능하고, 결과는 카드와 표로 즉시 확인할 수 있습니다.</p>
                <div class=\"hero-actions\">
                    <button type=\"button\" class=\"primary-btn\" id=\"runFullButton\">전체 흐름 실행</button>
                    <a class=\"secondary-link\" href=\"/api-docs\" target=\"_blank\" rel=\"noopener noreferrer\">개발용 API 문서 보기</a>
                </div>
            </div>
            <aside class=\"hero-panel\">
                <div class=\"hero-stat\"><span>수집</span><strong id=\"countCollected\">0</strong></div>
                <div class=\"hero-stat\"><span>확장</span><strong id=\"countExpanded\">0</strong></div>
                <div class=\"hero-stat\"><span>분석</span><strong id=\"countAnalyzed\">0</strong></div>
                <div class=\"hero-stat\"><span>선별</span><strong id=\"countSelected\">0</strong></div>
                <div class=\"hero-stat\"><span>제목</span><strong id=\"countTitled\">0</strong></div>
            </aside>
        </header>

        <main class=\"layout-grid\">
            <section class=\"panel control-panel\">
                <div class=\"panel-head\">
                    <div>
                        <p class=\"panel-kicker\">입력 설정</p>
                        <h2>실행 조건</h2>
                    </div>
                    <div class=\"preset-group\">
                        <button type=\"button\" class=\"ghost-chip\" data-preset=\"finance\">금융 예시</button>
                        <button type=\"button\" class=\"ghost-chip\" data-preset=\"travel\">여행 예시</button>
                        <button type=\"button\" class=\"ghost-chip\" data-preset=\"food\">맛집 예시</button>
                    </div>
                </div>

                <div class=\"form-grid\">
                    <div class=\"field-block mode-block\">
                        <span class=\"field-label\">수집 모드</span>
                        <label class=\"mode-card\">
                            <input type=\"radio\" name=\"collectorMode\" value=\"category\" checked />
                            <span><strong>카테고리 모드</strong><em>트렌드 섹션 기준으로 묶인 키워드만 수집합니다.</em></span>
                        </label>
                        <label class=\"mode-card\">
                            <input type=\"radio\" name=\"collectorMode\" value=\"seed\" />
                            <span><strong>시드 모드</strong><em>입력한 시드가 포함된 키워드만 모아서 이어서 처리합니다.</em></span>
                        </label>
                    </div>

                    <label class=\"field-block\">
                        <span class=\"field-label\">카테고리</span>
                        <input id=\"categoryInput\" type=\"text\" value=\"비즈니스경제\" placeholder=\"예: 비즈니스경제\" />
                    </label>

                    <label class=\"field-block\">
                        <span class=\"field-label\">시드 키워드</span>
                        <input id=\"seedInput\" type=\"text\" value=\"보험\" placeholder=\"예: 보험\" />
                    </label>

                    <label class=\"field-block\">
                        <span class=\"field-label\">수집 분석 파일 경로</span>
                        <input id=\"collectorAnalysisPath\" type=\"text\" value=\"app/collector/sample/site_analysis2.json\" />
                    </label>

                    <label class=\"field-block\">
                        <span class=\"field-label\">확장 분석 파일 경로</span>
                        <input id=\"expanderAnalysisPath\" type=\"text\" value=\"app/expander/sample/site_analysis.json\" />
                    </label>
                </div>

                <div class=\"option-row\">
                    <label class=\"check-chip\"><input id=\"optionRelated\" type=\"checkbox\" checked />연관 키워드 수집</label>
                    <label class=\"check-chip\"><input id=\"optionAutocomplete\" type=\"checkbox\" checked />자동완성 신호 사용</label>
                    <label class=\"check-chip\"><input id=\"optionBulk\" type=\"checkbox\" checked />대량 수집 모드 반영</label>
                </div>

                <div class=\"action-row\">
                    <button type=\"button\" class=\"subtle-btn\" id=\"runCollectButton\">수집만 실행</button>
                    <button type=\"button\" class=\"subtle-btn\" id=\"runExpandButton\">확장까지 실행</button>
                    <button type=\"button\" class=\"subtle-btn\" id=\"runAnalyzeButton\">분석까지 실행</button>
                    <button type=\"button\" class=\"subtle-btn\" id=\"runSelectButton\">골든 키워드 선별</button>
                    <button type=\"button\" class=\"subtle-btn\" id=\"runTitleButton\">제목 생성까지 실행</button>
                    <button type=\"button\" class=\"ghost-btn\" id=\"resetButton\">결과 비우기</button>
                </div>
            </section>

            <section class=\"panel summary-panel\">
                <div class=\"panel-head\">
                    <div>
                        <p class=\"panel-kicker\">진행 현황</p>
                        <h2>현재 상태</h2>
                    </div>
                    <span class=\"status-pill\" id=\"pipelineStatus\">대기 중</span>
                </div>
                <div class=\"status-list\" id=\"statusList\"></div>
                <div class=\"log-box\">
                    <div class=\"log-head\">실행 로그</div>
                    <div id=\"activityLog\" class=\"activity-log\"></div>
                </div>
            </section>

            <section class=\"panel results-panel\">
                <div class=\"panel-head\">
                    <div>
                        <p class=\"panel-kicker\">결과 미리보기</p>
                        <h2>단계별 출력</h2>
                    </div>
                </div>
                <div id=\"resultsGrid\" class=\"results-grid\"></div>
            </section>
        </main>
    </div>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> HTMLResponse:
    return HTMLResponse(_render_home())