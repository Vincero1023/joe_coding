from __future__ import annotations

from dataclasses import dataclass
import re

from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.title.hooks import build_trigger_bundle
from app.title.rules import NAVER_HOME_MAX_LENGTH
from app.title.types import CategoryType


_KNOWN_LOCALITY_TOKENS = {
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "수원",
    "평택",
    "성남",
    "용인",
    "고양",
    "창원",
    "제주",
    "천안",
    "안산",
    "청주",
    "전주",
    "김포",
}
_LOCALITY_SUFFIX_RE = re.compile(r"(시|군|구|동|읍|면|역)$")
_SERVICE_TERMS = ("왁싱", "샵", "미용", "네일", "피부", "트리트먼트", "관리", "예약", "상담", "센터")
_PROFILE_TERMS = ("프로필", "작품", "작품활동", "수상", "경력", "이력", "교수", "작가", "감독", "배우", "출연")
_MEDIA_TERMS = ("후기", "리뷰", "인스타", "영상", "동영상", "사진", "평판")
_ACTION_TERMS = ("예약", "가입", "신청", "절차", "방법", "사용법", "등록", "접수")
_PRICE_TERMS = ("가격", "비용", "요금", "견적", "금액", "수강료")
_COMPARISON_TERMS = ("비교", "추천", "순위", "차이", "vs")
_LOCATION_TERMS = ("위치", "코스", "루트", "주차", "장소", "근처", "찾아가는")
_POLICY_TERMS = ("요일", "대상", "기준", "제도", "조회", "조건", "적용", "제한")
_QUESTION_TERMS = ("뜻", "의미", "정리", "개념", "정보")


@dataclass(frozen=True)
class TemplateContext:
    keyword: str
    category: CategoryType
    intent: str
    locality: str
    entity_focus: str
    detail_focus: str
    is_local: bool
    is_service: bool
    is_profile: bool
    is_media: bool
    is_policy: bool


def build_naver_home_titles(keyword: str, category: CategoryType) -> list[str]:
    context = _build_template_context(keyword, category)
    groups = _build_naver_home_groups(context)
    return _select_group_titles(context.keyword, groups, limit=2, max_length=NAVER_HOME_MAX_LENGTH)


def build_blog_titles(keyword: str, category: CategoryType) -> list[str]:
    context = _build_template_context(keyword, category)
    groups = _build_blog_groups(context)
    return _select_group_titles(context.keyword, groups, limit=2)


def _build_template_context(keyword: str, category: CategoryType) -> TemplateContext:
    normalized_keyword = normalize_text(keyword)
    tokens = tokenize_text(normalized_keyword)
    locality = _extract_locality(tokens)
    intent = _detect_keyword_intent(normalized_keyword)
    entity_focus = _extract_entity_focus(tokens, locality)
    detail_focus = _resolve_detail_focus(category, normalized_keyword, intent, entity_focus)

    keyword_key = normalize_key(normalized_keyword)
    is_service = any(term in normalized_keyword or normalize_key(term) in keyword_key for term in _SERVICE_TERMS)
    is_profile = any(term in normalized_keyword or normalize_key(term) in keyword_key for term in _PROFILE_TERMS)
    is_media = any(term in normalized_keyword or normalize_key(term) in keyword_key for term in _MEDIA_TERMS)
    is_policy = any(term in normalized_keyword or normalize_key(term) in keyword_key for term in _POLICY_TERMS)

    return TemplateContext(
        keyword=normalized_keyword,
        category=category,
        intent=intent,
        locality=locality,
        entity_focus=entity_focus,
        detail_focus=detail_focus,
        is_local=bool(locality),
        is_service=is_service,
        is_profile=is_profile,
        is_media=is_media,
        is_policy=is_policy,
    )


