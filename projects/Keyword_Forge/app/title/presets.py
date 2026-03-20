from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TitlePreset:
    key: str
    label: str
    description: str
    provider: str
    model: str
    temperature: float
    prompt_guidance: str


TITLE_PRESETS: tuple[TitlePreset, ...] = (
    TitlePreset(
        key="openai_balanced",
        label="추천 균형형",
        description="기본 추천값입니다. 규칙 준수와 제목 다양성의 균형을 가장 무난하게 맞춥니다.",
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.7,
        prompt_guidance=(
            "Preset focus:\n"
            "- Balance strict keyword preservation with natural editorial phrasing.\n"
            "- Prefer concrete search-intent wording such as comparison, checklist, review, update, and decision point.\n"
            "- Keep titles commercially useful without sounding like boilerplate SEO filler."
        ),
    ),
    TitlePreset(
        key="openai_strict",
        label="안정형 규칙 우선",
        description="길이, 키워드 보존, 중복 억제를 더 엄격하게 잡는 보수형 프리셋입니다.",
        provider="openai",
        model="gpt-4.1-mini",
        temperature=0.2,
        prompt_guidance=(
            "Preset focus:\n"
            "- Put the keyword at the front whenever it reads naturally.\n"
            "- Favor shorter, cleaner titles with less stylistic risk.\n"
            "- Avoid novelty wording and keep each angle obviously distinct."
        ),
    ),
    TitlePreset(
        key="gemini_fast",
        label="빠른 실험형",
        description="속도와 비용을 우선하면서도 검색 의도는 유지하는 빠른 비교용 프리셋입니다.",
        provider="gemini",
        model="gemini-2.5-flash-lite",
        temperature=0.5,
        prompt_guidance=(
            "Preset focus:\n"
            "- Generate clean first-pass titles quickly.\n"
            "- Use direct phrasing and avoid long, winding clauses.\n"
            "- Keep variation visible, but stay conservative on risky creativity."
        ),
    ),
    TitlePreset(
        key="claude_variety",
        label="표현 확장형",
        description="블로그형과 에디터형 문장 골격을 더 넓게 탐색하는 확장 프리셋입니다.",
        provider="anthropic",
        model="claude-sonnet-4-6",
        temperature=1.0,
        prompt_guidance=(
            "Preset focus:\n"
            "- Increase sentence-frame variety across the whole batch.\n"
            "- Favor natural Korean magazine-style phrasing over rigid patterns.\n"
            "- Keep every title specific and useful even when exploring wider variation."
        ),
    ),
)

TITLE_PRESET_MAP = {preset.key: preset for preset in TITLE_PRESETS}
DEFAULT_TITLE_PRESET_KEY = "openai_balanced"
MANUAL_TITLE_PRESET_KEY = "manual"


def get_title_preset(value: str | None) -> TitlePreset | None:
    normalized = str(value or "").strip().lower()
    if not normalized or normalized == MANUAL_TITLE_PRESET_KEY:
        return None
    return TITLE_PRESET_MAP.get(normalized)


def normalize_title_preset_key(value: str | None) -> str:
    preset = get_title_preset(value)
    return preset.key if preset else ""


def build_title_preset_payload(*, include_manual: bool = True) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    if include_manual:
        payload.append(
            {
                "key": MANUAL_TITLE_PRESET_KEY,
                "label": "직접 설정",
                "description": "Provider, 모델, temperature를 직접 고릅니다. 추가 프롬프트는 그대로 함께 사용됩니다.",
                "provider": "",
                "model": "",
                "temperature": None,
                "prompt_guidance": "",
                "is_manual": True,
                "is_default": False,
            }
        )

    for preset in TITLE_PRESETS:
        item = asdict(preset)
        item["is_manual"] = False
        item["is_default"] = preset.key == DEFAULT_TITLE_PRESET_KEY
        payload.append(item)
    return payload
