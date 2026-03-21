from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.analyzer.config import DEFAULT_CONFIG
from app.analyzer.main import analyzer_module
from app.analyzer.scorer import (
    classify_attackability_grade,
    classify_golden_bucket,
    classify_profitability_grade,
)
from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.selector.cannibalization import build_cannibalization_report


_OPTIONAL_SUFFIX_LIBRARY: dict[str, dict[str, str]] = {
    "guide": {
        "label": "가이드",
        "suffix": "가이드",
    },
    "checklist": {
        "label": "체크리스트",
        "suffix": "체크리스트",
    },
}
_INTENT_TERMS: dict[str, tuple[str, ...]] = {
    "commercial": ("추천", "비교", "가격", "비용", "요금", "견적", "순위"),
    "review": ("후기", "리뷰", "평판", "영상", "인스타", "사진"),
    "action": ("예약", "가입", "신청", "등록", "발급", "조회"),
    "info": ("뜻", "의미", "정리", "개념", "가이드", "방법", "사용법", "프로필"),
    "location": ("위치", "코스", "루트", "주차", "근처", "동선"),
    "policy": ("대상", "조건", "기준", "제도", "요일", "적용", "제한"),
}
_ALL_INTENT_TERMS = {
    normalize_key(term): intent_key
    for intent_key, terms in _INTENT_TERMS.items()
    for term in terms
    if normalize_key(term)
}
_STOPWORDS = {"추천", "비교", "정리", "가이드", "방법", "사용법", "뜻", "의미"}
_PROFITABILITY_ORDER = ["A", "B", "C", "D"]
_ATTACKABILITY_ORDER = ["1", "2", "3", "4"]