def _build_naver_home_groups(context: TemplateContext) -> list[list[str]]:
    triggers = build_trigger_bundle(context.keyword)
    groups: list[list[str]] = []

    if context.intent == "review" or context.is_media:
        groups.append([
            f"{context.keyword} 직접 보기 전 체크할 점",
            f"{context.keyword} 평판에서 갈리는 부분",
        ])
    if context.intent == "action":
        groups.append([
            f"{context.keyword} 진행 전 확인할 조건",
            f"{context.keyword} 준비 전에 볼 핵심",
        ])
    if context.intent == "price":
        groups.append([
            f"{context.keyword} 비용 보기 전 기준",
            f"{context.keyword} 가격대 읽는 포인트",
        ])
    if context.intent == "comparison":
        groups.append([
            f"{context.keyword} 비교할 때 보는 기준",
            f"{context.keyword} 무엇이 다른지 먼저 보기",
        ])
    if context.intent == "definition" or context.is_profile:
        groups.append([
            f"{context.keyword} 핵심 정보 빠르게 보기",
            f"{context.keyword} 먼저 볼 이력 포인트",
        ])
    if context.intent == "location" or context.is_local:
        groups.append([
            f"{context.keyword} 위치와 방문 포인트",
            f"{context.keyword} 동선 먼저 보는 포인트",
        ])
    if context.is_service:
        groups.append([
            f"{context.keyword} 관리 전 확인할 부분",
            f"{context.keyword} 고를 때 보는 포인트",
        ])
    if context.is_policy:
        groups.append([
            f"{context.keyword} 오늘 확인할 기준",
            f"{context.keyword} 적용 포인트 한눈에",
        ])

    priority_count = len(groups)
    groups.extend([
        [
            f"{context.keyword} {context.detail_focus} 먼저 보기",
            f"{context.keyword} {context.detail_focus} 한눈에",
        ],
        [
            f"{context.keyword} 찾는 사람이 보는 핵심",
            f"{triggers.time} {context.keyword} 핵심 흐름",
        ],
        [
            f"{context.keyword} 헷갈리기 쉬운 부분",
            f"{context.keyword} 바로 확인할 포인트 {triggers.numeric}",
        ],
    ])

    return _order_groups_for_keyword(context.keyword, groups, locked_prefix_count=priority_count)


def _build_blog_groups(context: TemplateContext) -> list[list[str]]:
    triggers = build_trigger_bundle(context.keyword)
    groups: list[list[str]] = []
    review_lead = f"{context.keyword} 보는 포인트" if _contains_any_term(context.keyword, ("후기", "리뷰")) else f"{context.keyword} 후기에서 보는 포인트"

    if context.intent == "review" or context.is_media:
        groups.append([
            review_lead,
            f"{context.keyword} 직접 보기 전 알 점",
        ])
    if context.intent == "action":
        groups.append([
            f"{context.keyword} 진행 전 준비사항",
            f"{context.keyword} 절차 전에 챙길 점",
        ])
    if context.intent == "price":
        groups.append([
            f"{context.keyword} 가격대와 추가 비용",
            f"{context.keyword} 비용 구간 정리",
        ])
    if context.intent == "comparison":
        groups.append([
            f"{context.keyword} 핵심 차이 정리",
            f"{context.keyword} 고르는 기준 보기",
        ])
    if context.intent == "definition" or context.is_profile:
        groups.append([
            f"{context.keyword} 핵심 이력 가이드",
            f"{context.keyword} 자주 찾는 정보 모음",
        ])
    if context.intent == "location" or context.is_local:
        groups.append([
            f"{context.keyword} 위치와 방문 포인트",
            f"{context.keyword} 동선과 확인 포인트",
        ])
    if context.is_service:
        groups.append([
            f"{context.keyword} 선택 전에 볼 포인트",
            f"{context.keyword} 방문 전에 알아둘 점",
        ])
    if context.is_policy:
        groups.append([
            f"{context.keyword} 빠르게 확인하는 법",
            f"{context.keyword} 자주 묻는 내용 정리",
        ])

    priority_count = len(groups)
    groups.extend([
        [
            f"{context.keyword} 핵심 기준 정리",
            f"{context.keyword} 먼저 볼 포인트",
        ],
        [
            f"{context.keyword} 실수 줄이는 포인트",
            f"{context.keyword} 알아둘 점 {triggers.numeric}",
        ],
        [
            f"{context.keyword} {context.detail_focus} 정리",
            f"{context.keyword} {context.detail_focus} 포인트",
        ],
        [
            f"{context.keyword} 처음 찾는 사람용 안내",
            f"{context.keyword} 빠르게 이해하는 핵심",
        ],
    ])

    return _order_groups_for_keyword(context.keyword, groups, locked_prefix_count=priority_count)


