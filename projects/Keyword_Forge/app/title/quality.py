from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from app.expander.utils.tokenizer import normalize_key, normalize_text, tokenize_text
from app.title.rules import NAVER_HOME_MAX_LENGTH


TITLE_QUALITY_PASS_SCORE = 84
TITLE_QUALITY_REVIEW_SCORE = 75
_NOISY_PUNCTUATION_RE = re.compile(r"[!?]{2,}|\.{3,}")
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


def enrich_title_results(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched_items: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []

    for item in items:
        report = assess_title_bundle(item)
        reports.append(report)
        enriched_items.append(
            {
                **{
                    key: value
                    for key, value in item.items()
                    if key not in {"titles", "quality_report"}
                },
                "keyword": normalize_text(item.get("keyword")),
                "titles": {
                    "naver_home": list(item.get("titles", {}).get("naver_home", [])),
                    "blog": list(item.get("titles", {}).get("blog", [])),
                },
                "quality_report": report,
            }
        )

    return enriched_items, summarize_title_quality(reports)


def assess_title_bundle(item: dict[str, Any]) -> dict[str, Any]:
    keyword = normalize_text(item.get("keyword"))
    titles = item.get("titles") if isinstance(item.get("titles"), dict) else {}
    naver_home_titles = _normalize_title_list(titles.get("naver_home"))
    blog_titles = _normalize_title_list(titles.get("blog"))
    all_titles = naver_home_titles + blog_titles
    duplicate_counts = _count_duplicates(all_titles)

    channel_reports: dict[str, list[dict[str, Any]]] = {
        "naver_home": [
            assess_single_title(keyword, title, "naver_home", duplicate_counts)
            for title in naver_home_titles
        ],
        "blog": [
            assess_single_title(keyword, title, "blog", duplicate_counts)
            for title in blog_titles
        ],
    }

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

    all_reports = channel_reports["naver_home"] + channel_reports["blog"]
    for report in all_reports:
        bundle_issues.extend(report["issues"])

    unique_issues = _unique_preserve_order(bundle_issues)
    bundle_score = round(sum(channel_scores.values()) / len(channel_scores)) if channel_scores else 0

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
        }

    passes_threshold = (
        bundle_score >= TITLE_QUALITY_PASS_SCORE
        and all(score >= TITLE_QUALITY_REVIEW_SCORE for score in channel_scores.values())
        and not critical_issue
    )

    if passes_threshold:
        status = "good"
        label = "양호"
    elif bundle_score >= TITLE_QUALITY_REVIEW_SCORE and not critical_issue:
        status = "review"
        label = "재검토"
    else:
        status = "retry"
        label = "재생성 권장"

    summary = (
        "키워드 노출과 제목 변주 폭이 안정적입니다."
        if not unique_issues
        else " / ".join(unique_issues[:3])
    )

    return {
        "bundle_score": bundle_score,
        "status": status,
        "label": label,
        "passes_threshold": passes_threshold,
        "retry_recommended": status == "retry",
        "issue_count": len(unique_issues),
        "issues": unique_issues,
        "summary": summary,
        "channel_scores": channel_scores,
        "title_checks": channel_reports,
    }


def assess_single_title(
    keyword: str,
    title: str,
    channel: str,
    duplicate_counts: dict[str, int],
) -> dict[str, Any]:
    normalized_title = normalize_text(title)
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

    if _NOISY_PUNCTUATION_RE.search(normalized_title):
        issues.append("구두점 사용이 과합니다.")
        score -= 6

    if duplicate_risk:
        issues.append("다른 제목과 거의 같습니다.")
        score -= 20

    score = max(0, min(100, score))
    if critical or score < TITLE_QUALITY_REVIEW_SCORE:
        status = "retry"
    elif score < 88:
        status = "review"
    else:
        status = "good"

    return {
        "title": normalized_title,
        "score": score,
        "status": status,
        "critical": critical,
        "issues": _unique_preserve_order(issues),
        "checks": {
            "contains_keyword": contains_keyword,
            "starts_with_keyword": starts_with_keyword,
            "length_ok": length_ok,
            "duplicate_risk": duplicate_risk,
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
    return [normalize_text(title) for title in raw_titles if normalize_text(title)]


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
    normalized_title = normalize_key(title)
    normalized_keyword = normalize_key(keyword)
    if normalized_keyword and normalized_title.startswith(normalized_keyword):
        normalized_title = normalized_title[len(normalized_keyword):]
    return normalized_title


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