def build_longtail_map(
    selected_items: list[dict[str, Any]],
    keyword_clusters: list[dict[str, Any]] | None = None,
    longtail_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_items = [item for item in selected_items if isinstance(item, dict) and normalize_text(item.get("keyword"))]
    clusters = [cluster for cluster in keyword_clusters or [] if isinstance(cluster, dict)]
    resolved_options = resolve_longtail_options(longtail_options)
    if not selected_items:
        return {
            "longtail_suggestions": [],
            "longtail_summary": _build_longtail_summary([]),
            "longtail_options": resolved_options,
        }

    if not clusters:
        clusters = _build_fallback_clusters(selected_items)

    selected_by_keyword = {
        normalize_text(item.get("keyword")): item
        for item in selected_items
        if normalize_text(item.get("keyword"))
    }
    suggestions: list[dict[str, Any]] = []
    seen_keywords: set[str] = set()

    for cluster in clusters:
        cluster_suggestions = _build_cluster_longtail_suggestions(
            cluster,
            selected_by_keyword,
            resolved_options,
        )
        for suggestion in cluster_suggestions:
            longtail_keyword = normalize_text(suggestion.get("longtail_keyword"))
            keyword_key = normalize_key(longtail_keyword)
            if not longtail_keyword or not keyword_key or keyword_key in seen_keywords:
                continue
            seen_keywords.add(keyword_key)
            suggestions.append(suggestion)

    for index, suggestion in enumerate(suggestions, start=1):
        suggestion["suggestion_id"] = f"longtail-{index:02d}"

    return {
        "longtail_suggestions": suggestions,
        "longtail_summary": _build_longtail_summary(suggestions),
        "longtail_options": resolved_options,
    }


def verify_longtail_candidates(input_data: dict[str, Any]) -> dict[str, Any]:
    selected_items = _coerce_items(input_data.get("selected_keywords"))
    keyword_clusters = _coerce_items(input_data.get("keyword_clusters"))
    resolved_options = resolve_longtail_options(input_data.get("longtail_options"))
    payload = build_longtail_map(
        selected_items,
        keyword_clusters,
        longtail_options=resolved_options,
    )
    should_rebuild = bool(input_data.get("force_rebuild"))
    suggestions = (
        payload["longtail_suggestions"]
        if should_rebuild
        else (_coerce_items(input_data.get("longtail_suggestions")) or payload["longtail_suggestions"])
    )
    if not suggestions:
        return {
            "verified_longtail_suggestions": [],
            "longtail_verification_summary": _build_longtail_summary([]),
            "verified_longtail_keywords": [],
            "longtail_options": payload.get("longtail_options", resolved_options),
        }

    analyzer_options = input_data.get("analyzer_options")
    analyzer_input = {
        "expanded_keywords": [
            {
                "keyword": suggestion["longtail_keyword"],
                "origin": suggestion.get("source_keyword") or suggestion.get("representative_keyword") or suggestion["longtail_keyword"],
                "type": "longtail_suggestion",
            }
            for suggestion in suggestions
            if normalize_text(suggestion.get("longtail_keyword"))
        ],
    }
    if isinstance(analyzer_options, dict):
        analyzer_input.update(analyzer_options)

    analyzed_result = analyzer_module.run(analyzer_input)
    analyzed_items = _coerce_items(analyzed_result.get("analyzed_keywords")) if isinstance(analyzed_result, dict) else []
    analyzed_by_keyword = {
        normalize_text(item.get("keyword")): item
        for item in analyzed_items
        if normalize_text(item.get("keyword"))
    }

    verified_suggestions = [
        _merge_verified_longtail_suggestion(suggestion, analyzed_by_keyword.get(normalize_text(suggestion.get("longtail_keyword"))))
        for suggestion in suggestions
    ]
    cannibalization_report = build_cannibalization_report(
        selected_items,
        keyword_clusters,
        verified_suggestions,
    )

    return {
        "verified_longtail_suggestions": verified_suggestions,
        "longtail_verification_summary": _build_longtail_summary(verified_suggestions),
        "verified_longtail_keywords": analyzed_items,
        "cannibalization_report": cannibalization_report,
        "longtail_options": payload.get("longtail_options", resolved_options),
    }


def _build_cluster_longtail_suggestions(
    cluster: dict[str, Any],
    selected_by_keyword: dict[str, dict[str, Any]],
    longtail_options: dict[str, Any],
) -> list[dict[str, Any]]:
    representative_keyword = normalize_text(cluster.get("representative_keyword"))
    all_keywords = [
        normalize_text(keyword)
        for keyword in cluster.get("all_keywords", [])
        if normalize_text(keyword)
    ]
    if not representative_keyword:
        return []

    base_phrase = _derive_base_phrase(cluster, representative_keyword)
    representative_item = selected_by_keyword.get(representative_keyword) or next(
        (selected_by_keyword.get(keyword) for keyword in all_keywords if selected_by_keyword.get(keyword)),
        {},
    )

    candidate_rows: list[dict[str, Any]] = []
    existing_keyword_keys = {normalize_key(keyword) for keyword in all_keywords if normalize_key(keyword)}

    for keyword in all_keywords:
        modifier_phrase = _extract_modifier_phrase(base_phrase, keyword)
        intent_key = _resolve_intent_key(keyword)
        for candidate in _build_longtail_candidates(
            base_phrase,
            modifier_phrase,
            intent_key,
            representative_keyword,
            optional_suffix_keys=longtail_options.get("optional_suffix_keys", []),
        ):
            normalized_candidate = normalize_text(candidate)
            candidate_key = normalize_key(normalized_candidate)
            if not normalized_candidate or not candidate_key or candidate_key in existing_keyword_keys:
                continue
            candidate_rows.append(
                _build_longtail_suggestion(
                    cluster=cluster,
                    representative_keyword=representative_keyword,
                    representative_item=representative_item,
                    source_keyword=keyword,
                    modifier_phrase=modifier_phrase,
                    intent_key=intent_key,
                    longtail_keyword=normalized_candidate,
                )
            )

    unique_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(candidate_rows, key=_longtail_sort_key, reverse=True):
        keyword_key = normalize_key(row.get("longtail_keyword"))
        if not keyword_key or keyword_key in seen:
            continue
        seen.add(keyword_key)
        unique_rows.append(row)
        if len(unique_rows) >= 3:
            break
    return unique_rows


def _build_longtail_suggestion(
    *,
    cluster: dict[str, Any],
    representative_keyword: str,
    representative_item: dict[str, Any],
    source_keyword: str,
    modifier_phrase: str,
    intent_key: str,
    longtail_keyword: str,
) -> dict[str, Any]:
    base_profitability = _resolve_profitability_grade(representative_item)
    base_attackability = _resolve_attackability_grade(representative_item)
    projected_profitability = _project_profitability_grade(base_profitability, intent_key=intent_key)
    projected_attackability = _project_attackability_grade(base_attackability, longtail_keyword, representative_keyword)
    projected_combo = f"{projected_profitability}{projected_attackability}" if projected_profitability and projected_attackability else ""
    projected_bucket = (
        classify_golden_bucket(projected_profitability, projected_attackability)
        if projected_profitability and projected_attackability
        else ""
    )
    projected_score = _project_longtail_score(
        representative_item,
        projected_profitability=projected_profitability,
        projected_attackability=projected_attackability,
        longtail_keyword=longtail_keyword,
        representative_keyword=representative_keyword,
    )

    return {
        "suggestion_id": "",
        "cluster_id": normalize_text(cluster.get("cluster_id")) or "",
        "representative_keyword": representative_keyword,
        "source_keyword": source_keyword,
        "base_phrase": _derive_base_phrase(cluster, representative_keyword),
        "modifier_phrase": modifier_phrase,
        "intent_key": intent_key,
        "intent_label": _format_intent_label(intent_key),
        "longtail_keyword": longtail_keyword,
        "combination_terms": [term for term in [representative_keyword, source_keyword, modifier_phrase] if normalize_text(term)],
        "projected_profitability_grade": projected_profitability,
        "projected_attackability_grade": projected_attackability,
        "projected_combo_grade": projected_combo,
        "projected_golden_bucket": projected_bucket,
        "projected_score": projected_score,
        "verification_status": "pending",
        "verification_label": "검증 대기",
        "verification_reason": "분석 전 단계의 예상치입니다.",
    }


def _build_longtail_candidates(
    base_phrase: str,
    modifier_phrase: str,
    intent_key: str,
    representative_keyword: str,
    *,
    optional_suffix_keys: list[str] | tuple[str, ...] = (),
) -> list[str]:
    base_phrase = normalize_text(base_phrase)
    modifier_phrase = normalize_text(modifier_phrase)
    if not base_phrase:
        return []

    if modifier_phrase:
        modifier_key = normalize_key(modifier_phrase)
        normalized_modifier = modifier_phrase
    else:
        modifier_key = ""
        normalized_modifier = ""

    candidates: list[str] = []

    if intent_key == "review":
        candidates.extend([
            f"{base_phrase} {normalized_modifier or '후기'} 체크포인트",
            f"{base_phrase} {normalized_modifier or '리뷰'} 보기 전 체크",
        ])
    elif intent_key == "action":
        candidates.extend([
            f"{base_phrase} {normalized_modifier or '예약'} 방법",
            f"{base_phrase} {normalized_modifier or '예약'} 전 체크포인트",
        ])
    elif intent_key == "commercial":
        candidates.extend([
            f"{base_phrase} {normalized_modifier or '추천'} 기준",
            f"{base_phrase} {normalized_modifier or '비교'} 포인트",
        ])
    elif intent_key == "info":
        candidates.extend([
            f"{base_phrase} {normalized_modifier or '정보'} 핵심 정리",
            f"{base_phrase} {normalized_modifier} 확인 포인트" if normalized_modifier else f"{base_phrase} 최신 정보",
        ])
    elif intent_key == "location":
        candidates.extend([
            f"{base_phrase} {normalized_modifier or '위치'} 포인트",
            f"{base_phrase} {normalized_modifier or '동선'} 체크",
        ])
    elif intent_key == "policy":
        candidates.extend([
            f"{base_phrase} {normalized_modifier or '적용'} 기준",
            f"{base_phrase} {normalized_modifier or '대상'} 확인 포인트",
        ])

    candidates.extend(_build_optional_suffix_candidates(base_phrase, normalized_modifier, optional_suffix_keys))

    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = normalize_text(candidate)
        if not cleaned:
            continue
        cleaned = cleaned.replace("  ", " ")
        if modifier_key and normalized_modifier in {"추천", "비교", "정보"} and cleaned == representative_keyword:
            continue
        if _is_awkward_longtail(cleaned):
            continue
        candidate_key = normalize_key(cleaned)
        if not candidate_key or candidate_key in seen:
            continue
        seen.add(candidate_key)
        normalized_candidates.append(cleaned)
    return normalized_candidates


def _build_optional_suffix_candidates(
    base_phrase: str,
    normalized_modifier: str,
    optional_suffix_keys: list[str] | tuple[str, ...],
) -> list[str]:
    base_phrase = normalize_text(base_phrase)
    normalized_modifier = normalize_text(normalized_modifier)
    if not base_phrase:
        return []

    candidates: list[str] = []
    modifier_key = normalize_key(normalized_modifier)
    for raw_key in optional_suffix_keys:
        option = _OPTIONAL_SUFFIX_LIBRARY.get(str(raw_key or "").strip().lower())
        if not option:
            continue
        suffix = option["suffix"]
        suffix_key = normalize_key(suffix)
        if normalized_modifier and modifier_key and modifier_key == suffix_key:
            candidates.append(f"{base_phrase} {suffix}")
            continue
        if normalized_modifier:
            candidates.append(f"{base_phrase} {normalized_modifier} {suffix}")
            continue
        candidates.append(f"{base_phrase} {suffix}")
    return candidates


def _is_awkward_longtail(keyword: str) -> bool:
    tokens = tokenize_text(keyword)
    if len(tokens) < 2 or len(tokens) > 6:
        return True
    seen_counts: dict[str, int] = defaultdict(int)
    for token in tokens:
        token_key = normalize_key(token)
        if not token_key:
            continue
        seen_counts[token_key] += 1
        if seen_counts[token_key] > 1:
            return True
    return False


def _derive_base_phrase(cluster: dict[str, Any], representative_keyword: str) -> str:
    topic_terms = [
        normalize_text(term)
        for term in cluster.get("topic_terms", [])
        if normalize_text(term)
    ]
    if topic_terms:
        return " ".join(topic_terms)

    tokens = tokenize_text(representative_keyword)
    filtered_tokens = [token for token in tokens if normalize_key(token) not in _ALL_INTENT_TERMS]
    return " ".join(filtered_tokens[:4]) if filtered_tokens else representative_keyword


def _extract_modifier_phrase(base_phrase: str, keyword: str) -> str:
    base_tokens = tokenize_text(base_phrase)
    keyword_tokens = tokenize_text(keyword)
    if not base_tokens:
        return ""

    remaining_tokens = keyword_tokens[:]
    for token in base_tokens:
        if remaining_tokens and normalize_key(remaining_tokens[0]) == normalize_key(token):
            remaining_tokens.pop(0)
            continue
        break

    modifier_tokens = [token for token in remaining_tokens if normalize_key(token) not in _STOPWORDS]
    if modifier_tokens:
        return " ".join(modifier_tokens)
    return " ".join(remaining_tokens)


def _resolve_intent_key(keyword: str) -> str:
    keyword_key = normalize_key(keyword)
    for term_key, intent_key in _ALL_INTENT_TERMS.items():
        if term_key and term_key in keyword_key:
            return intent_key
    return "general"


def _project_profitability_grade(base_grade: str, *, intent_key: str) -> str:
    if base_grade not in _PROFITABILITY_ORDER:
        return "C"
    index = _PROFITABILITY_ORDER.index(base_grade)
    if intent_key in {"commercial", "action"}:
        return base_grade
    if intent_key in {"review", "info", "location", "policy"}:
        return _PROFITABILITY_ORDER[min(index + 1, len(_PROFITABILITY_ORDER) - 1)]
    return _PROFITABILITY_ORDER[min(index + 1, len(_PROFITABILITY_ORDER) - 1)]


def _project_attackability_grade(base_grade: str, longtail_keyword: str, representative_keyword: str) -> str:
    if base_grade not in _ATTACKABILITY_ORDER:
        return "2"
    index = _ATTACKABILITY_ORDER.index(base_grade)
    token_bonus = 1 if len(tokenize_text(longtail_keyword)) > len(tokenize_text(representative_keyword)) else 0
    improved_index = max(0, index - token_bonus)
    return _ATTACKABILITY_ORDER[improved_index]


def _project_longtail_score(
    representative_item: dict[str, Any],
    *,
    projected_profitability: str,
    projected_attackability: str,
    longtail_keyword: str,
    representative_keyword: str,
) -> float:
    base_score = float(representative_item.get("score", 0.0) or 0.0)
    profitability_bonus = {"A": 7.0, "B": 4.0, "C": 1.0, "D": -3.0}.get(projected_profitability, 0.0)
    attackability_bonus = {"1": 8.0, "2": 4.0, "3": 0.0, "4": -4.0}.get(projected_attackability, 0.0)
    specificity_bonus = 2.0 if len(tokenize_text(longtail_keyword)) > len(tokenize_text(representative_keyword)) else 0.0
    return round(max(0.0, min(100.0, base_score * 0.78 + profitability_bonus + attackability_bonus + specificity_bonus)), 1)


def _merge_verified_longtail_suggestion(
    suggestion: dict[str, Any],
    analyzed_item: dict[str, Any] | None,
) -> dict[str, Any]:
    if not analyzed_item:
        return {
            **suggestion,
            "verification_status": "error",
            "verification_label": "검증 실패",
            "verification_reason": "분석 결과를 찾지 못했습니다.",
        }

    profitability_grade = _resolve_profitability_grade(analyzed_item)
    attackability_grade = _resolve_attackability_grade(analyzed_item)
    combo_grade = f"{profitability_grade}{attackability_grade}" if profitability_grade and attackability_grade else ""
    golden_bucket = str(analyzed_item.get("golden_bucket") or "").strip().lower() or (
        classify_golden_bucket(profitability_grade, attackability_grade)
        if profitability_grade and attackability_grade
        else ""
    )
    score = float(analyzed_item.get("score", 0.0) or 0.0)

    if golden_bucket in {"gold", "promising"}:
        verification_status = "pass"
        verification_label = "검증 통과"
        verification_reason = "실측/분석 기준에서 바로 써볼 수 있는 롱테일입니다."
    elif score >= 45.0:
        verification_status = "review"
        verification_label = "추가 검토"
        verification_reason = "노출 가능성은 있으나 우선순위는 한 단계 낮습니다."
    else:
        verification_status = "fail"
        verification_label = "보류"
        verification_reason = "검색량·수익성·공략성 기준에서 우선순위가 낮습니다."

    return {
        **suggestion,
        "verification_status": verification_status,
        "verification_label": verification_label,
        "verification_reason": verification_reason,
        "verified_keyword": normalize_text(analyzed_item.get("keyword")),
        "verified_score": round(score, 1),
        "verified_profitability_grade": profitability_grade,
        "verified_attackability_grade": attackability_grade,
        "verified_combo_grade": combo_grade,
        "verified_golden_bucket": golden_bucket,
        "verified_metrics": analyzed_item.get("metrics", {}),
        "verified_analysis_mode": analyzed_item.get("analysis_mode", ""),
    }


def _build_longtail_summary(suggestions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "suggestion_count": len(suggestions),
        "cluster_count": len({normalize_text(item.get("cluster_id")) for item in suggestions if normalize_text(item.get("cluster_id"))}),
        "pending_count": sum(1 for item in suggestions if item.get("verification_status") == "pending"),
        "verified_count": sum(1 for item in suggestions if item.get("verification_status") in {"pass", "review", "fail"}),
        "pass_count": sum(1 for item in suggestions if item.get("verification_status") == "pass"),
        "review_count": sum(1 for item in suggestions if item.get("verification_status") == "review"),
        "fail_count": sum(1 for item in suggestions if item.get("verification_status") == "fail"),
        "error_count": sum(1 for item in suggestions if item.get("verification_status") == "error"),
    }


def _build_fallback_clusters(selected_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "cluster_id": f"cluster-{index:02d}",
            "representative_keyword": normalize_text(item.get("keyword")),
            "topic_terms": tokenize_text(item.get("keyword"))[:3],
            "all_keywords": [normalize_text(item.get("keyword"))],
        }
        for index, item in enumerate(selected_items, start=1)
        if normalize_text(item.get("keyword"))
    ]