def _select_group_titles(
    keyword: str,
    groups: list[list[str]],
    *,
    limit: int,
    max_length: int | None = None,
) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    used_noisy_families: set[str] = set()
    seed = _stable_seed(keyword)

    for group_index, group in enumerate(groups):
        if not group:
            continue
        start_index = (seed + group_index) % len(group)
        deferred_choice: tuple[str, str] | None = None
        for offset in range(len(group)):
            candidate = group[(start_index + offset) % len(group)]
            normalized_title = _normalize_candidate(candidate, max_length=max_length)
            title_key = normalize_key(normalized_title)
            if not normalized_title or not title_key or title_key in seen:
                continue
            noisy_family = _detect_noisy_frame_family(keyword, normalized_title)
            if noisy_family and noisy_family in used_noisy_families:
                if deferred_choice is None:
                    deferred_choice = (normalized_title, title_key)
                continue
            seen.add(title_key)
            selected.append(normalized_title)
            if noisy_family:
                used_noisy_families.add(noisy_family)
            break
        else:
            if deferred_choice is not None:
                deferred_title, deferred_key = deferred_choice
                seen.add(deferred_key)
                selected.append(deferred_title)
                noisy_family = _detect_noisy_frame_family(keyword, deferred_title)
                if noisy_family:
                    used_noisy_families.add(noisy_family)
        if len(selected) >= limit:
            return selected

    return selected


def _detect_noisy_frame_family(keyword: str, title: str) -> str:
    remainder = normalize_text(title)
    normalized_keyword = normalize_text(keyword)
    if normalized_keyword and remainder.startswith(normalized_keyword):
        remainder = remainder[len(normalized_keyword):].strip()
    if not remainder:
        return ""

    if "체크리스트" in remainder or "체크포인트" in remainder or "체크" in remainder or "확인" in remainder:
        return "check"
    if "가이드" in remainder:
        return "guide"
    if "비교" in remainder:
        return "compare"
    return ""


def _normalize_candidate(candidate: str, *, max_length: int | None = None) -> str:
    title = normalize_text(candidate).replace(":", "")
    if not title:
        return ""
    if max_length is not None and len(title) > max_length:
        title = title[:max_length].rstrip()
    return title


def _extract_locality(tokens: list[str]) -> str:
    for token in tokens:
        if token in _KNOWN_LOCALITY_TOKENS or _LOCALITY_SUFFIX_RE.search(token):
            return token
    return ""


def _extract_entity_focus(tokens: list[str], locality: str) -> str:
    filtered_tokens = [token for token in tokens if token and token != locality]
    if not filtered_tokens:
        return ""
    return filtered_tokens[0]


def _detect_keyword_intent(keyword: str) -> str:
    intent_patterns = (
        ("price", _PRICE_TERMS),
        ("review", _MEDIA_TERMS),
        ("comparison", _COMPARISON_TERMS),
        ("action", _ACTION_TERMS),
        ("location", _LOCATION_TERMS),
        ("definition", _QUESTION_TERMS + _PROFILE_TERMS),
    )
    keyword_key = normalize_key(keyword)
    for intent, patterns in intent_patterns:
        if any(pattern in keyword or normalize_key(pattern) in keyword_key for pattern in patterns):
            return intent
    return "general"


def _contains_any_term(keyword: str, patterns: tuple[str, ...]) -> bool:
    keyword_key = normalize_key(keyword)
    return any(pattern in keyword or normalize_key(pattern) in keyword_key for pattern in patterns)


def _resolve_detail_focus(
    category: CategoryType,
    keyword: str,
    intent: str,
    entity_focus: str,
) -> str:
    if intent == "review":
        return "후기와 선택 기준"
    if intent == "action":
        return "준비 사항"
    if intent == "price":
        return "가격과 조건"
    if intent == "comparison":
        return "비교 기준"
    if intent == "definition":
        return "핵심 정보"

    phrases = {
        "product": "가격과 성능",
        "travel": "동선과 일정",
        "finance": "조건과 보장",
        "health": "주의와 선택 기준",
        "real_estate": "입지와 조건",
        "food": "메뉴와 방문 포인트",
        "general": "핵심 포인트",
    }
    if entity_focus and entity_focus not in keyword:
        return f"{entity_focus} 핵심 정보"
    return phrases.get(category, phrases["general"])


def _stable_seed(keyword: str) -> int:
    return sum(ord(char) for char in normalize_text(keyword))


def _order_groups_for_keyword(
    keyword: str,
    groups: list[list[str]],
    *,
    locked_prefix_count: int = 0,
) -> list[list[str]]:
    if not groups:
        return groups
    seed = _stable_seed(keyword)
    safe_prefix_count = max(0, min(locked_prefix_count, len(groups)))
    prefix_groups = groups[:safe_prefix_count]
    indexed_groups = list(enumerate(groups[safe_prefix_count:], start=safe_prefix_count))
    indexed_groups.sort(key=lambda item: ((seed + item[0] * 7) % 17, item[0]))
    return prefix_groups + [group for _, group in indexed_groups]
