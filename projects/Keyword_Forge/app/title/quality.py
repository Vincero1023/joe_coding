from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.title.category_detector import detect_category
from app.title.rules import NAVER_HOME_MAX_LENGTH


TITLE_QUALITY_PASS_SCORE = 84
TITLE_QUALITY_REVIEW_SCORE = 75
_NOISY_PUNCTUATION_RE = re.compile(r"[!?]{2,}|\.{3,}")
_FORBIDDEN_TITLE_PUNCTUATION = (":", "：")
_MODEL_NUMBER_TOKEN_RE = re.compile(r"(?i)^[a-z]{1,6}\d{2,4}[a-z0-9-]*$")
_CLICKSBAIT_TERMS = (
    "무조건",
    "충격",
    "레전드",
    "실화",
    "미쳤다",
    "대박",
    "반전",
    "소름",
    "논란",
    "핵꿀팁",
)
_GENERIC_TEMPLATE_TERMS = (
    "완벽 정리",
    "한 번에 정리",
    "갑자기 바뀌었다",
    "이유가 이상하다",
    "놓치면 손해",
    "비교 및 선택 기준 정리",
)
_LOW_SIGNAL_SKELETON_KEYS = (
    "최신정보",
    "업데이트확인",
    "최신업데이트확인",
    "최신순위",
    "신상",
    "비교",
    "리뷰",
    "사용법",
    "사용후기",
    "구매가이드",
    "추천가이드",
    "상세정보",
    "왜인기",
    "왜이럴까",
    "이것만알면",
    "인기이유",
    "인기모델비교",
    "구매팁",
)
_LOW_SIGNAL_SKELETON_TOKENS = {
    "최신",
    "정보",
    "업데이트",
    "확인",
    "신상",
    "비교",
    "리뷰",
    "후기",
    "사용",
    "사용법",
    "구매",
    "가이드",
    "추천",
    "기준",
    "이유",
    "인기",
    "분석",
    "정리",
    "팁",
    "상세",
}
_HARD_REJECT_TEMPLATE_SKELETON_KEYS = (
    "추천기준",
    "추천기준총정리",
    "고를때체크",
    "비교",
    "최신정보",
    "최신순위",
    "최신동향",
    "최신모델비교",
    "최신성능비교",
    "구매가이드",
    "완벽가이드",
    "완벽분석",
    "총정리",
    "뭐가다를까",
    "뭐가제일좋을까",
    "무엇을봐야할까",
    "무엇을확인",
    "왜인기일까",
    "이것만알면끝",
)
_HARD_REJECT_TEMPLATE_SUBSTRINGS = (
    "추천기준",
    "고를때체크",
    "최신정보",
    "최신순위",
    "최신동향",
    "최신업데이트",
    "업데이트확인",
    "최신모델비교",
    "최신성능비교",
    "구매가이드",
    "완벽가이드",
    "완벽분석",
    "총정리",
    "뭐가다를까",
    "뭐가제일좋을까",
    "무엇을봐야할까",
    "무엇을확인",
    "왜인기일까",
    "이것만알면끝",
)
_HARD_REJECT_TEMPLATE_TOKENS = {
    "최신",
    "정보",
    "동향",
    "업데이트",
    "확인",
    "구매",
    "가이드",
    "추천",
    "기준",
    "고를",
    "때",
    "총정리",
    "완벽",
    "분석",
    "뭐가",
    "다를까",
    "왜",
    "인기",
    "이럴까",
    "무엇",
    "봐야",
    "알면",
    "끝",
    "필수",
    "선택",
    "순위",
    "제일",
    "좋을까",
    "모델",
    "성능",
    "체크포인트",
}
_PRACTICAL_KEYWORD_PATTERNS = (
    "실사용 차이",
    "장단점",
    "설정 팁",
    "자주 생기는 문제",
    "연결 문제",
    "연결 방법",
    "설정 방법",
    "문제",
    "오류",
    "안됨",
    "끊김",
    "더블클릭",
    "휠 튐",
    "인식 안됨",
    "손목 통증",
)
_PRACTICAL_KEYWORD_KEYS = tuple(
    normalize_key(pattern) for pattern in _PRACTICAL_KEYWORD_PATTERNS if normalize_key(pattern)
)
_GENERIC_OVERLAY_PATTERNS = (
    "최신 정보",
    "최신 비교",
    "최신 비교 분석",
    "비교 분석",
    "총정리",
    "총정리 가이드",
    "완벽 가이드",
    "가이드",
    "이것만 알면",
    "꼭 알아두세요",
    "최적화 방법",
    "사용 후기",
    "추천 기준",
)
_GENERIC_OVERLAY_KEYS = tuple(
    normalize_key(pattern) for pattern in _GENERIC_OVERLAY_PATTERNS if normalize_key(pattern)
)
_GENERIC_OVERLAY_TOKENS = {
    normalize_key(token)
    for token in (
        "최신",
        "정보",
        "비교",
        "분석",
        "총정리",
        "완벽",
        "가이드",
        "이것만",
        "알면",
        "꼭",
        "알아두세요",
        "최적화",
        "방법",
        "사용",
        "후기",
        "추천",
        "기준",
    )
    if normalize_key(token)
}
_VAGUE_EDITORIAL_SKELETON_PATTERNS = (
    "숨은보석",
    "찾아봐요",
)
_VAGUE_EDITORIAL_SKELETON_REGEXES = (
    re.compile(r"꼭알아둘\d+가지"),
)
_SINGLE_VAGUE_TEASER_PATTERNS = (
    "놓치면후회",
    "인기급상승",
    "트렌드분석",
    "숨겨진꿀팁",
    "숨겨진혜택",
    "당신의선택은",
    "어떤점이인기일까",
    "주목해야할까",
    "이걸몰랐다고",
    "정말살만할까",
    "이번주시작",
    "경쟁예상",
    "특가예약팁",
    "출시임박",
    "예약전꼭확인",
    "바꿔보세요",
    "알고사자",
)
_UNVERIFIED_FRESHNESS_PATTERNS = (
    "오늘",
    "이번주",
    "이번달",
    "요즘",
    "방금",
    "2주",
    "2주차",
    "3주",
    "최신할인율",
    "최저가",
    "가격변동",
)
_GENERIC_SINGLE_LOW_INFO_TOKENS = {
    normalize_key(token)
    for token in (
        "오늘",
        "이번주",
        "요즘",
        "인기",
        "순위",
        "신상",
        "출시",
        "임박",
        "변화",
        "주목",
        "경쟁",
        "예상",
        "특가",
        "혜택",
        "이유",
        "선택",
        "궁금",
        "핫한",
        "뜨는",
    )
    if normalize_key(token)
}
_PRODUCT_SINGLE_CONCRETE_TOKENS = {
    normalize_key(token)
    for token in (
        "실사용",
        "장단점",
        "가격대",
        "추천",
        "대상",
        "클릭감",
        "배터리",
        "그립",
        "연결",
        "세팅",
        "키감",
        "배열",
        "키맵",
        "멀티페어링",
        "fn",
        "한영",
    )
    if normalize_key(token)
}
_PREORDER_SINGLE_CONCRETE_TOKENS = {
    normalize_key(token)
    for token in ("일정", "오픈", "링크", "혜택", "인증", "결제", "수령", "조건", "제한")
    if normalize_key(token)
}
_VALUE_SINGLE_CONCRETE_TOKENS = {
    normalize_key(token)
    for token in ("위치", "교통", "추가요금", "조식", "객실", "취소", "예산", "거리", "포함", "후기")
    if normalize_key(token)
}
_POLICY_SINGLE_CONCRETE_TOKENS = {
    normalize_key(token)
    for token in ("조건", "대상", "제한", "비용", "준비물", "서류", "신청", "기간", "금리", "우대")
    if normalize_key(token)
}
_PRODUCTISH_KEY_PATTERNS = (
    "마우스",
    "키보드",
    "노트북",
    "맥북",
    "아이패드",
    "아이폰",
    "갤럭시",
    "이어폰",
    "헤드셋",
    "모니터",
    "스피커",
    "웹캠",
    "프린터",
    "공유기",
    "태블릿",
    "닌텐도",
    "스위치",
    "콘솔",
    "카메라",
)
_QUESTION_ENDING_PATTERNS = (
    "좋을까",
    "살만할까",
    "치열할까",
    "시작",
    "일까",
    "할까",
)
_BATCH_SKELETON_REPEAT_THRESHOLD = 2
_TITLE_STATUS_SORT_RANK = {"good": 0, "review": 1, "retry": 2}
_BATCH_NOISY_FAMILY_PATTERNS = (
    ("difference_question", "차이 질문", ("뭐가다를까", "무엇이다를까", "차이가뭘까", "차이점")),
    ("check", "체크", ("체크리스트", "체크포인트", "체크", "확인")),
    ("selection_criteria", "선택 기준", ("추천기준", "선택기준", "고르는기준", "고를때")),
    ("compare", "비교", ("비교", "vs")),
    ("guide", "가이드", ("가이드",)),
)


