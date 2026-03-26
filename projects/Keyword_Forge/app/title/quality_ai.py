from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.expander.utils.tokenizer import normalize_text
from app.title.ai_client import TitleProviderError, request_ai_json_object
from app.title.evaluation_prompt import DEFAULT_TITLE_EVALUATION_PROMPT


@dataclass(frozen=True)
class TitleEvaluationOptions:
    provider: str = ""
    model: str = ""
    api_key: str | None = None
    system_prompt: str = DEFAULT_TITLE_EVALUATION_PROMPT
    temperature: float = 0.1
    max_output_tokens: int = 1400
    batch_size: int = 20

    @property
    def enabled(self) -> bool:
        return bool(
            normalize_text(self.provider)
            and normalize_text(self.model)
            and normalize_text(self.api_key)
            and normalize_text(self.system_prompt)
        )


def request_naver_home_title_evaluations(
    keyword: str,
    titles: list[str],
    options: TitleEvaluationOptions,
) -> dict[str, dict[str, Any]]:
    normalized_titles = [normalize_text(title) for title in titles if normalize_text(title)]
    if not normalized_titles or not options.enabled:
        return {}

    entries = [
        {
            "keyword": keyword,
            "title": title,
        }
        for title in normalized_titles
    ]
    evaluations_by_index = request_naver_home_title_evaluations_batch(entries, options)
    return {
        title: evaluations_by_index.get(index, {})
        for index, title in enumerate(normalized_titles)
    }


def request_naver_home_title_evaluations_batch(
    entries: list[dict[str, Any]],
    options: TitleEvaluationOptions,
) -> dict[int, dict[str, Any]]:
    normalized_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        keyword = normalize_text(entry.get("keyword"))
        title = normalize_text(entry.get("title"))
        if not keyword or not title:
            continue
        normalized_entries.append(
            {
                "index": index,
                "keyword": keyword,
                "title": title,
            }
        )

    if not normalized_entries or not options.enabled:
        return {}

    evaluations_by_index: dict[int, dict[str, Any]] = {}
    payload = request_ai_json_object(
        provider=options.provider,
        api_key=options.api_key,
        model=options.model,
        system_prompt=normalize_text(options.system_prompt),
        user_prompt=_build_naver_home_batch_evaluation_user_prompt(normalized_entries),
        temperature=options.temperature,
        max_output_tokens=options.max_output_tokens,
    )
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    parsed_items = [_normalize_batch_evaluation_item(item) for item in raw_items]
    parsed_items = [item for item in parsed_items if item]
    evaluations_by_index.update(_match_batch_evaluation_items(normalized_entries, parsed_items))

    return evaluations_by_index


def _build_naver_home_evaluation_user_prompt(keyword: str, titles: list[str]) -> str:
    title_lines = "\n".join(f'- "{title}"' for title in titles)
    return (
        "Evaluate the following Naver home titles using the system prompt policy.\n\n"
        "Return JSON in this exact shape:\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "title": "exact input title",\n'
        '      "score": {\n'
        '        "issue_or_context": 0,\n'
        '        "curiosity_gap": 0,\n'
        '        "contrast_or_conflict": 0,\n'
        '        "reversal_or_unexpected": 0,\n'
        '        "emotional_trigger": 0,\n'
        '        "specificity": 0,\n'
        '        "readability": 0,\n'
        '        "total": 0\n'
        "      },\n"
        '      "verdict": "keep",\n'
        '      "reason": "CTR 기준에서 한 줄 평가"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Keep each title field exactly identical to the input title string.\n"
        "- Score every input title independently.\n"
        "- Use integer scores only.\n"
        '- verdict must be either "keep" or "rewrite".\n'
        "- reason must be one short Korean sentence.\n\n"
        f"keyword:\n{normalize_text(keyword)}\n\n"
        f"titles:\n{title_lines}"
    )


