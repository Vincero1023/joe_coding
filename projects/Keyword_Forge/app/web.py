from functools import lru_cache
from html import escape
from pathlib import Path
import re

from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.collector.categories import (
    CATEGORY_GROUPS,
    CATEGORY_SOURCE_CHOICES,
    DEFAULT_CATEGORY,
    DEFAULT_CATEGORY_SOURCE,
    DEFAULT_TREND_SERVICE,
    TREND_SERVICE_CHOICES,
)
from app.expander.utils.tokenizer import normalize_key


router = APIRouter()
_ASSET_VERSION = "20260319-collect-compact-v27"
_STUDY_DIR = Path(__file__).resolve().parents[1] / "Study"
_GUIDE_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("basics", "시작하기", ("사용법", "무료 키워드", "검색량 조회", "도구 추천")),
    ("discovery", "키워드 발굴", ("황금키워드", "연관검색어", "롱테일", "검색량 많은", "트렌드")),
    ("blog", "블로그 전략", ("블로그", "SEO", "방문자", "애드포스트")),
    ("ads", "광고 · CPC", ("CPC", "입찰가", "경쟁사")),
    ("business", "스토어 · 플레이스", ("스마트스토어", "플레이스", "시즌")),
)


def _render_category_options() -> str:
    rendered_groups: list[str] = []
    for group_name, categories in CATEGORY_GROUPS:
        options = "".join(
            f'<option value="{category}"{" selected" if category == DEFAULT_CATEGORY else ""}>{category}</option>'
            for category in categories
        )
        rendered_groups.append(f'<optgroup label="{group_name}">{options}</optgroup>')

    return "".join(rendered_groups)


def _replace_sample_site_name(value: str) -> str:
    replaced = str(value or "")
    replaced = replaced.replace("키워드마스터", "본 사이트")
    replaced = replaced.replace("KeywordMaster", "본 사이트")
    replaced = replaced.replace("keywordmaster.net", "본 사이트")
    return replaced


def _clean_text(value: str) -> str:
    return " ".join(_replace_sample_site_name(value).split())


def _build_guide_slug(index: int, path: Path) -> str:
    stem = re.sub(r"-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$", "", path.stem)
    base = normalize_key(_replace_sample_site_name(stem)) or f"guide{index}"
    return f"guide-{index:02d}-{base[:48]}"


def _pick_guide_group(title: str) -> str:
    for key, _label, keywords in _GUIDE_GROUPS:
        if any(keyword in title for keyword in keywords):
            return key
    return "discovery"


def _sanitize_guide_content(article_html: str, *, title_map: dict[str, str]) -> str:
    soup = BeautifulSoup(article_html, "html.parser")

    for element in soup.select("script, style, nav, footer"):
        element.decompose()

    for text_node in soup.find_all(string=True):
        parent_name = getattr(text_node.parent, "name", "")
        if parent_name in {"script", "style"}:
            continue
        replaced = _replace_sample_site_name(str(text_node))
        if replaced != str(text_node):
            text_node.replace_with(replaced)

    for anchor in soup.find_all("a"):
        href = str(anchor.get("href") or "").strip()
        label = _clean_text(anchor.get_text(" ", strip=True))
        local_slug = title_map.get(label)
        if local_slug:
            anchor["href"] = f"/guides/{local_slug}"
            anchor.attrs.pop("target", None)
            anchor.attrs.pop("rel", None)
            continue

        if "keywordmaster.net" in href:
            anchor["href"] = "/" if "page=search" in href else "/guides"
            anchor.attrs.pop("target", None)
            anchor.attrs.pop("rel", None)
            continue

        if href.startswith(("http://", "https://")):
            anchor["target"] = "_blank"
            anchor["rel"] = "noopener noreferrer"

    return str(soup)


