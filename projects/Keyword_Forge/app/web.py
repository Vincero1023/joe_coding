import json
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
from app.title.ai_client import get_default_system_prompt
from app.title.presets import DEFAULT_TITLE_PRESET_KEY, build_title_preset_payload


router = APIRouter()
_ASSET_VERSION = "20260321-cannibal-serp-v48"
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


def _render_queue_routine_category_picker() -> str:
    rendered_groups: list[str] = []
    for group_name, categories in CATEGORY_GROUPS:
        chips = "".join(
            (
                '<label class="check-chip queue-category-chip">'
                f'<input type="checkbox" value="{escape(category)}" data-queue-category />'
                f"{escape(category)}"
                "</label>"
            )
            for category in categories
        )
        rendered_groups.append(
            '<div class="queue-category-group">'
            f'<span class="queue-category-group-label">{escape(group_name)}</span>'
            f'<div class="queue-category-chip-grid">{chips}</div>'
            "</div>"
        )
    return "".join(rendered_groups)


def _replace_sample_site_name(value: str) -> str:
    replaced = str(value or "")
    replaced = replaced.replace("키워드마스터", "본 사이트")
    replaced = replaced.replace("KeywordMaster", "본 사이트")
    replaced = replaced.replace("keywordmaster.net", "본 사이트")
    return replaced


def _clean_text(value: str) -> str:
    return " ".join(_replace_sample_site_name(value).split())


def _render_help_tooltip(text: str, *, label: str = "도움말") -> str:
    lines = [escape(_clean_text(line)) for line in str(text or "").splitlines() if _clean_text(line)]
    if not lines:
        return ""
    return (
        '<span class="inline-help">'
        f'<button type="button" class="help-icon-btn" aria-label="{escape(label)}">?</button>'
        f'<span class="help-tooltip">{"<br />".join(lines)}</span>'
        "</span>"
    )


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