def _build_naver_home_batch_evaluation_user_prompt(entries: list[dict[str, Any]]) -> str:
    entry_lines = "\n".join(
        f'- index: {int(entry["index"])} | keyword: "{entry["keyword"]}" | title: "{entry["title"]}"'
        for entry in entries
    )
    return (
        "Evaluate the following Naver home titles using the system prompt policy.\n\n"
        "Return JSON in this exact shape:\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "index": 0,\n'
        '      "keyword": "보험 추천",\n'
        '      "title": "보험 추천, 왜 갈리는 선택 기준일까?",\n'
        '      "score": {\n'
        '        "issue_or_context": 0,\n'
        '        "curiosity_gap": 0,\n'
        '        "contrast_or_conflict": 0,\n'
        '        "reversal_or_unexpected": 0,\n'
        '        "emotional_trigger": 0,\n'
        '        "specificity": 0,\n'
        '        "readability": 0,\n'
        '        "total": 0\n'
        "      },\n"
        '      "verdict": "keep",\n'
        '      "reason": "CTR 기준에서 한 줄 평가"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Return exactly one item for every input entry.\n"
        "- Preserve the same order as the input list.\n"
        "- Keep each index, keyword, and title field identical to the input entry.\n"
        "- Score every input title independently.\n"
        "- Use integer scores only.\n"
        '- verdict must be either "keep" or "rewrite".\n'
        "- reason must be one short Korean sentence.\n\n"
        f"entries:\n{entry_lines}"
    )


def _normalize_evaluation_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}

    raw_score = item.get("score") if isinstance(item.get("score"), dict) else {}
    score_breakdown: dict[str, int] = {}
    total = None
    for key, value in raw_score.items():
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        bounded = max(0, min(100, number))
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        score_breakdown[normalized_key] = bounded
        if normalized_key == "total":
            total = bounded

    if total is None:
        computed_total = sum(number for key, number in score_breakdown.items() if key != "total")
        total = max(0, min(100, computed_total))
        score_breakdown["total"] = total

    verdict = str(item.get("verdict") or "").strip().lower()
    if verdict not in {"keep", "rewrite"}:
        verdict = "keep" if total >= 85 else "rewrite"

    return {
        "title": normalize_text(item.get("title")),
        "score_breakdown": score_breakdown,
        "score": total,
        "verdict": verdict,
        "reason": normalize_text(item.get("reason")),
    }


def _normalize_batch_evaluation_item(item: Any) -> dict[str, Any]:
    parsed = _normalize_evaluation_item(item)
    if not parsed:
        return {}

    try:
        index = int(item.get("index"))
    except (AttributeError, TypeError, ValueError):
        index = -1

    parsed["index"] = index
    parsed["keyword"] = normalize_text(item.get("keyword"))
    return parsed


def _match_batch_evaluation_items(
    input_entries: list[dict[str, Any]],
    parsed_items: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    matched: dict[int, dict[str, Any]] = {}
    used_input_indexes: set[int] = set()
    valid_input_indexes = {int(entry["index"]) for entry in input_entries}
    remaining_by_title: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for entry in input_entries:
        key = (normalize_text(entry.get("keyword")), normalize_text(entry.get("title")))
        remaining_by_title.setdefault(key, []).append(entry)

    for parsed in parsed_items:
        try:
            parsed_index = int(parsed.get("index"))
        except (TypeError, ValueError):
            parsed_index = -1
        if parsed_index >= 0 and parsed_index in valid_input_indexes and parsed_index not in used_input_indexes:
            matched[parsed_index] = parsed
            used_input_indexes.add(parsed_index)
            continue

        key = (normalize_text(parsed.get("keyword")), normalize_text(parsed.get("title")))
        candidates = remaining_by_title.get(key) or []
        while candidates:
            candidate = candidates.pop(0)
            candidate_index = int(candidate["index"])
            if candidate_index in used_input_indexes:
                continue
            matched[candidate_index] = parsed
            used_input_indexes.add(candidate_index)
            break

    fallback_items = list(parsed_items)
    fallback_index = 0
    for entry in input_entries:
        entry_index = int(entry["index"])
        if entry_index in matched:
            continue
        while fallback_index < len(fallback_items):
            candidate = fallback_items[fallback_index]
            fallback_index += 1
            try:
                candidate_index = int(candidate.get("index"))
            except (TypeError, ValueError):
                candidate_index = -1
            if candidate_index in used_input_indexes:
                continue
            matched[entry_index] = candidate
            used_input_indexes.add(entry_index)
            break

    return matched