@lru_cache
def _load_study_guides() -> list[dict[str, object]]:
    if not _STUDY_DIR.exists():
        return []

    raw_guides: list[dict[str, object]] = []
    for index, path in enumerate(sorted(_STUDY_DIR.glob("*.html")), start=1):
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        article = soup.select_one("article.blog-article") or soup.find("article") or soup
        title_tag = article.find("h1") or soup.title
        subtitle_tag = article.select_one(".blog-hero-sub") or article.find("p")
        title = _clean_text(title_tag.get_text(" ", strip=True) if title_tag else path.stem)
        subtitle = _clean_text(subtitle_tag.get_text(" ", strip=True) if subtitle_tag else "")

        sections: list[dict[str, str]] = []
        for heading in article.find_all("h2")[:5]:
            heading_text = _clean_text(heading.get_text(" ", strip=True))
            summary_parts: list[str] = []
            sibling = heading.find_next_sibling()
            while sibling is not None and getattr(sibling, "name", None) != "h2" and len(summary_parts) < 2:
                if getattr(sibling, "name", None) == "p":
                    text = _clean_text(sibling.get_text(" ", strip=True))
                    if text:
                        summary_parts.append(text)
                elif getattr(sibling, "name", None) == "ul":
                    for li in sibling.find_all("li", recursive=False):
                        text = _clean_text(li.get_text(" ", strip=True))
                        if text:
                            summary_parts.append(text)
                        if len(summary_parts) >= 2:
                            break
                sibling = sibling.find_next_sibling()
            sections.append(
                {
                    "title": heading_text,
                    "summary": " ".join(summary_parts[:2]),
                }
            )

        raw_guides.append(
            {
                "slug": _build_guide_slug(index, path),
                "title": title,
                "subtitle": subtitle,
                "group": _pick_guide_group(title),
                "sections": sections,
                "article_html": str(article),
            }
        )

    title_map = {str(guide["title"]): str(guide["slug"]) for guide in raw_guides}
    return [
        {
            "slug": guide["slug"],
            "title": guide["title"],
            "subtitle": guide["subtitle"],
            "group": guide["group"],
            "sections": guide["sections"],
            "content_html": _sanitize_guide_content(str(guide["article_html"]), title_map=title_map),
        }
        for guide in raw_guides
    ]


def _render_guide_card(guide: dict[str, object]) -> str:
    section_items = "".join(
        f"<li><strong>{escape(str(section['title']))}</strong><span>{escape(str(section['summary']))}</span></li>"
        for section in guide.get("sections", [])
        if str(section.get("title") or "").strip()
    )
    return f"""
        <article class="guide-article-card">
            <div class="guide-article-head">
                <h4>{escape(str(guide['title']))}</h4>
                <p>{escape(str(guide['subtitle']))}</p>
            </div>
            <ul class="guide-article-points">
                {section_items}
            </ul>
            <a class="secondary-link guide-article-link" href="/guides/{escape(str(guide['slug']))}">문서 보기</a>
        </article>
    """


def _render_guide_panel() -> str:
    guides = _load_study_guides()
    if not guides:
        return ""

    grouped: dict[str, list[dict[str, object]]] = {key: [] for key, _label, _keywords in _GUIDE_GROUPS}
    for guide in guides:
        group_key = str(guide.get("group") or "discovery")
        grouped.setdefault(group_key, []).append(guide)

    tab_buttons = "".join(
        f'<button type="button" class="guide-tab-button{" active" if index == 0 else ""}" '
        f'data-guide-tab="{escape(key)}">{escape(label)}</button>'
        for index, (key, label, _keywords) in enumerate(_GUIDE_GROUPS)
    )

    tab_panels = []
    for index, (key, label, _keywords) in enumerate(_GUIDE_GROUPS):
        cards = "".join(_render_guide_card(guide) for guide in grouped.get(key, []))

        tab_panels.append(
            f"""
            <section class="guide-tab-panel{' active' if index == 0 else ''}" data-guide-panel="{escape(key)}" {'hidden' if index != 0 else ''}>
                <div class="guide-card-grid">
                    {cards if cards else '<div class="placeholder">해당 분류의 문서가 없습니다.</div>'}
                </div>
            </section>
            """
        )

    return f"""
        <section class="panel guide-panel">
            <div class="panel-head">
                <div>
                    <p class="panel-kicker">Guide</p>
                    <h2>사용 가이드</h2>
                </div>
                <span class="status-pill success">Study {len(guides)}편 반영</span>
            </div>
            <p class="input-help compact-help">
                Study 폴더 문서를 주제별로 묶었습니다. 본 사이트 사용 흐름과 운영 팁을 홈 화면에서 바로 열어볼 수 있습니다.
            </p>
            <div class="guide-tab-strip">
                {tab_buttons}
            </div>
            <div class="guide-tab-panels">
                {''.join(tab_panels)}
            </div>
        </section>
    """