def enrich_title_results(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reports = [assess_title_bundle(item) for item in items]
    reports = _apply_batch_similarity_feedback(items, reports)

    enriched_items: list[dict[str, Any]] = []
    for item, report in zip(items, reports):
        reordered_titles, reordered_title_checks = _reorder_titles_for_output(item, report)
        enriched_items.append(
            {
                **{
                    key: value
                    for key, value in item.items()
                    if key not in {"titles", "quality_report"}
                },
                "keyword": normalize_text(item.get("keyword")),
                "titles": reordered_titles,
                "quality_report": {
                    **report,
                    "title_checks": reordered_title_checks,
                },
            }
        )

    return enriched_items, summarize_title_quality(reports)


def assess_title_bundle(item: dict[str, Any]) -> dict[str, Any]:
    keyword = normalize_text(item.get("keyword"))
    titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
    naver_home_titles = _normalize_title_list(titles.get("naver_home"))
    blog_titles = _normalize_title_list(titles.get("blog"))
    duplicate_counts = _count_duplicates(naver_home_titles + blog_titles)

    channel_reports: dict[str, list[dict[str, Any]]] = {
        "naver_home": [
            assess_single_title(keyword, title, "naver_home", duplicate_counts, item_context=item)
            for title in naver_home_titles
        ],
        "blog": [
            assess_single_title(keyword, title, "blog", duplicate_counts, item_context=item)
            for title in blog_titles
        ],
    }
    return _build_bundle_report(keyword, channel_reports)


def assess_single_title(
    keyword: str,
    title: str,
    channel: str,
    duplicate_counts: dict[str, int],
    item_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_title = normalize_text(title)
    forbidden_punctuation_used = any(mark in raw_title for mark in _FORBIDDEN_TITLE_PUNCTUATION)
    normalized_title = _normalize_title_surface(raw_title)
    canonical_title = normalize_key(normalized_title)
    issues: list[str] = []
    score = 100
    critical = False

    if not normalized_title:
        return {
            "title": "",
            "score": 0,
            "status": "retry",
            "critical": True,
            "issues": ["제목이 비어 있습니다."],
            "checks": {
                "contains_keyword": False,
                "starts_with_keyword": False,
                "length_ok": False,
                "duplicate_risk": False,
            },
        }

    contains_keyword = _contains_keyword_phrase(keyword, normalized_title)
    starts_with_keyword = _starts_with_keyword_phrase(keyword, normalized_title)
    length_ok = True
    duplicate_risk = bool(canonical_title and duplicate_counts.get(canonical_title, 0) > 1)

    if not contains_keyword:
        issues.append("키워드 핵심 표현이 제목에 충분히 반영되지 않았습니다.")
        score -= 36
        critical = True
    elif not starts_with_keyword:
        issues.append("키워드가 제목 앞부분에 오지 않습니다.")
        score -= 10

    if channel == "naver_home" and len(normalized_title) > NAVER_HOME_MAX_LENGTH:
        issues.append(f"네이버 홈형은 {NAVER_HOME_MAX_LENGTH}자 이하여야 합니다.")
        score -= 20
        critical = True
        length_ok = False
    elif len(normalized_title) < max(10, len(keyword) + 2):
        issues.append("제목 길이가 너무 짧습니다.")
        score -= 8

    if keyword and normalized_title.count(keyword) > 1:
        issues.append("키워드 반복이 많습니다.")
        score -= 6

    if any(term in normalized_title for term in _CLICKSBAIT_TERMS):
        issues.append("과장 표현이 포함돼 있습니다.")
        score -= 12

    if any(term in normalized_title for term in _GENERIC_TEMPLATE_TERMS):
        issues.append("템플릿 표현이 지나치게 고정적입니다.")
        score -= 10

    if forbidden_punctuation_used:
        issues.append("제목에서 콜론 표기는 제거하는 편이 자연스럽습니다.")
        score -= 4

    generic_overlay_on_practical = _has_generic_overlay_on_practical_keyword(keyword, normalized_title)
    generic_single_overlay = _has_generic_single_overlay(
        keyword,
        normalized_title,
        item_context=item_context or {},
    )
    unverified_freshness_claim = _has_unverified_freshness_claim(
        keyword,
        normalized_title,
        item_context=item_context or {},
    )
    hard_reject_skeleton = (
        _is_hard_reject_title_skeleton(keyword, normalized_title)
        or generic_overlay_on_practical
        or generic_single_overlay
        or unverified_freshness_claim
    )
    if generic_overlay_on_practical:
        issues.append("구체 글감 위에 다시 템플릿형 포장을 덧씌웠습니다.")
        score -= 18
        critical = True
    elif generic_single_overlay:
        issues.append("단일 키워드 제목이 의도 대비 너무 추상적이거나 낚시형입니다.")
        score -= 18
        critical = True
    elif unverified_freshness_claim:
        issues.append("근거 없는 최신성·기간·가격 변화 표현이 포함돼 있습니다.")
        score -= 16
        critical = True
    elif hard_reject_skeleton:
        issues.append("제목 골격이 템플릿형 표현에 머물러 있습니다.")
        score -= 18
        critical = True
    elif _is_low_signal_title_skeleton(keyword, normalized_title):
        issues.append("제목 골격이 너무 일반적입니다.")
        score -= 12

    if _NOISY_PUNCTUATION_RE.search(normalized_title):
        issues.append("구두점 사용이 과합니다.")
        score -= 6

    if duplicate_risk:
        issues.append("다른 제목과 거의 같습니다.")
        score -= 20

    score = max(0, min(100, score))
    return {
        "title": normalized_title,
        "score": score,
        "status": _resolve_title_status(score, critical),
        "critical": critical,
        "issues": _unique_preserve_order(issues),
        "checks": {
            "contains_keyword": contains_keyword,
            "starts_with_keyword": starts_with_keyword,
            "length_ok": length_ok,
            "duplicate_risk": duplicate_risk,
            "hard_reject_skeleton": hard_reject_skeleton,
            "generic_overlay_on_practical_keyword": generic_overlay_on_practical,
            "generic_single_overlay": generic_single_overlay,
            "unverified_freshness_claim": unverified_freshness_claim,
            "forbidden_punctuation_used": forbidden_punctuation_used,
        },
    }


def summarize_title_quality(reports: list[dict[str, Any]]) -> dict[str, Any]:
    total_count = len(reports)
    if not total_count:
        return {
            "total_count": 0,
            "good_count": 0,
            "review_count": 0,
            "retry_count": 0,
            "average_score": 0,
        }

    return {
        "total_count": total_count,
        "good_count": sum(1 for report in reports if report.get("status") == "good"),
        "review_count": sum(1 for report in reports if report.get("status") == "review"),
        "retry_count": sum(1 for report in reports if report.get("status") == "retry"),
        "average_score": round(
            sum(int(report.get("bundle_score") or 0) for report in reports) / total_count,
            1,
        ),
    }


def _normalize_title_list(raw_titles: Any) -> list[str]:
    if not isinstance(raw_titles, list):
        return []
    return [_normalize_title_surface(title) for title in raw_titles if _normalize_title_surface(title)]


def _normalize_title_surface(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    for mark in _FORBIDDEN_TITLE_PUNCTUATION:
        text = text.replace(mark, " ")
    return normalize_text(text)


def _build_bundle_report(
    keyword: str,
    channel_reports: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    all_reports = channel_reports.get("naver_home", []) + channel_reports.get("blog", [])
    all_titles = [report["title"] for report in all_reports if normalize_text(report.get("title"))]
    bundle_issues: list[str] = []
    channel_scores: dict[str, int] = {}
    critical_issue = False

    for channel_name, title_reports in channel_reports.items():
        base_score = round(sum(report["score"] for report in title_reports) / len(title_reports)) if title_reports else 0
        variation_penalty, variation_issue = _assess_channel_variation(keyword, channel_name, title_reports)
        channel_scores[channel_name] = max(0, base_score - variation_penalty)
        if variation_issue:
            bundle_issues.append(variation_issue)
        if any(report["critical"] for report in title_reports):
            critical_issue = True

    for report in all_reports:
        bundle_issues.extend(report["issues"])

    unique_issues = _unique_preserve_order(bundle_issues)
    bundle_score = round(sum(channel_scores.values()) / len(channel_scores)) if channel_scores else 0
    channel_good_counts = {
        channel_name: sum(1 for report in title_reports if report.get("status") == "good")
        for channel_name, title_reports in channel_reports.items()
    }
    channel_usable_counts = {
        channel_name: sum(1 for report in title_reports if report.get("status") != "retry")
        for channel_name, title_reports in channel_reports.items()
    }
    required_channels = ("naver_home", "blog")
    recommended_pair_ready = all(channel_good_counts.get(channel_name, 0) > 0 for channel_name in required_channels)
    usable_pair_ready = all(channel_usable_counts.get(channel_name, 0) > 0 for channel_name in required_channels)

    if not keyword or not all_titles:
        return {
            "bundle_score": 0,
            "status": "retry",
            "label": "재생성 권장",
            "passes_threshold": False,
            "retry_recommended": True,
            "issue_count": 1,
            "issues": ["제목 결과가 비어 있습니다."],
            "summary": "제목 결과가 비어 있어 다시 생성이 필요합니다.",
            "channel_scores": channel_scores,
            "title_checks": channel_reports,
            "channel_good_counts": channel_good_counts,
            "channel_usable_counts": channel_usable_counts,
            "recommended_pair_ready": False,
            "usable_pair_ready": False,
        }

    passes_threshold = (
        bundle_score >= TITLE_QUALITY_PASS_SCORE
        and all(score >= TITLE_QUALITY_REVIEW_SCORE for score in channel_scores.values())
        and not critical_issue
    )
    status = _resolve_bundle_status(
        bundle_score,
        critical_issue,
        passes_threshold,
        recommended_pair_ready=recommended_pair_ready,
    )
    summary = (
        "키워드 노출과 제목 변주 폭이 안정적입니다."
        if not unique_issues
        else " / ".join(unique_issues[:3])
    )

    return {
        "bundle_score": bundle_score,
        "status": status,
        "label": _label_for_status(status),
        "passes_threshold": passes_threshold,
        "retry_recommended": status == "retry",
        "issue_count": len(unique_issues),
        "issues": unique_issues,
        "summary": summary,
        "channel_scores": channel_scores,
        "title_checks": channel_reports,
        "channel_good_counts": channel_good_counts,
        "channel_usable_counts": channel_usable_counts,
        "recommended_pair_ready": recommended_pair_ready,
        "usable_pair_ready": usable_pair_ready,
    }


def _contains_keyword_phrase(keyword: str, title: str) -> bool:
    normalized_keyword = normalize_text(keyword)
    normalized_title = normalize_text(title)
    if not normalized_keyword or not normalized_title:
        return False
    if normalized_keyword in normalized_title:
        return True

    keyword_tokens = _normalize_tokens(keyword)
    title_tokens = _normalize_tokens(title)
    if not keyword_tokens or not title_tokens:
        return False
    return _contains_tokens_in_order(keyword_tokens, title_tokens)


def _starts_with_keyword_phrase(keyword: str, title: str) -> bool:
    normalized_keyword = normalize_text(keyword)
    normalized_title = normalize_text(title)
    if not normalized_keyword or not normalized_title:
        return False
    if normalized_title.startswith(normalized_keyword):
        return True

    keyword_tokens = _normalize_tokens(keyword)
    title_tokens = _normalize_tokens(title)
    if not keyword_tokens or not title_tokens:
        return False

    prefix_length = 1 if len(keyword_tokens) == 1 else 2
    return (
        title_tokens[:prefix_length] == keyword_tokens[:prefix_length]
        and _contains_tokens_in_order(keyword_tokens, title_tokens)
    )


def _normalize_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for token in tokenize_text(value):
        normalized_token = normalize_key(token)
        if normalized_token:
            tokens.append(normalized_token)
    return tokens


def _contains_tokens_in_order(keyword_tokens: list[str], title_tokens: list[str]) -> bool:
    if not keyword_tokens:
        return False

    search_start = 0
    for keyword_token in keyword_tokens:
        matched = False
        for index in range(search_start, len(title_tokens)):
            if title_tokens[index] != keyword_token:
                continue
            search_start = index + 1
            matched = True
            break
        if not matched:
            return False
    return True


def _count_duplicates(titles: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for title in titles:
        canonical_title = normalize_key(title)
        if not canonical_title:
            continue
        counts[canonical_title] = counts.get(canonical_title, 0) + 1
    return counts


def _assess_channel_variation(
    keyword: str,
    channel_name: str,
    title_reports: list[dict[str, Any]],
) -> tuple[int, str]:
    titles = [report["title"] for report in title_reports if normalize_text(report.get("title"))]
    if len(titles) < 2:
        return 0, ""

    normalized_variants = [_strip_keyword(title, keyword) for title in titles]
    similarity = SequenceMatcher(None, normalized_variants[0], normalized_variants[1]).ratio()
    if similarity < 0.82:
        return 0, ""

    penalty = 12 if similarity >= 0.92 else 8
    label = "네이버 홈형" if channel_name == "naver_home" else "블로그형"
    return penalty, f"{label} 제목 2개가 너무 비슷합니다."


def _strip_keyword(title: str, keyword: str) -> str:
    title_tokens = _normalize_tokens(title)
    keyword_tokens = _normalize_tokens(keyword)
    stripped_tokens = _remove_keyword_tokens_once(title_tokens, keyword_tokens)
    if stripped_tokens:
        return "".join(stripped_tokens)

    normalized_title = normalize_key(title)
    normalized_keyword = normalize_key(keyword)
    if normalized_keyword and normalized_keyword in normalized_title:
        return normalized_title.replace(normalized_keyword, "", 1)
    return normalized_title


def _is_low_signal_title_skeleton(keyword: str, title: str) -> bool:
    skeleton_label = _build_title_skeleton_label(keyword, title)
    skeleton_key = normalize_key(skeleton_label)
    if not skeleton_key:
        return False
    if skeleton_key in _LOW_SIGNAL_SKELETON_KEYS:
        return True

    skeleton_tokens = _normalize_tokens(skeleton_label)
    if not skeleton_tokens:
        return False
    if len(skeleton_tokens) <= 2 and all(token in _LOW_SIGNAL_SKELETON_TOKENS for token in skeleton_tokens):
        return True

    return (
        len(skeleton_tokens) <= 3
        and skeleton_tokens[0] in {"왜", "무엇", "뭐"}
        and all(token in _LOW_SIGNAL_SKELETON_TOKENS for token in skeleton_tokens[1:])
    )


def _is_hard_reject_title_skeleton(keyword: str, title: str) -> bool:
    skeleton_label = _build_title_skeleton_label(keyword, title)
    skeleton_key = normalize_key(skeleton_label)
    if not skeleton_key:
        return False
    if skeleton_key in _HARD_REJECT_TEMPLATE_SKELETON_KEYS:
        return True
    if any(pattern in skeleton_key for pattern in _HARD_REJECT_TEMPLATE_SUBSTRINGS):
        return True
    if any(pattern in skeleton_key for pattern in _VAGUE_EDITORIAL_SKELETON_PATTERNS):
        return True
    if any(regex.search(skeleton_key) for regex in _VAGUE_EDITORIAL_SKELETON_REGEXES):
        return True

    skeleton_tokens = _normalize_tokens(skeleton_label)
    if not skeleton_tokens:
        return False
    if len(skeleton_tokens) <= 3 and skeleton_tokens[-1] == "공개":
        return True
    return len(skeleton_tokens) <= 5 and all(
        token in _HARD_REJECT_TEMPLATE_TOKENS for token in skeleton_tokens
    )


def _has_generic_overlay_on_practical_keyword(keyword: str, title: str) -> bool:
    keyword_key = normalize_key(keyword)
    if not keyword_key or not any(pattern in keyword_key for pattern in _PRACTICAL_KEYWORD_KEYS):
        return False

    skeleton_label = _build_title_skeleton_label(keyword, title)
    skeleton_key = normalize_key(skeleton_label)
    if not skeleton_key:
        return False
    if not any(pattern in skeleton_key for pattern in _GENERIC_OVERLAY_KEYS):
        return False

    informative_tokens = [
        token
        for token in _normalize_tokens(skeleton_label)
        if token not in _GENERIC_OVERLAY_TOKENS
    ]
    return len(informative_tokens) <= 1


def _has_generic_single_overlay(
    keyword: str,
    title: str,
    *,
    item_context: dict[str, Any],
) -> bool:
    target_mode = normalize_key(item_context.get("target_mode"))
    if target_mode != "single":
        return False

    skeleton_label = _build_title_skeleton_label(keyword, title)
    skeleton_key = normalize_key(skeleton_label)
    if not skeleton_key:
        return False
    if any(pattern in skeleton_key for pattern in _SINGLE_VAGUE_TEASER_PATTERNS):
        return True

    skeleton_tokens = _normalize_tokens(skeleton_label)
    if not skeleton_tokens:
        return False

    single_domain = _infer_single_keyword_domain(keyword, item_context)
    concrete_tokens = _resolve_single_domain_concrete_tokens(single_domain)
    has_concrete_axis = bool(concrete_tokens) and any(token in concrete_tokens for token in skeleton_tokens)

    if _is_low_info_question_skeleton(skeleton_key, skeleton_tokens, has_concrete_axis=has_concrete_axis):
        return True

    keyword_key = normalize_key(keyword)
    source_selection_mode = normalize_key(item_context.get("source_selection_mode") or item_context.get("selection_mode"))
    if source_selection_mode == "seedanchor":
        if "사전예약" in keyword or "사전예약" in keyword_key:
            return not has_concrete_axis
        if "가성비" in keyword or "가성비" in keyword_key:
            return not has_concrete_axis

    source_kind = normalize_key(item_context.get("source_kind"))
    if source_kind == "selectedkeyword" and single_domain in {"product", "stay", "policy"}:
        if has_concrete_axis:
            return False
        return _is_generic_low_info_single_skeleton(skeleton_key, skeleton_tokens)
    return False


def _is_low_info_question_skeleton(
    skeleton_key: str,
    skeleton_tokens: list[str],
    *,
    has_concrete_axis: bool,
) -> bool:
    if has_concrete_axis:
        return False
    if any(pattern in skeleton_key for pattern in _QUESTION_ENDING_PATTERNS):
        return len(skeleton_tokens) <= 6
    return False


def _is_generic_low_info_single_skeleton(skeleton_key: str, skeleton_tokens: list[str]) -> bool:
    if any(pattern in skeleton_key for pattern in _SINGLE_VAGUE_TEASER_PATTERNS):
        return True
    if any(token in _GENERIC_SINGLE_LOW_INFO_TOKENS for token in skeleton_tokens):
        return len(skeleton_tokens) <= 6
    return False


def _has_unverified_freshness_claim(
    keyword: str,
    title: str,
    *,
    item_context: dict[str, Any],
) -> bool:
    title_key = normalize_key(title)
    if not title_key:
        return False
    keyword_key = normalize_key(keyword)
    if any(pattern in keyword_key for pattern in _UNVERIFIED_FRESHNESS_PATTERNS):
        return False
    if any(pattern in title_key for pattern in _UNVERIFIED_FRESHNESS_PATTERNS):
        issue_context = item_context.get("issue_context")
        return not isinstance(issue_context, dict)
    return False


def _infer_single_keyword_domain(keyword: str, item_context: dict[str, Any]) -> str:
    keyword_key = normalize_key(keyword)
    if not keyword_key:
        return "general"
    if "사전예약" in keyword or "사전예약" in keyword_key:
        return "preorder"
    if "가성비" in keyword or "가성비" in keyword_key:
        return "stay"
    detected_category = detect_category(keyword)
    if detected_category == "travel":
        return "stay"
    if detected_category in {"finance", "real_estate"}:
        return "policy"
    if _looks_product_like_context(keyword, item_context):
        return "product"
    return "general"


def _resolve_single_domain_concrete_tokens(domain: str) -> set[str]:
    if domain == "product":
        return _PRODUCT_SINGLE_CONCRETE_TOKENS
    if domain == "preorder":
        return _PREORDER_SINGLE_CONCRETE_TOKENS
    if domain == "stay":
        return _VALUE_SINGLE_CONCRETE_TOKENS
    if domain == "policy":
        return _POLICY_SINGLE_CONCRETE_TOKENS
    return set()


def _looks_product_like_context(keyword: str, item_context: dict[str, Any]) -> bool:
    keyword_key = normalize_key(keyword)
    if any(pattern in keyword_key for pattern in _PRODUCTISH_KEY_PATTERNS):
        return True

    context_tokens: list[str] = [keyword]
    for field_name in ("base_keyword", "source_note"):
        value = item_context.get(field_name)
        if isinstance(value, str) and normalize_text(value):
            context_tokens.append(normalize_text(value))
    for field_name in ("support_keywords", "source_keywords"):
        value = item_context.get(field_name)
        if isinstance(value, list):
            context_tokens.extend(normalize_text(token) for token in value if normalize_text(token))

    for value in context_tokens:
        value_key = normalize_key(value)
        if any(pattern in value_key for pattern in _PRODUCTISH_KEY_PATTERNS):
            return True
        if any(_MODEL_NUMBER_TOKEN_RE.match(token) for token in tokenize_text(value)):
            return True
    return detect_category(keyword) == "product"


def _reorder_titles_for_output(
    item: dict[str, Any],
    report: dict[str, Any],
) -> tuple[dict[str, list[str]], dict[str, list[dict[str, Any]]]]:
    raw_titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
    raw_title_checks = report.get("title_checks") if isinstance(report.get("title_checks"), dict) else {}
    reordered_titles: dict[str, list[str]] = {"naver_home": [], "blog": []}
    reordered_checks: dict[str, list[dict[str, Any]]] = {"naver_home": [], "blog": []}

    for channel_name in ("naver_home", "blog"):
        channel_titles = list(raw_titles.get(channel_name, [])) if isinstance(raw_titles.get(channel_name), list) else []
        channel_checks = list(raw_title_checks.get(channel_name, [])) if isinstance(raw_title_checks.get(channel_name), list) else []
        sorted_titles, sorted_checks = _sort_channel_titles_by_quality(channel_titles, channel_checks)
        reordered_titles[channel_name] = sorted_titles
        reordered_checks[channel_name] = sorted_checks

    return reordered_titles, reordered_checks


def _sort_channel_titles_by_quality(
    titles: list[str],
    title_reports: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    entries = [
        (
            index,
            _normalize_title_surface(title),
            title_reports[index] if index < len(title_reports) and isinstance(title_reports[index], dict) else {},
        )
        for index, title in enumerate(titles)
        if _normalize_title_surface(title)
    ]
    if not entries:
        return [], []

    entries.sort(
        key=lambda entry: (
            _TITLE_STATUS_SORT_RANK.get(str(entry[2].get("status") or "retry"), 3),
            -int(entry[2].get("score") or 0),
            entry[0],
        )
    )
    return [title for _, title, _ in entries], [report for _, _, report in entries]


def _apply_batch_similarity_feedback(
    items: list[dict[str, Any]],
    reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries = _collect_batch_title_entries(items, reports)
    if len(entries) < 2:
        return reports

    skeleton_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for entry in entries:
        skeleton_key = entry["skeleton_key"]
        if skeleton_key:
            skeleton_counts[skeleton_key] = skeleton_counts.get(skeleton_key, 0) + 1
        for family_key in entry["family_keys"]:
            family_counts[family_key] = family_counts.get(family_key, 0) + 1

    repeated_skeletons = {
        skeleton_key
        for skeleton_key, count in skeleton_counts.items()
        if count >= _BATCH_SKELETON_REPEAT_THRESHOLD
    }
    repeated_families = {
        family_key
        for family_key, count in family_counts.items()
        if count >= _resolve_batch_family_repeat_threshold(len(entries))
    }
    if not repeated_skeletons and not repeated_families:
        return reports

    item_contexts: dict[int, dict[str, list[str]]] = {}
    title_contexts: dict[tuple[int, str, int], dict[str, list[str]]] = {}

    for entry in entries:
        repeated_family_keys = [family_key for family_key in entry["family_keys"] if family_key in repeated_families]
        if entry["skeleton_key"] not in repeated_skeletons and not repeated_family_keys:
            continue

        item_context = item_contexts.setdefault(
            entry["item_index"],
            {
                "skeleton_labels": [],
                "family_labels": [],
            },
        )
        title_context = title_contexts.setdefault(
            (entry["item_index"], entry["channel"], entry["title_index"]),
            {
                "skeleton_labels": [],
                "family_labels": [],
            },
        )

        if entry["skeleton_key"] in repeated_skeletons and entry["skeleton_label"]:
            item_context["skeleton_labels"].append(entry["skeleton_label"])
            title_context["skeleton_labels"].append(entry["skeleton_label"])
        for family_key in repeated_family_keys:
            family_label = _family_key_to_label(family_key)
            item_context["family_labels"].append(family_label)
            title_context["family_labels"].append(family_label)

    updated_reports: list[dict[str, Any]] = []
    for index, report in enumerate(reports):
        context = item_contexts.get(index)
        if not context:
            updated_reports.append(report)
            continue

        title_checks = _clone_title_checks(report.get("title_checks", {}))
        for channel_name, title_reports in title_checks.items():
            for title_index, title_report in enumerate(title_reports):
                title_context = title_contexts.get((index, channel_name, title_index))
                if not title_context:
                    continue
                _apply_title_batch_feedback(title_report, title_context)

        rebuilt_report = _build_bundle_report(normalize_text(items[index].get("keyword")), title_checks)
        updated_reports.append(_apply_bundle_batch_feedback(rebuilt_report, context))

    return updated_reports


def _collect_batch_title_entries(
    items: list[dict[str, Any]],
    reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for item_index, (item, report) in enumerate(zip(items, reports)):
        keyword = normalize_text(item.get("keyword"))
        title_checks = report.get("title_checks") if isinstance(report.get("title_checks"), dict) else {}
        for channel_name, channel_reports in title_checks.items():
            if not isinstance(channel_reports, list):
                continue
            for title_index, title_report in enumerate(channel_reports):
                title = normalize_text(title_report.get("title"))
                if not title:
                    continue
                skeleton_label = _build_title_skeleton_label(keyword, title)
                skeleton_key = normalize_key(skeleton_label)
                if not skeleton_key:
                    continue
                entries.append(
                    {
                        "item_index": item_index,
                        "channel": str(channel_name or "").strip(),
                        "title_index": title_index,
                        "skeleton_key": skeleton_key,
                        "skeleton_label": skeleton_label,
                        "family_keys": _detect_batch_family_keys(skeleton_key),
                    }
                )

    return entries


def _apply_title_batch_feedback(title_report: dict[str, Any], context: dict[str, list[str]]) -> None:
    issues = list(title_report.get("issues", []))
    checks = dict(title_report.get("checks", {}))
    score = int(title_report.get("score") or 0)
    skeleton_labels = _unique_preserve_order(context.get("skeleton_labels", []))
    family_labels = _unique_preserve_order(context.get("family_labels", []))

    if skeleton_labels:
        issues.append(_format_batch_skeleton_issue(skeleton_labels))
        score -= min(12, 6 * len(skeleton_labels))
        checks["batch_repeat_risk"] = True
    if family_labels:
        issues.append(_format_batch_family_issue(family_labels))
        score -= min(8, 4 * len(family_labels))
        checks["batch_family_risk"] = True

    score = max(0, min(100, score))
    critical = bool(title_report.get("critical"))
    title_report["score"] = score
    title_report["issues"] = _unique_preserve_order(issues)
    title_report["checks"] = checks
    title_report["status"] = _resolve_title_status(score, critical)


def _apply_bundle_batch_feedback(
    report: dict[str, Any],
    context: dict[str, list[str]],
) -> dict[str, Any]:
    skeleton_labels = _unique_preserve_order(context.get("skeleton_labels", []))
    family_labels = _unique_preserve_order(context.get("family_labels", []))
    issues = list(report.get("issues", []))

    if skeleton_labels:
        issues.append(_format_batch_skeleton_issue(skeleton_labels))
    if family_labels:
        issues.append(_format_batch_family_issue(family_labels))

    issue_list = _unique_preserve_order(issues)
    bundle_score = int(report.get("bundle_score") or 0)
    bundle_score -= min(24, 8 * len(skeleton_labels))
    bundle_score -= min(10, 4 * len(family_labels))
    bundle_score = max(0, bundle_score)

    exact_repeat_risk = bool(skeleton_labels)
    critical_issue = bool(report.get("retry_recommended"))
    passes_threshold = (
        bool(report.get("passes_threshold"))
        and not exact_repeat_risk
        and bundle_score >= TITLE_QUALITY_PASS_SCORE
    )
    status = _resolve_bundle_status(
        bundle_score,
        critical_issue,
        passes_threshold,
        recommended_pair_ready=bool(report.get("recommended_pair_ready")),
    )
    summary = (
        "키워드 노출과 제목 변주 폭이 안정적입니다."
        if not issue_list
        else " / ".join(issue_list[:3])
    )

    return {
        **report,
        "bundle_score": bundle_score,
        "status": status,
        "label": _label_for_status(status),
        "passes_threshold": passes_threshold,
        "retry_recommended": status == "retry",
        "issue_count": len(issue_list),
        "issues": issue_list,
        "summary": summary,
        "batch_repeat_risk": exact_repeat_risk,
        "batch_family_risk": bool(family_labels),
    }


def _build_title_skeleton_label(keyword: str, title: str) -> str:
    title_tokens = tokenize_text(title)
    stripped_tokens = _remove_keyword_tokens_once(title_tokens, tokenize_text(keyword))
    stripped_text = normalize_text(" ".join(stripped_tokens))
    if stripped_text:
        return stripped_text

    normalized_title = normalize_text(title)
    normalized_keyword = normalize_text(keyword)
    if normalized_keyword and normalized_keyword in normalized_title:
        stripped_text = normalize_text(normalized_title.replace(normalized_keyword, "", 1))
        if stripped_text:
            return stripped_text
    return normalized_title


def _remove_keyword_tokens_once(title_tokens: list[str], keyword_tokens: list[str]) -> list[str]:
    normalized_keyword_tokens = [normalize_key(token) for token in keyword_tokens if normalize_key(token)]
    if not normalized_keyword_tokens:
        return title_tokens

    remaining_tokens: list[str] = []
    keyword_index = 0
    for token in title_tokens:
        normalized_token = normalize_key(token)
        if (
            keyword_index < len(normalized_keyword_tokens)
            and normalized_token == normalized_keyword_tokens[keyword_index]
        ):
            keyword_index += 1
            continue
        remaining_tokens.append(token)

    return remaining_tokens if keyword_index == len(normalized_keyword_tokens) else title_tokens


def _detect_batch_family_keys(skeleton_key: str) -> list[str]:
    family_keys: list[str] = []
    for family_key, _, patterns in _BATCH_NOISY_FAMILY_PATTERNS:
        if any(pattern in skeleton_key for pattern in patterns):
            family_keys.append(family_key)
    return family_keys


def _resolve_batch_family_repeat_threshold(total_titles: int) -> int:
    return max(5, min(8, (max(1, total_titles) + 3) // 4))


def _family_key_to_label(family_key: str) -> str:
    for candidate_key, label, _ in _BATCH_NOISY_FAMILY_PATTERNS:
        if family_key == candidate_key:
            return label
    return family_key


def _format_batch_skeleton_issue(skeleton_labels: list[str]) -> str:
    labels = _join_labels_for_issue(skeleton_labels)
    return f"배치에서 '{labels}' 제목 골격이 반복됩니다."


def _format_batch_family_issue(family_labels: list[str]) -> str:
    labels = _join_labels_for_issue(family_labels)
    return f"배치에서 {labels} 계열 표현이 과하게 반복됩니다."


def _join_labels_for_issue(labels: list[str]) -> str:
    unique_labels = _unique_preserve_order(labels)
    if not unique_labels:
        return ""
    if len(unique_labels) == 1:
        return unique_labels[0]
    return ", ".join(unique_labels[:2])


def _clone_title_checks(raw_title_checks: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw_title_checks, dict):
        return {"naver_home": [], "blog": []}

    cloned: dict[str, list[dict[str, Any]]] = {}
    for channel_name in ("naver_home", "blog"):
        channel_reports = raw_title_checks.get(channel_name)
        if not isinstance(channel_reports, list):
            cloned[channel_name] = []
            continue
        cloned[channel_name] = [
            {
                **title_report,
                "issues": list(title_report.get("issues", [])),
                "checks": dict(title_report.get("checks", {})),
            }
            for title_report in channel_reports
        ]
    return cloned


def _resolve_title_status(score: int, critical: bool) -> str:
    if critical or score < TITLE_QUALITY_REVIEW_SCORE:
        return "retry"
    if score < 88:
        return "review"
    return "good"


def _resolve_bundle_status(
    bundle_score: int,
    critical_issue: bool,
    passes_threshold: bool,
    *,
    recommended_pair_ready: bool = False,
) -> str:
    if passes_threshold:
        return "good"
    if recommended_pair_ready and bundle_score >= TITLE_QUALITY_REVIEW_SCORE:
        return "review"
    if bundle_score >= TITLE_QUALITY_REVIEW_SCORE and not critical_issue:
        return "review"
    return "retry"


def _label_for_status(status: str) -> str:
    if status == "good":
        return "양호"
    if status == "review":
        return "재검토"
    return "재생성 권장"


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized_item = normalize_text(item)
        if not normalized_item or normalized_item in seen:
            continue
        seen.add(normalized_item)
        output.append(normalized_item)
    return output