def _render_title_prompt_editor() -> str:
    title_presets = build_title_preset_payload()
    title_preset_payload = json.dumps(title_presets, ensure_ascii=False).replace("</", "<\\/")
    default_system_prompt_payload = json.dumps(get_default_system_prompt(), ensure_ascii=False).replace("</", "<\\/")
    default_preset_key_payload = json.dumps(DEFAULT_TITLE_PRESET_KEY, ensure_ascii=False)
    body = f"""
    <div class="bg-orb bg-orb-a"></div>
    <div class="bg-orb bg-orb-b"></div>
    <div class="bg-grid"></div>
    <script>
        window.KEYWORD_FORGE_TITLE_PRESETS = {title_preset_payload};
        window.KEYWORD_FORGE_TITLE_DEFAULT_SYSTEM_PROMPT = {default_system_prompt_payload};
        window.KEYWORD_FORGE_TITLE_DEFAULT_PRESET_KEY = {default_preset_key_payload};
    </script>
    <main class="doc-shell title-prompt-shell">
        <div class="doc-stack">
            <section class="doc-hero doc-hero-compact">
                <div class="doc-breadcrumbs">
                    <a href="/">Keyword Forge</a>
                    <span>/</span>
                    <span>제목 프롬프트</span>
                </div>
                <div class="doc-hero-copy">
                    <p class="panel-kicker">Title Prompt</p>
                    <h1>AI 제목 프롬프트 관리</h1>
                    <p>
                        기본 시스템 프롬프트와 선택된 프리셋 안내는 계속 고정됩니다.
                        여기서는 그 뒤에 붙는 사용자 저장본을 만들고, 저장하고, 불러와서 현재 적용본으로 바꿀 수 있습니다.
                    </p>
                </div>
                <div class="title-prompt-guide">
                    <div class="title-prompt-guide-card">
                        <strong>현재 구조</strong>
                        <p>기본 시스템 프롬프트 + 선택한 프리셋 안내 + 저장본 또는 직접 입력 지침 순서로 실제 프롬프트가 구성됩니다.</p>
                    </div>
                    <div class="title-prompt-guide-card">
                        <strong>권장 운영</strong>
                        <p>홈판형, 리뷰형, 보수형 같은 저장본을 따로 만들어 두고 필요할 때 선택해서 쓰는 방식이 가장 관리하기 쉽습니다.</p>
                    </div>
                </div>
            </section>

            <section class="panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Preview</p>
                        <h2>현재 적용 프롬프트 미리보기</h2>
                    </div>
                    <span class="status-pill" id="titlePromptEditorStatus">불러오는 중</span>
                </div>
                <div class="form-grid">
                    <div class="field-block">
                        <span class="field-label">현재 프리셋</span>
                        <div id="titlePromptPresetLabel" class="title-prompt-summary">불러오는 중</div>
                    </div>
                    <div class="field-block">
                        <span class="field-label">현재 적용 저장본</span>
                        <div id="titlePromptAppliedProfile" class="title-prompt-summary">불러오는 중</div>
                    </div>
                    <label class="field-block field-block-wide">
                        <span class="field-label">기본 시스템 + 프리셋 안내</span>
                        <textarea
                            id="titlePromptBasePreview"
                            class="title-prompt-textarea"
                            rows="14"
                            readonly
                        ></textarea>
                    </label>
                    <label class="field-block field-block-wide">
                        <span class="field-label">실제 적용 프롬프트 전체 미리보기</span>
                        <textarea
                            id="titlePromptEffectivePreview"
                            class="title-prompt-textarea"
                            rows="18"
                            readonly
                        ></textarea>
                    </label>
                </div>
            </section>

            <section class="panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Profiles</p>
                        <h2>저장본 편집 및 선택</h2>
                    </div>
                    <span class="status-pill" id="titlePromptProfileStatus">저장본 불러오는 중</span>
                </div>
                <div class="form-grid">
                    <label class="field-block">
                        <span class="field-label">저장본 선택</span>
                        <select id="titlePromptProfileSelect"></select>
                    </label>
                    <label class="field-block">
                        <span class="field-label">저장본 이름</span>
                        <input
                            id="titlePromptProfileName"
                            type="text"
                            maxlength="40"
                            placeholder="예: 홈판 공격형"
                        />
                    </label>
                </div>
                <label class="field-block field-block-wide">
                    <span class="field-label">추가 지침 편집</span>
                    <textarea
                        id="titlePromptEditorInput"
                        class="title-prompt-textarea"
                        rows="16"
                        placeholder="예: 키워드는 항상 제목 맨 앞에 두고, 홈판용은 최신 이슈를 우선 반영하며, 과장형 금지 표현은 더 엄격하게 적용하세요."
                    ></textarea>
                </label>
                <p class="input-help compact-help">
                    저장본을 선택한 뒤 저장하면 메인 화면에서 바로 적용됩니다. 직접 입력으로 두면 저장본 없이 현재 지침만 적용합니다.
                </p>
                <div class="doc-actions title-prompt-actions">
                    <button type="button" class="subtle-btn" id="saveTitlePromptButton">현재 적용 저장</button>
                    <button type="button" class="ghost-btn" id="saveAsTitlePromptButton">새 저장본</button>
                    <button type="button" class="ghost-btn" id="deleteTitlePromptButton">저장본 삭제</button>
                    <button type="button" class="ghost-btn" id="clearTitlePromptEditorButton">현재 비우기</button>
                    <button type="button" class="ghost-chip" id="closeTitlePromptEditorButton">탭 닫기</button>
                </div>
            </section>
        </div>
    </main>
    <script>
        (function() {{
            const STORAGE_KEY = "keyword_forge_title_settings";
            const presets = Array.isArray(window.KEYWORD_FORGE_TITLE_PRESETS) ? window.KEYWORD_FORGE_TITLE_PRESETS : [];
            const presetMap = presets.reduce((map, item) => {{
                const key = String(item && item.key || "").trim();
                if (key) {{
                    map[key] = item;
                }}
                return map;
            }}, {{}});
            const defaultSystemPrompt = String(window.KEYWORD_FORGE_TITLE_DEFAULT_SYSTEM_PROMPT || "").replace(/\\r\\n/g, "\\n").trim();
            const defaultPresetKey = String(window.KEYWORD_FORGE_TITLE_DEFAULT_PRESET_KEY || "").trim();
            const input = document.getElementById("titlePromptEditorInput");
            const status = document.getElementById("titlePromptEditorStatus");
            const profileStatus = document.getElementById("titlePromptProfileStatus");
            const profileSelect = document.getElementById("titlePromptProfileSelect");
            const profileNameInput = document.getElementById("titlePromptProfileName");
            const presetLabel = document.getElementById("titlePromptPresetLabel");
            const appliedProfile = document.getElementById("titlePromptAppliedProfile");
            const basePreview = document.getElementById("titlePromptBasePreview");
            const effectivePreview = document.getElementById("titlePromptEffectivePreview");
            const saveButton = document.getElementById("saveTitlePromptButton");
            const saveAsButton = document.getElementById("saveAsTitlePromptButton");
            const deleteButton = document.getElementById("deleteTitlePromptButton");
            const clearButton = document.getElementById("clearTitlePromptEditorButton");
            const closeButton = document.getElementById("closeTitlePromptEditorButton");

            function readSettings() {{
                try {{
                    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{{}}");
                }} catch (error) {{
                    return {{}};
                }}
            }}

            function writeSettings(settings) {{
                window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
            }}

            function normalizePrompt(value) {{
                return String(value || "").replace(/\\r\\n/g, "\\n").trim();
            }}

            function normalizeProfileName(value) {{
                return String(value || "").replace(/\\s+/g, " ").trim();
            }}

            function normalizeProfileId(value) {{
                return String(value || "").trim();
            }}

            function resolveDirectPrompt(settings) {{
                const directPrompt = normalizePrompt(settings.direct_system_prompt || "");
                if (directPrompt) {{
                    return directPrompt;
                }}
                return normalizePrompt(settings.system_prompt || "");
            }}

            function normalizePromptProfiles(value) {{
                if (!Array.isArray(value)) {{
                    return [];
                }}
                const seenIds = new Set();
                const output = [];
                value.forEach((item, index) => {{
                    if (!item || typeof item !== "object") {{
                        return;
                    }}
                    const id = normalizeProfileId(item.id || `profile-${{index + 1}}`);
                    const name = normalizeProfileName(item.name || `저장본 ${{output.length + 1}}`);
                    const prompt = normalizePrompt(item.prompt);
                    if (!id || seenIds.has(id)) {{
                        return;
                    }}
                    seenIds.add(id);
                    output.push({{
                        id,
                        name,
                        prompt,
                        updated_at: String(item.updated_at || "").trim(),
                    }});
                }});
                return output;
            }}

            function createProfileId() {{
                return `profile-${{Date.now()}}-${{Math.random().toString(36).slice(2, 8)}}`;
            }}

            function getPresetFromSettings(settings) {{
                const presetKey = String(settings.preset_key || "").trim().toLowerCase();
                return presetMap[presetKey] || presetMap[defaultPresetKey] || null;
            }}

            function resolveActiveProfile(settings, profiles = normalizePromptProfiles(settings.prompt_profiles)) {{
                const activeProfileId = normalizeProfileId(settings.active_prompt_profile_id);
                return profiles.find((profile) => profile.id === activeProfileId) || null;
            }}

            function resolveAppliedPrompt(settings, profiles = normalizePromptProfiles(settings.prompt_profiles)) {{
                const activeProfile = resolveActiveProfile(settings, profiles);
                if (activeProfile) {{
                    return activeProfile.prompt;
                }}
                return resolveDirectPrompt(settings);
            }}

            function buildBasePrompt(settings) {{
                const sections = [defaultSystemPrompt];
                const preset = getPresetFromSettings(settings);
                const presetPrompt = normalizePrompt(preset && preset.prompt_guidance || "");
                if (presetPrompt) {{
                    sections.push(`Preset guidance:\\n${{presetPrompt}}`);
                }}
                return sections.filter(Boolean).join("\\n\\n");
            }}

            function buildEffectivePrompt(settings, promptValue) {{
                const sections = [buildBasePrompt(settings)];
                const extraPrompt = normalizePrompt(promptValue);
                if (extraPrompt) {{
                    sections.push(`Additional guidance:\\n${{extraPrompt}}`);
                }}
                return sections.filter(Boolean).join("\\n\\n");
            }}

            function updateStatus(message, kind) {{
                status.textContent = message;
                status.classList.remove("success", "error");
                if (kind) {{
                    status.classList.add(kind);
                }}
            }}

            function updateProfileStatus(message, kind) {{
                profileStatus.textContent = message;
                profileStatus.classList.remove("success", "error");
                if (kind) {{
                    profileStatus.classList.add(kind);
                }}
            }}

            function renderProfileOptions(settings, selectedProfileId = "") {{
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const activeProfileId = normalizeProfileId(selectedProfileId || settings.active_prompt_profile_id);
                profileSelect.innerHTML = "";

                const directOption = document.createElement("option");
                directOption.value = "";
                directOption.textContent = profiles.length ? "직접 입력 / 저장본 미선택" : "직접 입력";
                profileSelect.appendChild(directOption);

                profiles.forEach((profile) => {{
                    const option = document.createElement("option");
                    option.value = profile.id;
                    option.textContent = profile.name;
                    profileSelect.appendChild(option);
                }});

                profileSelect.value = activeProfileId;
                if (profileSelect.value !== activeProfileId) {{
                    profileSelect.value = "";
                }}
            }}

            function updatePreview(settings) {{
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const selectedProfile = profiles.find((profile) => profile.id === normalizeProfileId(profileSelect.value)) || null;
                const promptValue = normalizePrompt(input.value);
                const preset = getPresetFromSettings(settings);

                presetLabel.textContent = preset
                    ? `${{preset.label}} / ${{preset.provider}} / ${{preset.model}} / temperature ${{preset.temperature}}`
                    : "직접 설정";
                appliedProfile.textContent = selectedProfile
                    ? `저장본 적용 예정: ${{selectedProfile.name}}`
                    : (promptValue ? "직접 입력 적용 예정" : "추가 지침 없음");
                basePreview.value = buildBasePrompt(settings);
                effectivePreview.value = buildEffectivePrompt(settings, promptValue);
            }}

            function loadEditorState(selectedProfileId = "") {{
                const settings = readSettings();
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const activeProfile = resolveActiveProfile(settings, profiles);
                renderProfileOptions(settings, selectedProfileId || (activeProfile && activeProfile.id) || "");

                const selectedProfile = profiles.find((profile) => profile.id === normalizeProfileId(profileSelect.value)) || null;
                if (selectedProfile) {{
                    profileNameInput.value = selectedProfile.name;
                    input.value = selectedProfile.prompt;
                }} else {{
                    profileNameInput.value = "";
                    input.value = resolveDirectPrompt(settings);
                }}

                deleteButton.disabled = !selectedProfile;
                updatePreview(settings);
                updateStatus(
                    input.value
                        ? `현재 추가 지침 ${{input.value.length}}자`
                        : "기본 시스템 프롬프트만 사용 중",
                );
                updateProfileStatus(
                    selectedProfile
                        ? `선택 저장본: ${{selectedProfile.name}}`
                        : `저장본 ${{profiles.length}}개 / 직접 입력`,
                );
            }}

            function saveCurrentPrompt() {{
                const settings = readSettings();
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const selectedProfileId = normalizeProfileId(profileSelect.value);
                const prompt = normalizePrompt(input.value);
                const name = normalizeProfileName(profileNameInput.value);

                if (selectedProfileId) {{
                    const nextProfiles = profiles.map((profile) => (
                        profile.id === selectedProfileId
                            ? {{
                                ...profile,
                                name: name || profile.name,
                                prompt,
                                updated_at: new Date().toISOString(),
                            }}
                            : profile
                    ));
                    writeSettings({{
                        ...settings,
                        prompt_profiles: nextProfiles,
                        active_prompt_profile_id: selectedProfileId,
                        direct_system_prompt: resolveDirectPrompt(settings),
                        system_prompt: prompt,
                    }});
                    loadEditorState(selectedProfileId);
                    updateStatus(`저장됨 · ${{prompt.length}}자`, "success");
                    updateProfileStatus(`저장본 업데이트: ${{name || "이름 없음"}}`, "success");
                    return;
                }}

                writeSettings({{
                    ...settings,
                    active_prompt_profile_id: "",
                    direct_system_prompt: prompt,
                    system_prompt: prompt,
                }});
                loadEditorState("");
                updateStatus(prompt ? `직접 입력 저장됨 · ${{prompt.length}}자` : "기본 시스템 프롬프트만 사용 중", "success");
                updateProfileStatus("직접 입력 적용", "success");
            }}

            function saveAsNewProfile() {{
                const settings = readSettings();
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const prompt = normalizePrompt(input.value);
                const name = normalizeProfileName(profileNameInput.value) || `저장본 ${{profiles.length + 1}}`;
                const newProfileId = createProfileId();
                const nextProfiles = [
                    ...profiles,
                    {{
                        id: newProfileId,
                        name,
                        prompt,
                        updated_at: new Date().toISOString(),
                    }},
                ];

                writeSettings({{
                    ...settings,
                    prompt_profiles: nextProfiles,
                    active_prompt_profile_id: newProfileId,
                    direct_system_prompt: resolveDirectPrompt(settings),
                    system_prompt: prompt,
                }});
                loadEditorState(newProfileId);
                updateStatus(`새 저장본 저장됨 · ${{prompt.length}}자`, "success");
                updateProfileStatus(`저장본 생성: ${{name}}`, "success");
            }}

            function deleteSelectedProfile() {{
                const settings = readSettings();
                const profiles = normalizePromptProfiles(settings.prompt_profiles);
                const selectedProfileId = normalizeProfileId(profileSelect.value);
                if (!selectedProfileId) {{
                    updateProfileStatus("삭제할 저장본이 없습니다.", "error");
                    return;
                }}

                const nextProfiles = profiles.filter((profile) => profile.id !== selectedProfileId);
                const directPrompt = resolveDirectPrompt(settings);
                writeSettings({{
                    ...settings,
                    prompt_profiles: nextProfiles,
                    active_prompt_profile_id: "",
                    direct_system_prompt: directPrompt,
                    system_prompt: directPrompt,
                }});
                loadEditorState("");
                updateStatus(
                    directPrompt
                        ? `직접 입력 유지 · ${{directPrompt.length}}자`
                        : "기본 시스템 프롬프트만 사용 중",
                    "success",
                );
                updateProfileStatus("저장본 삭제 완료", "success");
            }}

            function clearCurrentPrompt() {{
                input.value = "";
                updatePreview(readSettings());
                updateStatus("현재 입력 비움");
            }}

            saveButton.addEventListener("click", saveCurrentPrompt);
            saveAsButton.addEventListener("click", saveAsNewProfile);
            deleteButton.addEventListener("click", deleteSelectedProfile);
            clearButton.addEventListener("click", () => {{
                clearCurrentPrompt();
            }});
            closeButton.addEventListener("click", () => {{
                window.close();
            }});
            profileSelect.addEventListener("change", () => {{
                loadEditorState(profileSelect.value);
            }});
            input.addEventListener("input", () => {{
                updatePreview(readSettings());
                updateStatus(
                    input.value
                        ? `현재 추가 지침 ${{normalizePrompt(input.value).length}}자`
                        : "기본 시스템 프롬프트만 사용 중",
                );
            }});
            input.addEventListener("keydown", (event) => {{
                if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {{
                    event.preventDefault();
                    saveCurrentPrompt();
                }}
            }});

            loadEditorState();
        }})();
    </script>
    """
    return _render_static_shell(
        title="제목 프롬프트 편집",
        description="AI 제목 생성용 추가 시스템 프롬프트를 수정합니다.",
        body=body,
    )


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
    queue_routine_category_picker = _render_queue_routine_category_picker()
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
    title_presets = build_title_preset_payload()
    title_preset_options = "".join(
        f'<option value="{escape(str(item["key"]))}"{" selected" if item["key"] == DEFAULT_TITLE_PRESET_KEY else ""}>'
        f'{escape(str(item["label"]))}'
        "</option>"
        for item in title_presets
    )
    title_preset_payload = json.dumps(title_presets, ensure_ascii=False).replace("</", "<\\/")
    title_mode_help = _render_help_tooltip(
        "template는 규칙 기반으로 바로 생성합니다.\n"
        "AI는 provider/model을 사용해 더 유연하게 생성하고, 저점수 자동 재작성도 함께 쓸 수 있습니다.\n"
        "Vertex AI는 Express Mode API key로 붙이면 Google Cloud 크레딧/쿼터 체계로 운용할 수 있습니다."
    )
    title_keyword_modes_help = _render_help_tooltip(
        "단일은 안전형입니다.\n"
        "V1은 선별 결과 기반 롱테일입니다.\n"
        "V2는 관련 탈락 키워드 연계 확장입니다.\n"
        "V3는 저검색량까지 넓히는 실험형입니다."
    )
    title_auto_retry_help = _render_help_tooltip(
        "AI 모드에서 품질 점수가 기준보다 낮은 제목만 1회 더 다시 생성합니다.\n"
        "기준 점수를 올리면 더 엄격하게 다시 쓰고, 너무 높이면 호출량과 시간이 늘어납니다."
    )
    title_issue_context_help = _render_help_tooltip(
        "AI 제목 생성 직전에 네이버 검색 상위 결과를 확인해 최근 뉴스/이슈 표현을 프롬프트에 반영합니다.\n"
        "조회 개수는 이번 호출에서 실시간 맥락을 붙일 키워드 수입니다. 높일수록 느려질 수 있습니다."
    )
    title_api_key_help = _render_help_tooltip(
        "API 키는 서버에 저장하지 않고 현재 브라우저 localStorage에만 보관합니다.\n"
        "Gemini는 Google AI Studio 키, Vertex AI는 Express Mode API key를 사용합니다."
    )
    title_prompt_help = _render_help_tooltip(
        "새 탭에서 제목 생성용 추가 지침을 수정합니다. 저장하면 현재 작업대에 바로 반영됩니다."
    )
    creator_login_help = _render_help_tooltip(
        "전용 프로필에서 로그인하면 세션을 저장해 다음 수집에 바로 사용합니다."
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
    <script>
        window.KEYWORD_FORGE_TITLE_PRESETS = {title_preset_payload};
    </script>
    <link rel="stylesheet" href="/assets/app.css?v={_ASSET_VERSION}" />
    <script src="/assets/app.js?v={_ASSET_VERSION}" defer></script>
    <script src="/assets/app_overrides.js?v={_ASSET_VERSION}" defer></script>
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

            <div class="control-column">
            <section class="panel settings-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Popup</p>
                        <h2>설정</h2>
                    </div>
                </div>
                <p class="input-help compact-help settings-panel-note">
                    운영 제한과 예약 작업은 팝업으로 열어 관리합니다. 실행 로그와 진단은 아래 작업대에서도 바로 확인할 수 있습니다.
                </p>
                <div class="settings-shortcut-row">
                    <button type="button" class="ghost-chip" data-utility-open="settings" aria-pressed="false">운영 설정</button>
                    <button type="button" class="ghost-chip" data-utility-open="queue" aria-pressed="false">예약 / Queue</button>
                </div>
            </section>

            <section class="panel control-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Input</p>
                        <h2>실행 조건</h2>
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
                            <span class="field-label field-label-row">
                                <span>Creator Advisor 로그인</span>
                                {creator_login_help}
                            </span>
                            <input
                                id="trendCookieInput"
                                type="hidden"
                                value=""
                            />
                            <button type="button" class="primary-btn session-helper-btn" id="launchLoginBrowserButton">로그인</button>
                            <p class="input-help session-helper-status" id="localCookieStatus">
                                저장된 전용 로그인 세션을 확인하는 중입니다.
                            </p>
                        </div>
                    </div>

                    <label class="field-block" data-mode-visibility="seed" hidden>
                        <span class="field-label">시드 키워드</span>
                        <input id="seedInput" type="text" placeholder="예: 보험" />
                    </label>

                    <div class="field-block field-block-wide collector-inline-actions">
                        <div class="collector-action-row">
                            <button type="button" class="subtle-btn collector-run-btn" data-run-action="collect">수집만 실행</button>
                            <div class="collector-option-row">
                                <label class="launcher-toggle-chip collector-toggle-chip">
                                    <input id="optionRelated" type="checkbox" checked />
                                    <span>연관 키워드 수집</span>
                                </label>
                                <label class="launcher-toggle-chip collector-toggle-chip">
                                    <input id="optionAutocomplete" type="checkbox" checked />
                                    <span>자동완성 우선 사용</span>
                                </label>
                                <label class="launcher-toggle-chip collector-toggle-chip">
                                    <input id="optionDebug" type="checkbox" checked />
                                    <span>디버그 정보 포함</span>
                                </label>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="option-row collect-category-options" data-mode-visibility="category">
                    <label class="check-chip"><input id="optionBulk" type="checkbox" checked />카테고리 다중 쿼리 사용</label>
                    <label class="check-chip"><input id="trendFallbackInput" type="checkbox" />트렌드 실패 시 preset fallback</label>
                </div>

                <p class="input-help" id="trendSourceHelp" data-mode-visibility="category">
                    카테고리 모드에서 네이버 트렌드를 고르면 Creator Advisor 주제 기반 인기 키워드를 먼저 조회합니다.
                    입력 칸이 비어 있어도 저장된 전용 로그인 세션이 있으면 자동으로 사용하고, 세션이 없거나 실패하면 아래 fallback 설정에 따라 검색 preset으로 전환합니다.
                </p>

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
                <section class="grade-select-panel pipeline-grade-select">
                    <div class="grade-select-head">
                        <div>
                            <span class="field-label">2축 선별</span>
                            <p class="grade-select-summary" id="gradeSelectSummary">수익성 전체 · 공략성 전체</p>
                        </div>
                        <p class="input-help compact-help">수익성 A~D와 공략성 1~4를 조합해 선별합니다. 기본 골든 후보는 A~C · 1~3 조합입니다.</p>
                    </div>
                    <div class="grade-select-presets">
                        <button type="button" class="ghost-chip" data-selection-preset="all">전체</button>
                        <button type="button" class="ghost-chip" data-selection-preset="golden_candidate">골든 후보</button>
                        <button type="button" class="ghost-chip" data-selection-preset="profit_focus">수익형 집중</button>
                        <button type="button" class="ghost-chip" data-selection-preset="easy_exposure">쉬운 노출</button>
                    </div>
                    <div class="grade-select-row grade-select-axis-row">
                        <span class="grade-select-axis-label">수익성</span>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="A">A</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="B">B</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="C">C</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-profitability-toggle="D">D</button>
                    </div>
                    <div class="grade-select-row grade-select-axis-row">
                        <span class="grade-select-axis-label">공략성</span>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="1">1</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="2">2</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="3">3</button>
                        <button type="button" class="ghost-chip grade-toggle-chip" data-attackability-toggle="4">4</button>
                        <button type="button" class="subtle-btn grade-select-run" id="runGradeSelectButton">선택 조합 선별</button>
                    </div>
                </section>
                <p class="input-help compact-help">
                    상단 실행 버튼은 현재 입력값 기준으로 새로 시작합니다. 결과 카드의 `이 결과로 ...` 버튼은 지금 화면의 결과를 이어서 사용합니다.
                </p>

                </section>

                </div>
            </section>
            </div>

            <section class="panel launcher-panel">
                <div class="panel-head">
                    <div>
                        <p class="panel-kicker">Launcher</p>
                        <h2>시작점</h2>
                    </div>
                </div>
                <p class="input-help compact-help launcher-panel-note">
                    현재 결과를 이어서 쓰거나 직접 붙여넣기로 확장, 분석, 제목 생성을 시작합니다.
                </p>

                <div class="control-launcher-column">
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
                                <div class="option-row launcher-toggle-row">
                                    <label class="launcher-toggle-chip">
                                        <input id="expandOptionRelated" type="checkbox" checked />
                                        <span>연관확장</span>
                                    </label>
                                    <label class="launcher-toggle-chip">
                                        <input id="expandOptionAutocomplete" type="checkbox" checked />
                                        <span>자동완성</span>
                                    </label>
                                    <label class="launcher-toggle-chip">
                                        <input id="expandOptionSeedFilter" type="checkbox" checked />
                                        <span>원문포함</span>
                                    </label>
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

                <section class="title-settings-card launcher-card control-stage-block control-stage-title" data-control-block="title">
                    <div class="launcher-head">
                        <div>
                            <p class="panel-kicker">Title Entry</p>
                            <h3>제목 생성 시작점</h3>
                        </div>
                        <span class="badge" id="titleModeBadge">template</span>
                    </div>
                    <div class="form-grid">
                        <input id="titleMode" type="hidden" value="template" />

                        <div class="field-block mode-block title-mode-block">
                            <span class="field-label field-label-row">
                                <span>제목 생성 모드</span>
                                {title_mode_help}
                            </span>
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

                        <div class="field-block field-block-wide">
                            <span class="field-label field-label-row">
                                <span>제목 키워드 조합</span>
                                {title_keyword_modes_help}
                            </span>
                            <div class="option-row" id="titleKeywordModes">
                                <label class="check-chip"><input id="titleModeSingle" type="checkbox" checked />단일 키워드</label>
                                <label class="check-chip"><input id="titleModeLongtailSelected" type="checkbox" checked />롱테일 V1</label>
                                <label class="check-chip"><input id="titleModeLongtailExploratory" type="checkbox" />롱테일 V2</label>
                                <label class="check-chip"><input id="titleModeLongtailExperimental" type="checkbox" />롱테일 V3</label>
                            </div>
                            <p id="titleKeywordModeSummary" class="input-help compact-help">
                                선택: 단일 + V1
                            </p>
                        </div>

                        <div class="title-advanced-toggle-row">
                            <button
                                type="button"
                                class="ghost-chip title-advanced-toggle"
                                id="toggleTitleAdvancedButton"
                                aria-expanded="false"
                                aria-controls="titleAdvancedSettings"
                            >추가설정</button>
                            <p class="input-help compact-help title-advanced-copy">
                                자동 재시도, AI 소스 반영, 모델, 프롬프트, API 설정을 펼쳐서 봅니다.
                            </p>
                        </div>

                        <div id="titleAdvancedSettings" class="title-advanced-settings" hidden>
                        <div class="field-block field-block-wide">
                            <span class="field-label field-label-row">
                                <span>저점수 자동 재작성</span>
                                {title_auto_retry_help}
                            </span>
                            <div class="title-auto-retry-row">
                                <label class="check-chip"><input id="titleAutoRetryEnabled" type="checkbox" checked />기준 미달 제목 1회 자동 재작성</label>
                                <label class="title-auto-retry-threshold">
                                    <span>최소 점수</span>
                                    <input id="titleAutoRetryThreshold" type="number" min="70" max="100" step="1" value="84" />
                                </label>
                            </div>
                            <p id="titleAutoRetrySummary" class="input-help compact-help">
                                84점 미만만 자동 재작성
                            </p>
                        </div>

                        <div class="field-block field-block-wide" data-title-mode-visibility="ai" hidden>
                            <span class="field-label field-label-row">
                                <span>실시간 이슈 반영</span>
                                {title_issue_context_help}
                            </span>
                            <div class="title-auto-retry-row">
                                <label class="check-chip"><input id="titleIssueContextEnabled" type="checkbox" checked />네이버 검색 상위 뉴스/콘텐츠 이슈 반영</label>
                                <label class="title-auto-retry-threshold">
                                    <span>조회 개수</span>
                                    <input id="titleIssueContextLimit" type="number" min="1" max="5" step="1" value="3" />
                                </label>
                            </div>
                            <p id="titleIssueContextSummary" class="input-help compact-help">
                                AI 요청당 상위 3개 키워드에 실시간 이슈 반영
                            </p>
                        </div>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label field-label-row">
                                <span>프롬프트 / 모델 프리셋</span>
                                <span class="inline-help">
                                    <button type="button" class="help-icon-btn" aria-label="프리셋 도움말">?</button>
                                    <span id="titlePresetDescription" class="help-tooltip">홈판 이슈형을 기본값으로 두고, 필요하면 직접 설정으로 바꿔 세부값을 조정합니다.</span>
                                </span>
                            </span>
                            <select id="titlePreset">
                                {title_preset_options}
                            </select>
                        </label>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">AI Provider</span>
                            <select id="titleProvider">
                                <option value="openai">OpenAI</option>
                                <option value="gemini">Gemini</option>
                                <option value="vertex">Vertex AI</option>
                                <option value="anthropic">Anthropic</option>
                            </select>
                        </label>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">Model</span>
                            <select id="titleModel"></select>
                        </label>

                        <label class="field-block field-block-wide" data-title-mode-visibility="ai" hidden>
                            <span class="field-label field-label-row">
                                <span>API Key</span>
                                {title_api_key_help}
                            </span>
                            <input id="titleApiKey" type="password" placeholder="브라우저에만 저장됩니다." />
                        </label>

                        <div class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label field-label-row">
                                <span>창의성 프리셋</span>
                                <span class="inline-help">
                                    <button type="button" class="help-icon-btn" aria-label="창의성 프리셋 도움말">?</button>
                                    <span id="titleTemperatureDescription" class="help-tooltip">규칙 준수와 표현 다양성의 균형이 가장 무난한 기본값입니다.</span>
                                </span>
                            </span>
                            <select id="titleTemperature">
                                <option value="0.2">안정형</option>
                                <option value="0.5">절충형</option>
                                <option value="0.7">(추천) 균형형</option>
                                <option value="1.0">확장형</option>
                            </select>
                        </div>

                        <label class="field-block" data-title-mode-visibility="ai" hidden>
                            <span class="field-label">Fallback</span>
                            <label class="check-chip"><input id="titleFallback" type="checkbox" checked />AI 실패 시 template 사용</label>
                        </label>

                        <div class="field-block field-block-wide title-prompt-block" data-title-mode-visibility="ai" hidden>
                            <div class="title-prompt-head">
                                <div>
                                    <span class="field-label field-label-row">
                                        <span>AI 프롬프트</span>
                                        {title_prompt_help}
                                    </span>
                                </div>
                            <div class="title-prompt-actions">
                                    <button type="button" class="ghost-chip" id="openTitlePromptEditorButton">프롬프트 편집</button>
                                    <button type="button" class="ghost-chip" id="clearTitlePromptButton">비우기</button>
                                </div>
                            </div>
                            <label class="field-block">
                                <span class="field-label">저장본 선택</span>
                                <select id="titlePromptProfilePicker">
                                    <option value="">직접 입력</option>
                                </select>
                            </label>
                            <div id="titlePromptSummary" class="title-prompt-summary">추가 지침 없음</div>
                            <input id="titleSystemPrompt" type="hidden" value="" />
                        </div>
                        </div>
                    </div>
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
                <div class="results-panel-tools">
                    <button type="button" class="ghost-chip" data-utility-open="diagnostics" aria-pressed="false">오류 / 진단</button>
                    <button type="button" class="ghost-chip" data-utility-open="logs" aria-pressed="false">실행 로그</button>
                    <button type="button" class="ghost-chip" id="exportTitleCsvButton">제목 결과 CSV</button>
                </div>
                <div id="resultsGrid" class="results-grid"></div>
            </section>
        </main>
        <div id="utilityDrawer" class="utility-drawer" hidden>
            <button type="button" class="utility-drawer-backdrop" id="utilityDrawerBackdrop" aria-label="보조 패널 닫기"></button>
            <section class="utility-drawer-panel">
                <div class="utility-drawer-head">
                    <div class="utility-drawer-tabs">
                        <button type="button" class="ghost-chip" data-utility-tab="settings" aria-pressed="false">운영 설정</button>
                        <button type="button" class="ghost-chip" data-utility-tab="queue" aria-pressed="false">예약 / Queue</button>
                        <button type="button" class="ghost-chip" data-utility-tab="diagnostics" aria-pressed="true">오류 / 진단</button>
                        <button type="button" class="ghost-chip" data-utility-tab="logs" aria-pressed="false">실행 로그</button>
                    </div>
                    <button type="button" class="ghost-btn" id="utilityDrawerClose">닫기</button>
                </div>
                <div class="utility-drawer-body">
                    <section class="utility-drawer-view" data-utility-panel="settings" hidden>
                        <div class="settings-shell">
                            <div class="settings-hero">
                                <div>
                                    <p class="panel-kicker">Ops</p>
                                    <h2>운영 설정</h2>
                                    <p class="settings-copy">
                                        예약모드와 장시간 실행을 대비해 요청 간격, 일일 한도, 인증 오류 보호를 여기서 관리합니다.
                                    </p>
                                </div>
                                <div class="settings-hero-actions">
                                    <button type="button" class="ghost-chip" id="refreshOperationSettingsButton">새로고침</button>
                                    <button type="button" class="ghost-chip" id="resetOperationGuardsButton">보호 잠금 해제</button>
                                    <button type="button" class="ghost-btn" id="saveOperationSettingsButton">저장 후 적용</button>
                                </div>
                            </div>
                            <div class="settings-status-grid">
                                <article class="collector-stat-card">
                                    <span>현재 모드</span>
                                    <strong id="operationModeStatus">상시 슬로우</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>오늘 작업</span>
                                    <strong id="operationDailyUsage">0 / 제한 없음</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>오늘 Naver 요청</span>
                                    <strong id="operationRequestUsage">0 / 제한 없음</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>보호 상태</span>
                                    <strong id="operationGuardStatus">정상</strong>
                                </article>
                            </div>
                            <div class="settings-panel-grid">
                                <section class="settings-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">Mode</p>
                                            <h3>운영 모드</h3>
                                        </div>
                                    </div>
                                    <div class="field-block">
                                        <span class="field-label">모드 선택</span>
                                        <select id="operationMode">
                                            <option value="daily_light">일일 10회 이하</option>
                                            <option value="always_on_slow">상시 슬로우</option>
                                            <option value="custom">직접 설정</option>
                                        </select>
                                    </div>
                                    <div id="operationModeDescription" class="collector-empty">
                                        상시 슬로우를 기본으로 두고, 작업 횟수나 요청 한도가 필요하면 다른 모드로 바꿉니다.
                                    </div>
                                    <div id="operationCustomModeGuide" class="settings-hint">
                                        `직접 설정`을 고르면 새 창이 뜨지 않고, 바로 오른쪽 `보호 옵션`이 편집 가능해집니다. 먼저 추천값을 불러온 뒤 필요한 부분만 조절하면 됩니다.
                                    </div>
                                </section>
                                <section class="settings-card" id="operationGuardCard">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">Guard</p>
                                            <h3>보호 옵션</h3>
                                        </div>
                                    </div>
                                    <div id="operationCustomPresetPanel" class="operation-custom-panel" hidden>
                                        <div class="operation-custom-head">
                                            <strong>추천 조절</strong>
                                            <span>숫자를 직접 다 정하지 말고 `안전 / 추천 / 빠름` 중 하나를 먼저 고른 뒤, 아래 값만 미세 조정하세요.</span>
                                        </div>
                                        <div class="operation-custom-chip-row">
                                            <button type="button" class="ghost-chip" data-operation-custom-preset="safe">안전</button>
                                            <button type="button" class="ghost-chip" data-operation-custom-preset="balanced">추천</button>
                                            <button type="button" class="ghost-chip" data-operation-custom-preset="fast">빠름</button>
                                        </div>
                                        <div id="operationCustomPresetDescription" class="collector-empty">
                                            추천값 설명을 불러오는 중입니다.
                                        </div>
                                    </div>
                                    <div class="settings-form-grid">
                                        <label class="field-block">
                                            <span class="field-label">Naver 요청 간격(초)</span>
                                            <input id="operationRequestGap" type="number" min="0" max="120" step="0.5" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">하루 작업 시작 상한</span>
                                            <input id="operationDailyLimit" type="number" min="0" max="1000" step="1" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">하루 Naver 요청 상한</span>
                                            <input id="operationDailyRequestLimit" type="number" min="0" max="100000" step="1" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">연속 실행 보호(분)</span>
                                            <input id="operationMaxContinuousMinutes" type="number" min="0" max="1440" step="5" />
                                        </label>
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">인증 오류 보호</span>
                                            <label class="check-chip">
                                                <input id="operationStopOnAuthError" type="checkbox" checked />
                                                401/403 감지 시 이후 요청 자동 중지
                                            </label>
                                        </label>
                                    </div>
                                    <div id="operationSettingsHint" class="settings-hint">
                                        0을 넣으면 해당 상한은 해제됩니다. 저장 후 즉시 서버 런타임에 반영됩니다.
                                    </div>
                                    <div id="operationSettingsSyncStatus" class="collector-empty">
                                        서버 런타임 상태를 불러오는 중입니다.
                                    </div>
                                </section>
                            </div>
                        </div>
                    </section>
                    <section class="utility-drawer-view" data-utility-panel="queue" hidden>
                        <div class="queue-shell">
                            <div class="settings-hero">
                                <div>
                                    <p class="panel-kicker">Queue</p>
                                    <h2>예약 작업</h2>
                                    <p class="settings-copy">
                                        현재 화면의 수집, 확장, 분석, 제목 설정을 묶어서 시드 배치 Queue나 일일 카테고리 루틴으로 등록합니다.
                                    </p>
                                </div>
                                <div class="settings-hero-actions">
                                    <button type="button" class="ghost-chip" id="refreshQueueSnapshotButton">새로고침</button>
                                    <button type="button" class="ghost-chip" id="pauseQueueRunnerButton">일시정지</button>
                                    <button type="button" class="ghost-btn" id="resumeQueueRunnerButton">재개</button>
                                </div>
                            </div>
                            <div class="settings-status-grid">
                                <article class="collector-stat-card">
                                    <span>Runner 상태</span>
                                    <strong id="queueRunnerStateLabel">불러오는 중</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>현재 작업</span>
                                    <strong id="queueRunnerJobLabel">대기 중</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>등록된 작업</span>
                                    <strong id="queueJobCountLabel">0건</strong>
                                </article>
                                <article class="collector-stat-card">
                                    <span>엑셀 출력 폴더</span>
                                    <strong id="queueOutputDirLabel">-</strong>
                                </article>
                            </div>
                            <div class="queue-panel-grid">
                                <section class="settings-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">Batch</p>
                                            <h3>시드 배치 Queue</h3>
                                        </div>
                                    </div>
                                    <div class="settings-form-grid">
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">배치 이름</span>
                                            <input id="queueSeedBatchNameInput" type="text" placeholder="예: 3월 4주차 보험 시드" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">예약 시각</span>
                                            <input id="queueSeedBatchScheduleInput" type="datetime-local" />
                                        </label>
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">시드 키워드</span>
                                            <textarea
                                                id="queueSeedBatchSeedsInput"
                                                rows="7"
                                                placeholder="줄바꿈으로 여러 시드를 넣으세요&#10;예:&#10;실비보험 추천&#10;운전자보험 비교"
                                            ></textarea>
                                        </label>
                                    </div>
                                    <div id="queueSeedBatchHint" class="settings-hint">
                                        현재 수집, 확장, 분석, 제목 옵션을 그대로 묶어서 시드별 전체 파이프라인을 순차 실행합니다. API 키나 트렌드 쿠키가 있으면 상태 파일에도 함께 저장됩니다.
                                    </div>
                                    <div class="queue-form-actions">
                                        <span id="queueSeedBatchCountLabel" class="queue-inline-meta">시드 0건</span>
                                        <button type="button" class="ghost-btn" id="submitQueueSeedBatchButton">시드 배치 등록</button>
                                    </div>
                                </section>
                                <section class="settings-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">Routine</p>
                                            <h3>일일 카테고리 루틴</h3>
                                        </div>
                                    </div>
                                    <div class="settings-form-grid">
                                        <label class="field-block field-block-wide">
                                            <span class="field-label">루틴 이름</span>
                                            <input id="queueRoutineNameInput" type="text" placeholder="예: 오전 카테고리 루틴" />
                                        </label>
                                        <label class="field-block">
                                            <span class="field-label">실행 시각</span>
                                            <input id="queueRoutineTimeInput" type="time" value="06:00" />
                                        </label>
                                        <div class="field-block field-block-wide">
                                            <span class="field-label">실행 요일</span>
                                            <div class="queue-weekday-grid">
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="0" data-queue-weekday checked />
                                                    월
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="1" data-queue-weekday checked />
                                                    화
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="2" data-queue-weekday checked />
                                                    수
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="3" data-queue-weekday checked />
                                                    목
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="4" data-queue-weekday checked />
                                                    금
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="5" data-queue-weekday checked />
                                                    토
                                                </label>
                                                <label class="check-chip queue-weekday-chip">
                                                    <input type="checkbox" value="6" data-queue-weekday checked />
                                                    일
                                                </label>
                                            </div>
                                        </div>
                                        <div class="field-block field-block-wide">
                                            <span class="field-label">카테고리 선택</span>
                                            <div class="queue-category-picker">
                                                {queue_routine_category_picker}
                                            </div>
                                        </div>
                                    </div>
                                    <div id="queueRoutineHint" class="settings-hint">
                                        선택한 요일과 시각마다 카테고리 작업을 자동 생성합니다. 앱이 실행 중이어야 내부 예약이 동작하며, 현재 인증 설정도 상태 파일에 저장될 수 있습니다.
                                    </div>
                                    <div class="queue-form-actions">
                                        <span id="queueRoutineCountLabel" class="queue-inline-meta">카테고리 0건</span>
                                        <button type="button" class="ghost-btn" id="submitQueueRoutineButton">루틴 등록</button>
                                    </div>
                                </section>
                            </div>
                            <div class="queue-panel-grid">
                                <section class="settings-card queue-list-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">Jobs</p>
                                            <h3>최근 작업</h3>
                                        </div>
                                    </div>
                                    <div id="queueJobsList" class="queue-item-list">
                                        <div class="collector-empty">등록된 작업이 없습니다.</div>
                                    </div>
                                </section>
                                <section class="settings-card queue-list-card">
                                    <div class="collector-panel-head">
                                        <div>
                                            <p class="panel-kicker">Routines</p>
                                            <h3>등록된 루틴</h3>
                                        </div>
                                    </div>
                                    <div id="queueRoutinesList" class="queue-item-list">
                                        <div class="collector-empty">등록된 루틴이 없습니다.</div>
                                    </div>
                                </section>
                            </div>
                            <div id="queueSnapshotStatus" class="collector-empty">
                                스케줄러 상태를 아직 불러오지 않았습니다.
                            </div>
                        </div>
                    </section>
                    <section class="utility-drawer-view" data-utility-panel="diagnostics">
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
                    <section class="utility-drawer-view" data-utility-panel="logs" hidden>
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
                </div>
            </section>
        </div>
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


@router.get("/title-prompt-editor", response_class=HTMLResponse, include_in_schema=False)
def title_prompt_editor() -> HTMLResponse:
    return HTMLResponse(_render_title_prompt_editor())