def _render_static_shell(*, title: str, description: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | Keyword Forge</title>
    <meta name="description" content="{escape(description)}" />
    <link rel="stylesheet" href="/assets/app.css?v={_ASSET_VERSION}" />
</head>
<body>
    <div class="bg-orb bg-orb-a"></div>
    <div class="bg-orb bg-orb-b"></div>
    <div class="bg-grid"></div>
    {body}
</body>
</html>
"""


def _render_guides_index() -> str:
    guides = _load_study_guides()
    grouped: dict[str, list[dict[str, object]]] = {key: [] for key, _label, _keywords in _GUIDE_GROUPS}
    for guide in guides:
        grouped.setdefault(str(guide.get("group") or "discovery"), []).append(guide)

    sections: list[str] = []
    for key, label, _keywords in _GUIDE_GROUPS:
        cards = "".join(_render_guide_card(guide) for guide in grouped.get(key, []))
        sections.append(
            f"""
            <section class="doc-section">
                <div class="doc-section-head">
                    <p class="panel-kicker">Guide Group</p>
                    <h2>{escape(label)}</h2>
                </div>
                <div class="guide-card-grid">
                    {cards if cards else '<div class="placeholder">해당 분류의 문서가 없습니다.</div>'}
                </div>
            </section>
            """
        )

    return _render_static_shell(
        title="사용 가이드",
        description="Study 문서를 본 사이트 안에서 볼 수 있는 가이드 인덱스입니다.",
        body=f"""
        <div class="doc-shell">
            <header class="doc-hero">
                <div class="doc-breadcrumbs"><a href="/">홈</a><span>/</span><strong>사용 가이드</strong></div>
                <div class="doc-actions">
                    <a class="secondary-link" href="/">대시보드</a>
                    <a class="secondary-link" href="/api-docs" target="_blank" rel="noopener noreferrer">API 문서</a>
                </div>
                <div class="doc-hero-copy">
                    <p class="eyebrow">Guide</p>
                    <h1>Study 문서 모음</h1>
                    <p>기능 설명서와 운영 팁을 주제별로 묶었습니다. 각 문서는 본 사이트 안에서 바로 열립니다.</p>
                </div>
            </header>
            <main class="doc-stack">
                {''.join(sections)}
            </main>
        </div>
        """,
    )


def _render_guide_detail(guide_slug: str) -> str:
    guide = next((item for item in _load_study_guides() if str(item.get("slug")) == guide_slug), None)
    if guide is None:
        raise HTTPException(status_code=404, detail="Guide not found.")

    return _render_static_shell(
        title=str(guide["title"]),
        description=str(guide.get("subtitle") or ""),
        body=f"""
        <div class="doc-shell">
            <header class="doc-hero doc-hero-compact">
                <div class="doc-breadcrumbs">
                    <a href="/">홈</a><span>/</span><a href="/guides">사용 가이드</a><span>/</span><strong>{escape(str(guide['title']))}</strong>
                </div>
                <div class="doc-actions">
                    <a class="secondary-link" href="/guides">가이드 목록</a>
                    <a class="secondary-link" href="/">대시보드</a>
                </div>
                <div class="doc-hero-copy">
                    <p class="eyebrow">Guide Detail</p>
                    <h1>{escape(str(guide['title']))}</h1>
                    <p>{escape(str(guide.get('subtitle') or ''))}</p>
                </div>
            </header>
            <main class="doc-content">
                <article class="doc-article">
                    {str(guide.get("content_html") or "")}
                </article>
            </main>
        </div>
        """,
    )


def _render_home() -> str:
    category_options = _render_category_options()
    category_source_options = "".join(
        f'<option value="{source}"{" selected" if source == DEFAULT_CATEGORY_SOURCE else ""}>'
        f'{"네이버 트렌드" if source == "naver_trend" else "검색 preset fallback"}'
        "</option>"
        for source in CATEGORY_SOURCE_CHOICES
    )
    trend_service_options = "".join(
        f'<option value="{service}"{" selected" if service == DEFAULT_TREND_SERVICE else ""}>'
        f'{"네이버 블로그" if service == "naver_blog" else "인플루언서"}'
        "</option>"
        for service in TREND_SERVICE_CHOICES
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>수익형 키워드 발굴&amp;제목 생성기</title>
    <meta
        name="description"
        content="수익형 키워드를 수집, 확장, 분석, 선별하고 제목까지 생성하는 로컬 도구"
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
                <p class="eyebrow">Keyword Forge</p>
                <h1>수익형 키워드 발굴&amp;제목 생성기</h1>
                <aside class="hero-panel">
                    <div class="hero-stat"><span>수집</span><strong id="countCollected">0</strong></div>
                    <div class="hero-stat"><span>확장</span><strong id="countExpanded">0</strong></div>
                    <div class="hero-stat"><span>분석</span><strong id="countAnalyzed">0</strong></div>
                    <div class="hero-stat"><span>선별</span><strong id="countSelected">0</strong></div>
                    <div class="hero-stat"><span>제목</span><strong id="countTitled">0</strong></div>
                </aside>
                <p class="hero-text">
                    시드 검색과 카테고리 수집을 바탕으로 키워드를 확장하고, 분석 후 제목용 후보까지 바로 추립니다.
                </p>
                <div class="hero-actions">
                    <button type="button" class="primary-btn" id="runFullButton">전체 실행</button>
                    <a class="secondary-link" href="/guides">사용 가이드</a>
                    <a class="secondary-link" href="/api-docs" target="_blank" rel="noopener noreferrer">API 문서</a>
                </div>
            </div>
        </header>

        <main class="layout-grid">
            <section class="panel summary-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Progress</p>
                        <h2>진행 현황</h2>
                    </div>
                    <span class="status-pill" id="pipelineStatus">대기 중</span>
                </div>

                <div class="progress-card">
                    <div class="progress-track">
                        <div id="progressBar" class="progress-bar"></div>
                    </div>
                    <div class="progress-meta">
                        <strong id="progressText">0 / 5 단계 완료</strong>
                        <span id="progressDetail">아직 실행하지 않았습니다.</span>
                    </div>
                </div>

                <div class="status-list" id="statusList"></div>

            </section>

            <section class="panel insights-panel" id="resultsRailPanel" hidden>
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Insights</p>
                        <h2>실시간 인사이트</h2>
                    </div>
                </div>
                <div id="resultsRail" class="results-rail"></div>
            </section>

            <section class="panel control-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Input</p>
                        <h2>실행 조건</h2>
                    </div>
                    <div class="preset-group">
                        <button type="button" class="ghost-chip" data-preset="finance">금융 예시</button>
                        <button type="button" class="ghost-chip" data-preset="travel">여행 예시</button>
                        <button type="button" class="ghost-chip" data-preset="food">맛집 예시</button>
                    </div>
                </div>

                <div class="control-stack" id="controlStack">
                <section class="control-stage-block control-stage-collect" data-control-block="collect">
                    <div class="control-stage-head">
                        <div>
                            <p class="panel-kicker">Collect Setup</p>
                            <h3>수집 설정</h3>
                        </div>
                        <span class="badge">1단계</span>
                    </div>

                <div class="form-grid">
                    <div class="field-block mode-block">
                        <span class="field-label">수집 모드</span>
                        <label class="mode-card">
                            <input type="radio" name="collectorMode" value="category" checked />
                            <span>
                                <strong>카테고리 모드</strong>
                                <em>카테고리 기반으로 대표 키워드를 가져온 뒤 확장과 분석으로 이어집니다.</em>
                            </span>
                        </label>
                        <label class="mode-card">
                            <input type="radio" name="collectorMode" value="seed" />
                            <span>
                                <strong>시드 모드</strong>
                                <em>입력한 시드 키워드를 기준으로 연관확장과 자동완성을 수행합니다.</em>
                            </span>
                        </label>
                    </div>

                    <div class="category-settings-grid" data-mode-visibility="category">
                        <label class="field-block category-setting-card">
                            <span class="field-label">카테고리</span>
                            <select id="categoryInput">
                                {category_options}
                            </select>
                        </label>

                        <label class="field-block category-setting-card">
                            <span class="field-label">카테고리 수집 소스</span>
                            <select id="categorySourceInput">
                                {category_source_options}
                            </select>
                        </label>

                        <label class="field-block category-setting-card">
                            <span class="field-label">Creator Advisor 서비스</span>
                            <select id="trendServiceInput">
                                {trend_service_options}
                            </select>
                        </label>

                        <label class="field-block category-setting-card">
                            <span class="field-label">트렌드 날짜</span>
                            <input id="trendDateInput" type="date" />
                        </label>

                        <label class="field-block category-setting-card">
                            <span class="field-label">로컬 브라우저</span>
                            <select id="trendBrowserInput">
                                <option value="auto">자동 감지</option>
                                <option value="edge">Microsoft Edge</option>
                                <option value="chrome">Google Chrome</option>
                                <option value="firefox">Mozilla Firefox</option>
                            </select>
                        </label>

                        <div class="field-block category-setting-card session-helper-card">
                            <span class="field-label">Creator Advisor 로그인</span>
                            <input
                                id="trendCookieInput"
                                type="hidden"
                                value=""
                            />
                            <button type="button" class="primary-btn session-helper-btn" id="launchLoginBrowserButton">전용 로그인 브라우저 열기</button>
                            <p class="input-help compact-help">전용 프로필에서 로그인하면 세션을 자동 저장해 다음 수집에 바로 사용합니다.</p>
                        </div>
                    </div>

                    <label class="field-block" data-mode-visibility="seed" hidden>
                        <span class="field-label">시드 키워드</span>
                        <input id="seedInput" type="text" placeholder="예: 보험" />
                    </label>

                    <div class="field-block field-block-wide collector-inline-actions" data-mode-visibility="seed" hidden>
                        <div class="action-row action-row-tight">
                            <button type="button" class="subtle-btn" data-run-action="collect">수집만 실행</button>
                        </div>
                    </div>

                    <div class="field-block field-block-wide collector-inline-actions" data-mode-visibility="category">
                        <div class="action-row action-row-tight">
                            <button type="button" class="subtle-btn" data-run-action="collect">수집만 실행</button>
                        </div>
                    </div>
                </div>

                <p class="input-help" id="trendSourceHelp" data-mode-visibility="category">
                    카테고리 모드에서 네이버 트렌드를 고르면 Creator Advisor 주제 기반 인기 키워드를 먼저 조회합니다.
                    쿠키가 없거나 실패하면 아래 fallback 설정에 따라 검색 preset으로 전환합니다.
                </p>

                <div class="option-row">
                    <label class="check-chip"><input id="optionRelated" type="checkbox" checked />연관 키워드 수집</label>
                    <label class="check-chip"><input id="optionAutocomplete" type="checkbox" checked />자동완성 우선 사용</label>
                    <label class="check-chip" data-mode-visibility="category"><input id="optionBulk" type="checkbox" checked />카테고리 다중 쿼리 사용</label>
                    <label class="check-chip"><input id="optionDebug" type="checkbox" checked />디버그 정보 포함</label>
                    <label class="check-chip" data-mode-visibility="category"><input id="trendFallbackInput" type="checkbox" />트렌드 실패 시 preset fallback</label>
                </div>

                </section>

                <section class="control-stage-block control-stage-pipeline" data-control-block="pipeline">
                    <div class="control-stage-head">
                        <div>
                            <p class="panel-kicker">Pipeline</p>
                            <h3>실행 버튼</h3>
                        </div>
                        <span class="badge">2-4단계</span>
                    </div>

                <div class="action-row pipeline-action-row">
                    <button type="button" class="subtle-btn" id="runExpandButton">확장까지 실행</button>
                    <button type="button" class="subtle-btn" id="runAnalyzeButton">분석까지 실행</button>
                    <button type="button" class="subtle-btn" id="runSelectButton">골든 키워드 선별</button>
                    <button type="button" class="subtle-btn" id="runTitleButton">제목 생성까지 실행</button>
                    <button type="button" class="ghost-btn" id="stopStreamButton" disabled>중지</button>
                    <button type="button" class="ghost-btn" id="resetButton">결과 초기화</button>
                </div>

                <section class="grade-select-panel">
                    <div class="grade-select-head">
                        <div>
                            <span class="field-label">등급별 선별</span>
                            <p class="grade-select-summary" id="gradeSelectSummary">전체 등급 선별</p>
                        </div>
                        <p class="input-help compact-help">수집 → 확장 → 분석까지 자동 실행한 뒤, 선택한 등급만 선별합니다.</p>
                    </div>
                    <div class="grade-select-presets">
                        <button type="button" class="ghost-chip" data-grade-preset="all">전체</button>
                        <button type="button" class="ghost-chip" data-grade-preset="sa">S·A</button>
                        <button type="button" class="ghost-chip" data-grade-preset="ab">A·B</button>
                        <button type="button" class="ghost-chip" data-grade-preset="bc">B·C</button>
                        <button type="button" class="ghost-chip" data-grade-preset="cd">C·D</button>
                        <button type="button" class="ghost-chip" data-grade-preset="df">D·F</button>
                    </div>
                    <div class="grade-select-row">
                        <button type="button" class="ghost-chip grade-toggle-chip" data-grade-toggle="S">S</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-grade-toggle="A">A</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-grade-toggle="B">B</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-grade-toggle="C">C</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-grade-toggle="D">D</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-grade-toggle="F">F</button>
                        <button type="button" class="subtle-btn grade-select-run" id="runGradeSelectButton">선택 등급 선별</button>
                    </div>
                </section>

                </section>

                    <section class="control-stage-block launcher-card control-stage-expand" data-control-block="expand" data-control-card="expand">
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
                                <option value="collector_selected">수집 결과 중 선택 항목</option>
                                <option value="manual_text">직접 붙여넣기</option>
                            </select>
                        </label>
                        <div class="launcher-source-details" data-expand-source-visibility="collector_selected" hidden>
                            <div class="launcher-note-card">
                                수집 결과에서 체크한 키워드만 확장에 사용합니다. 아래 수집 결과 카드에서 원하는 항목만 선택하면 됩니다.
                            </div>
                        </div>
                        <div class="launcher-source-details" data-expand-source-visibility="manual_text" hidden>
                            <label class="field-block">
                                <span class="field-label">직접 붙여넣을 키워드</span>
                                <textarea
                                    id="expandManualInput"
                                    rows="5"
                                    placeholder="예: 보험&#10;카드 비교&#10;대출 추천"
                                ></textarea>
                            </label>
                            <p class="input-help compact-help">줄바꿈, 콤마, 세미콜론으로 여러 키워드를 나눌 수 있습니다.</p>
                        </div>
                        <div class="launcher-inline-grid">
                            <div class="field-block">
                                <span class="field-label">확장 옵션</span>
                                <div class="option-row">
                                    <label class="check-chip"><input id="expandOptionRelated" type="checkbox" checked />연관확장</label>
                                    <label class="check-chip"><input id="expandOptionAutocomplete" type="checkbox" checked />자동완성</label>
                                    <label class="check-chip"><input id="expandOptionSeedFilter" type="checkbox" checked />원문포함</label>
                                </div>
                            </div>
                            <div class="field-block">
                                <span class="field-label">개수 설정</span>
                                <div class="option-row">
                                    <button type="button" class="ghost-chip" data-expand-limit="1000">1,000개</button>
                                    <button type="button" class="ghost-chip" data-expand-limit="10000">10,000개</button>
                                    <button type="button" class="ghost-chip" data-expand-limit="infinite">무제한</button>
                                </div>
                                <input id="expandMaxResultsInput" type="number" min="1" step="1" value="1000" placeholder="예: 1000" />
                            </div>
                        </div>
                    </section>

                    <section class="control-stage-block launcher-card control-stage-analyze" data-control-block="analyze" data-control-card="analyze">
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
                        <div class="launcher-source-details" data-analyze-source-visibility="manual_text" hidden>
                            <label class="field-block">
                                <span class="field-label">직접 붙여넣을 키워드</span>
                                <textarea
                                    id="analyzeManualInput"
                                    rows="5"
                                    placeholder="예: 보험 추천, 카드 비교, 대출 금리"
                                ></textarea>
                            </label>
                        </div>
                        <details class="launcher-advanced">
                            <summary>실측 데이터 / CSV</summary>
                            <div class="launcher-advanced-body">
                                <label class="field-block field-block-wide">
                                    <span class="field-label">실측 데이터 붙여넣기</span>
                                    <textarea
                                        id="analyzeKeywordStatsInput"
                                        rows="6"
                                        placeholder="분석 HTML 전체 또는 data-line 행을 그대로 붙여넣으세요."
                                    ></textarea>
                                </label>
                                <p class="input-help compact-help">분석 HTML 전체나 data-line 행을 붙여넣으면 PC/MO조회, 블로그수, 입찰가를 우선 사용합니다.</p>
                                <div class="field-block field-block-wide">
                                    <span class="field-label">분석/출력</span>
                                    <div class="option-row">
                                        <button type="button" class="ghost-chip" id="exportCsvButton">분석 결과 CSV</button>
                                    </div>
                                </div>
                                <p class="input-help compact-help">확장 없이 분석만 실행하거나, 분석 결과를 내려받는 용도로 씁니다.</p>
                            </div>
                        </details>
                    </section>

                <section class="title-settings-card" data-control-block="title">
                    <div class="launcher-head">
                        <div>
                            <p class="panel-kicker">Title AI</p>
                            <h3>제목 생성 설정</h3>
                        </div>
                        <span class="badge" id="titleModeBadge">template</span>
                    </div>
                    <div class="form-grid">
                        <input id="titleMode" type="hidden" value="template" />

                        <div class="field-block mode-block title-mode-block">
                            <span class="field-label">제목 생성 모드</span>
                            <label class="mode-card">
                                <input type="radio" name="titleModeOption" value="template" checked />
                                <span>
                                    <strong>템플릿 모드</strong>
                                    <em>추가 설정 없이 즉시 제목을 생성합니다. 빠르게 후보를 뽑을 때 적합합니다.</em>
                                </span>
                            </label>
                            <label class="mode-card">
                                <input type="radio" name="titleModeOption" value="ai" />
                                <span>
                                    <strong>AI 모드</strong>
                                    <em>Provider, 모델, API Key를 사용해 더 유연한 제목을 생성합니다.</em>
                                </span>
                            </label>
                        </div>

                        <div class="field-block field-block-wide title-mode-note" data-title-mode-visibility="template">
                            <span class="field-label">템플릿 안내</span>
                            <p class="input-help compact-help">
                                템플릿 모드는 현재 선택된 골든 키워드로 네이버형/블로그형 제목 세트를 바로 만듭니다.
                                별도 API 설정 없이 가장 빠르게 사용할 수 있습니다.
                            </p>
                        </div>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">AI Provider</span>
                            <select id="titleProvider">
                                <option value="openai">OpenAI</option>
                                <option value="gemini">Gemini</option>
                                <option value="anthropic">Anthropic</option>
                            </select>
                        </label>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">Model</span>
                            <input id="titleModel" type="text" value="gpt-4o-mini" placeholder="예: gpt-4o-mini" />
                        </label>

                        <label class="field-block field-block-wide" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">API Key</span>
                            <input id="titleApiKey" type="password" placeholder="브라우저에만 저장됩니다." />
                        </label>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">Temperature</span>
                            <input id="titleTemperature" type="text" value="0.7" />
                        </label>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">Fallback</span>
                            <label class="check-chip"><input id="titleFallback" type="checkbox" checked />AI 실패 시 template 사용</label>
                        </label>
                    </div>
                    <p class="input-help" data-title-mode-visibility="ai" hidden>
                        API 키는 서버에 저장하지 않고 현재 브라우저 localStorage 에만 보관합니다.
                    </p>
                </section>
                </div>

            </section>

            <section class="panel results-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Workbench</p>
                        <h2>키워드 작업대</h2>
                    </div>
                </div>
                <div id="resultsGrid" class="results-grid"></div>
            </section>

            <section class="panel diagnostics-panel">
                <div class="debug-box">
                    <div class="debug-box-head">
                        <div>
                            <p class="panel-kicker">Debug</p>
                            <h3>오류 및 진단</h3>
                        </div>
                        <button type="button" class="ghost-btn debug-clear-btn" id="clearDebugButton">진단 초기화</button>
                    </div>
                    <div id="errorConsole" class="error-console empty">오류가 발생하지 않았습니다.</div>
                    <div id="debugPanels" class="debug-panels"></div>
                </div>
            </section>

            <section class="panel logs-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Logs</p>
                        <h2>실행 로그</h2>
                    </div>
                </div>
                <div class="log-box">
                    <div id="activityLog" class="activity-log"></div>
                </div>
            </section>
        </main>
    </div>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> HTMLResponse:
    return HTMLResponse(_render_home())


@router.get("/guides", response_class=HTMLResponse, include_in_schema=False)
def guides_index() -> HTMLResponse:
    return HTMLResponse(_render_guides_index())


@router.get("/guides/{guide_slug}", response_class=HTMLResponse, include_in_schema=False)
def guide_detail(guide_slug: str) -> HTMLResponse:
    return HTMLResponse(_render_guide_detail(guide_slug))