def _coerce_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def resolve_longtail_options(value: Any) -> dict[str, Any]:
    raw_keys: list[Any]
    if isinstance(value, dict):
        raw_keys = value.get("optional_suffix_keys") or value.get("optional_suffixes") or []
    elif isinstance(value, list):
        raw_keys = value
    else:
        raw_keys = []

    normalized_keys: list[str] = []
    seen: set[str] = set()
    for raw_key in raw_keys:
        key = _normalize_optional_suffix_key(raw_key)
        if not key or key in seen:
            continue
        seen.add(key)
        normalized_keys.append(key)

    return {
        "optional_suffix_keys": normalized_keys,
        "optional_suffix_labels": [
            _OPTIONAL_SUFFIX_LIBRARY[key]["label"]
            for key in normalized_keys
            if key in _OPTIONAL_SUFFIX_LIBRARY
        ],
    }


def _normalize_optional_suffix_key(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _OPTIONAL_SUFFIX_LIBRARY:
        return normalized

    token_key = normalize_key(value)
    for option_key, option in _OPTIONAL_SUFFIX_LIBRARY.items():
        if token_key == normalize_key(option["label"]) or token_key == normalize_key(option["suffix"]):
            return option_key
    return ""


def _longtail_sort_key(item: dict[str, Any]) -> tuple[float, float, float]:
    attackability_grade = str(item.get("projected_attackability_grade") or "").strip()
    if attackability_grade in _ATTACKABILITY_ORDER:
        attackability_rank = float(len(_ATTACKABILITY_ORDER) - _ATTACKABILITY_ORDER.index(attackability_grade))
    else:
        attackability_rank = 0.0
    return (
        float(item.get("projected_score") or 0.0),
        attackability_rank,
        float(len(tokenize_text(item.get("longtail_keyword") or ""))),
    )


def _resolve_profitability_grade(item: dict[str, Any]) -> str:
    grade = str(item.get("profitability_grade") or "").strip().upper()
    if grade in _PROFITABILITY_ORDER:
        return grade
    profitability_score = float(item.get("profitability_score", 0.0) or 0.0)
    return classify_profitability_grade(profitability_score, DEFAULT_CONFIG)


def _resolve_attackability_grade(item: dict[str, Any]) -> str:
    grade = str(item.get("attackability_grade") or "").strip()
    if grade in _ATTACKABILITY_ORDER:
        return grade
    attackability_score = float(item.get("attackability_score", 0.0) or 0.0)
    return classify_attackability_grade(attackability_score, DEFAULT_CONFIG)


def _format_intent_label(intent_key: str) -> str:
    label_map = {
        "commercial": "비교/추천형",
        "review": "후기형",
        "action": "행동형",
        "info": "정보형",
        "location": "위치형",
        "policy": "조건형",
        "general": "일반형",
    }
    return label_map.get(intent_key, "일반형")
