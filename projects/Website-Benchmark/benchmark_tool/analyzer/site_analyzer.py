from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

BUTTON_INPUT_TYPES = {"button", "submit", "reset"}
API_ENDPOINT_REGEX = re.compile(r"/api/[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", re.IGNORECASE)
FETCH_CALL_REGEX = re.compile(r"fetch\s*\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
XHR_OPEN_REGEX = re.compile(r"\.open\s*\(\s*[\"'][A-Z]+[\"']\s*,\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
AXIOS_CALL_REGEX = re.compile(r"axios\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
AJAX_URL_REGEX = re.compile(r"url\s*:\s*[\"']([^\"']+)[\"']", re.IGNORECASE)

CORE_FUNCTION_ORDER = [
    "keyword_analysis",
    "keyword_expansion",
    "scoring_system",
    "data_filtering",
    "content_guidance",
]
SITE_TYPE_ORDER = ["keyword_tool", "content_site", "general_website"]
FEATURE_LOGIC_ORDER = [
    "keyword_analysis",
    "keyword_expansion",
    "keyword_scoring",
    "data_filtering",
    "content_guidance",
]
FEATURE_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "keyword_analysis": {
        "goal": "키워드 검색",
        "description": "사용자가 키워드의 검색량, CPC, 경쟁도를 확인하려고 할 때 선택하는 기능",
        "ui_roles": ["keyword search", "bulk keyword input", "data results"],
        "input_roles": ["keyword seed", "bulk keyword seed"],
        "output_roles": ["keyword metrics"],
        "flow_names": ["keyword_analysis_flow"],
        "feature_names": ["keyword_analysis"],
        "business_logic_items": ["고CPC 키워드 우선 노출", "검색량 + 경쟁도 조합 분석"],
    },
    "keyword_expansion": {
        "goal": "키워드 확장",
        "description": "기본 키워드에서 연관어와 추천 키워드를 넓혀서 후보군을 만들 때 선택하는 기능",
        "ui_roles": ["keyword search", "bulk keyword input", "keyword suggestions"],
        "input_roles": ["keyword seed", "bulk keyword seed"],
        "output_roles": ["related keyword suggestions"],
        "flow_names": ["keyword_expansion_flow"],
        "feature_names": ["keyword_expansion"],
        "business_logic_items": ["연관 키워드 추천 및 확장"],
    },
    "scoring_system": {
        "goal": "점수 계산",
        "description": "검색량, CPC, 경쟁도를 조합해 키워드 우선순위를 계산해야 할 때 선택하는 기능",
        "ui_roles": ["data filtering", "data results"],
        "input_roles": ["keyword seed", "metric conditions"],
        "output_roles": ["keyword metrics"],
        "flow_names": ["keyword_analysis_flow"],
        "feature_names": ["keyword_scoring"],
        "business_logic_items": ["검색량 + 경쟁도 조합 분석", "CPC 기반 키워드 점수화"],
    },
    "data_filtering": {
        "goal": "필터링",
        "description": "결과를 검색량, CPC, 경쟁도 조건으로 좁혀야 할 때 선택하는 기능",
        "ui_roles": ["data filtering", "data results"],
        "input_roles": ["metric conditions"],
        "output_roles": ["keyword metrics"],
        "flow_names": ["keyword_analysis_flow"],
        "feature_names": ["data_filtering"],
        "business_logic_items": ["고가 키워드 필터링"],
    },
    "content_guidance": {
        "goal": "콘텐츠 제공",
        "description": "가이드나 블로그 문서로 전략과 사용법을 설명해야 할 때 선택하는 기능",
        "ui_roles": ["guide content"],
        "input_roles": [],
        "output_roles": ["guide articles"],
        "flow_names": ["content_to_tool_flow"],
        "feature_names": ["content_guidance"],
        "business_logic_items": [],
    },
}
UI_COMPONENT_ORDER = [
    ("input", "keyword search"),
    ("textarea", "bulk keyword input"),
    ("filter", "data filtering"),
    ("table", "data results"),
    ("list", "keyword suggestions"),
    ("list", "data results"),
    ("article", "guide content"),
]
IMPORTANT_KEYWORD_RULES = [
    ("CPC", ("cpc",)),
    ("검색량", ("검색량", "search volume")),
    ("키워드", ("키워드", "keyword")),
    ("확장", ("확장", "연관", "related", "expand", "조합", "combine")),
    ("추천", ("추천", "recommend", "suggest")),
]
CONTENT_TERMS = (
    "blog",
    "article",
    "guide",
    "manual",
    "tutorial",
    "블로그",
    "가이드",
    "사용법",
    "방법",
    "문서",
    "콘텐츠",
)
KEYWORD_TERMS = (
    "키워드",
    "keyword",
    "검색어",
    "seed keyword",
    "연관검색어",
    "롱테일",
)
METRIC_TERMS = (
    "cpc",
    "검색량",
    "search volume",
    "경쟁",
    "competition",
    "score",
    "점수",
    "스코어",
)
EXPANSION_TERMS = (
    "확장",
    "연관",
    "추천",
    "related",
    "expand",
    "recommend",
    "suggest",
    "seed",
    "조합",
    "combine",
)
FILTER_TERMS = (
    "filter",
    "sort",
    "정렬",
    "필터",
    "조건",
    "범위",
    "최소",
    "최대",
)
SCORING_TERMS = (
    "score",
    "scoring",
    "점수",
    "스코어",
    "황금키워드",
    "golden keyword",
)
NAVER_TERMS = ("네이버", "naver", "검색광고", "searchad")
API_TERMS = ("api", "endpoint", "fetch", "xhr", "ajax")
CRAWLING_TERMS = ("크롤링", "crawler", "crawl", "scraping", "수집")
SAAS_TERMS = ("가격안내", "pricing", "plan", "subscription", "구독", "요금", "무료", "유료", "trial", "upgrade")
AD_TERMS = ("광고", "ad", "애드센스", "애드포스트", "광고수익")


def analyze_document(source_path: str, html: str, soup: BeautifulSoup) -> dict[str, Any]:
    inputs = extract_input_components(soup)
    buttons = extract_button_components(soup)
    forms = extract_form_components(soup)
    tables = extract_table_components(soup)
    lists = extract_list_components(soup)
    api_patterns = extract_api_patterns(soup, html)
    text = full_text(soup)

    signals = build_semantic_signals(text, inputs, buttons, forms, tables, lists, api_patterns)
    core_functions = infer_core_functions(signals)
    site_type = infer_site_type(signals)
    ui_components = summarize_ui_components(signals)
    data_inputs = summarize_data_inputs(signals)
    data_outputs = summarize_data_outputs(signals)
    user_flow = infer_user_flow(core_functions, site_type, ui_components)
    feature_logic = infer_feature_logic(core_functions, signals)
    monetization_model = infer_monetization_model(core_functions, site_type, signals)
    data_source = infer_data_source(signals)
    business_logic = infer_business_logic(core_functions, signals)

    return {
        "site_type": site_type,
        "core_functions": core_functions,
        "important_keywords": signals["important_keywords"],
        "monetization_model": monetization_model,
        "data_source": data_source,
        "business_logic": business_logic,
        "ui_components": ui_components,
        "user_flow": user_flow,
        "data_inputs": data_inputs,
        "data_outputs": data_outputs,
        "api_patterns": api_patterns,
        "feature_logic": feature_logic,
    }


def merge_site_analyses(
    document_analyses: list[dict[str, Any]],
    content_exports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    content_exports = content_exports or []
    source_files = [str(item["source_file"]) for item in document_analyses]

    site_types: list[str] = []
    core_functions: list[str] = []
    important_keywords: list[str] = []
    monetization_models: list[str] = []
    data_sources: list[str] = []
    business_logic: list[str] = []
    ui_components: list[dict[str, Any]] = []
    user_flow: list[dict[str, Any]] = []
    data_inputs: list[dict[str, Any]] = []
    data_outputs: list[dict[str, Any]] = []
    api_patterns: list[dict[str, Any]] = []
    feature_logic: list[dict[str, Any]] = []

    for document in document_analyses:
        analysis = document["analysis"]
        site_types.extend(list(analysis.get("site_type", [])))
        core_functions.extend(list(analysis.get("core_functions", [])))
        important_keywords.extend(list(analysis.get("important_keywords", [])))
        monetization_models.append(str(analysis.get("monetization_model", "")))
        data_sources.append(str(analysis.get("data_source", "")))
        business_logic.extend(list(analysis.get("business_logic", [])))
        ui_components.extend(list(analysis.get("ui_components", [])))
        user_flow.extend(list(analysis.get("user_flow", [])))
        data_inputs.extend(list(analysis.get("data_inputs", [])))
        data_outputs.extend(list(analysis.get("data_outputs", [])))
        api_patterns.extend(list(analysis.get("api_patterns", [])))
        feature_logic.extend(list(analysis.get("feature_logic", [])))

    if content_exports:
        site_types.append("content_site")
        if "content_guidance" not in core_functions:
            core_functions.append("content_guidance")
        ui_components.append({"type": "article", "role": "guide content"})
        feature_logic.append(
            {
                "feature": "content_guidance",
                "logic": "블로그/가이드 콘텐츠로 키워드 전략과 도구 사용법을 제공",
            }
        )

    merged_site_types = order_values(deduplicate_strings(site_types), SITE_TYPE_ORDER)
    merged_core_functions = order_values(deduplicate_strings(core_functions), CORE_FUNCTION_ORDER)
    merged_keywords = order_values(deduplicate_strings(important_keywords), [item[0] for item in IMPORTANT_KEYWORD_RULES])
    merged_monetization_model = select_best_monetization_model(monetization_models, merged_core_functions, merged_site_types, merged_keywords)
    merged_data_source = select_best_data_source(data_sources, merged_keywords)
    merged_business_logic = order_business_logic(deduplicate_strings(business_logic))
    merged_ui_components = order_ui_components(deduplicate_dicts(ui_components, ("type", "role")))
    merged_user_flow = deduplicate_dicts(user_flow, ("name", "process"))
    merged_data_inputs = deduplicate_dicts(data_inputs, ("type", "role"))
    merged_data_outputs = deduplicate_dicts(data_outputs, ("type", "role"))
    merged_api_patterns = deduplicate_dicts(api_patterns, ("type", "pattern"))
    merged_feature_logic = order_feature_logic(merge_feature_logic_values(feature_logic))
    features = build_features(
        merged_core_functions,
        merged_ui_components,
        merged_data_inputs,
        merged_data_outputs,
        merged_user_flow,
        merged_feature_logic,
        merged_business_logic,
    )

    if not merged_site_types:
        merged_site_types = infer_integrated_site_type(merged_core_functions, merged_keywords, content_exports)

    return {
        "pages_analyzed": len(document_analyses),
        "source_files": source_files,
        "site_type": merged_site_types,
        "important_keywords": merged_keywords,
        "core_functions": merged_core_functions,
        "monetization_model": merged_monetization_model,
        "data_source": merged_data_source,
        "business_logic": merged_business_logic,
        "ui_components": merged_ui_components,
        "user_flow": merged_user_flow,
        "data_inputs": merged_data_inputs,
        "data_outputs": merged_data_outputs,
        "api_patterns": merged_api_patterns,
        "feature_logic": merged_feature_logic,
        "features": features,
        "content_exports": slim_content_exports(content_exports),
    }


def extract_input_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tag in soup.find_all(["input", "textarea", "select"]):
        label = tag_label(tag, soup)
        results.append(
            {
                "component_type": tag.name,
                "role": classify_input_role(tag, label),
                "label": label,
                "name": tag.get("name", ""),
                "selector_hint": selector_hint(tag),
            }
        )
    return results


def extract_button_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tag in soup.find_all(["button", "input"]):
        if tag.name == "input" and tag.get("type", "").lower() not in BUTTON_INPUT_TYPES:
            continue
        label = tag_label(tag, soup)
        results.append(
            {
                "component_type": "button",
                "role": classify_button_role(tag, label),
                "label": label,
                "selector_hint": selector_hint(tag),
            }
        )
    return results


def extract_form_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for form in soup.find_all("form"):
        child_roles = [classify_input_role(tag, tag_label(tag, soup)) for tag in form.find_all(["input", "textarea", "select"])]
        submit_labels = [
            tag_label(tag, soup)
            for tag in form.find_all(["button", "input"])
            if tag.name == "button" or tag.get("type", "").lower() in BUTTON_INPUT_TYPES
        ]
        results.append(
            {
                "component_type": "form",
                "role": infer_form_role(form, child_roles, submit_labels),
                "label": contextual_label(form, soup),
                "action": form.get("action", ""),
            }
        )
    return results


def extract_table_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        headers = [clean_text(cell.get_text(" ", strip=True)) for cell in table.find_all("th")]
        results.append(
            {
                "component_type": "table",
                "role": classify_table_role(headers, contextual_label(table, soup)),
                "label": contextual_label(table, soup),
                "headers": [header for header in headers if header],
            }
        )
    return results


def extract_list_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tag in soup.find_all(["ul", "ol", "dl"]):
        item_texts = extract_list_items(tag)
        if not item_texts:
            continue
        results.append(
            {
                "component_type": "list",
                "role": classify_list_role(tag, item_texts, contextual_label(tag, soup)),
                "label": contextual_label(tag, soup),
                "items_preview": item_texts[:3],
            }
        )
    return results


def build_semantic_signals(
    text: str,
    inputs: list[dict[str, Any]],
    buttons: list[dict[str, Any]],
    forms: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    lists: list[dict[str, Any]],
    api_patterns: list[dict[str, Any]],
) -> dict[str, Any]:
    input_roles = {item["role"] for item in inputs}
    button_roles = {item["role"] for item in buttons}
    form_roles = {item["role"] for item in forms}
    table_roles = {item["role"] for item in tables}
    list_roles = {item["role"] for item in lists}
    important_keywords = detect_important_keywords(text)

    has_keyword_context = contains_any(text, KEYWORD_TERMS) or "키워드" in important_keywords
    has_metric_context = contains_any(text, METRIC_TERMS) or bool(table_roles & {"keyword_metrics", "keyword_results"})
    has_expansion_context = contains_any(text, EXPANSION_TERMS) or bool(
        {"expand_keywords", "keyword_suggestions", "keyword_expansion_form"} & (button_roles | list_roles | form_roles)
    )
    has_filter_context = contains_any(text, FILTER_TERMS) or bool({"filter_control", "filter_action", "filter_form"} & (input_roles | button_roles | form_roles))
    has_scoring_context = contains_any(text, SCORING_TERMS) or (
        ("CPC" in important_keywords) and ("검색량" in important_keywords) and contains_any(text, ("경쟁", "competition", "난이도"))
    )
    has_content_context = contains_any(text, CONTENT_TERMS)
    has_naver_context = contains_any(text, NAVER_TERMS)
    has_api_context = contains_any(text, API_TERMS) or bool(api_patterns)
    has_crawling_context = contains_any(text, CRAWLING_TERMS)
    has_saas_context = contains_any(text, SAAS_TERMS)
    has_ad_context = contains_any(text, AD_TERMS)

    return {
        "important_keywords": important_keywords,
        "has_keyword_context": has_keyword_context,
        "has_metric_context": has_metric_context,
        "has_expansion_context": has_expansion_context,
        "has_filter_context": has_filter_context,
        "has_scoring_context": has_scoring_context,
        "has_content_context": has_content_context,
        "has_naver_context": has_naver_context,
        "has_api_context": has_api_context,
        "has_crawling_context": has_crawling_context,
        "has_saas_context": has_saas_context,
        "has_ad_context": has_ad_context,
        "has_keyword_input": bool({"keyword_input", "bulk_keyword_input"} & input_roles),
        "has_results": bool(table_roles | list_roles),
        "has_results_table": bool(tables),
        "has_suggestion_list": "keyword_suggestions" in list_roles,
        "has_api": bool(api_patterns),
        "inputs": inputs,
        "buttons": buttons,
        "forms": forms,
        "tables": tables,
        "lists": lists,
    }


def infer_core_functions(signals: dict[str, Any]) -> list[str]:
    functions: list[str] = []

    if signals["has_keyword_context"] and (
        signals["has_keyword_input"] or signals["has_metric_context"] or signals["has_results"] or signals["has_api"]
    ):
        functions.append("keyword_analysis")
    if signals["has_expansion_context"]:
        functions.append("keyword_expansion")
    if signals["has_scoring_context"]:
        functions.append("scoring_system")
    if signals["has_filter_context"]:
        functions.append("data_filtering")
    if signals["has_content_context"]:
        functions.append("content_guidance")

    return order_values(deduplicate_strings(functions), CORE_FUNCTION_ORDER)


def infer_site_type(signals: dict[str, Any]) -> list[str]:
    site_types: list[str] = []
    important_keywords = set(signals["important_keywords"])

    if important_keywords & {"CPC", "검색량", "키워드", "확장", "추천"} or (
        signals["has_keyword_context"] and (signals["has_metric_context"] or signals["has_keyword_input"])
    ):
        site_types.append("keyword_tool")
    if signals["has_content_context"]:
        site_types.append("content_site")
    if not site_types:
        site_types.append("general_website")

    return order_values(deduplicate_strings(site_types), SITE_TYPE_ORDER)


def summarize_ui_components(signals: dict[str, Any]) -> list[dict[str, str]]:
    components: list[dict[str, str]] = []
    if signals["has_keyword_input"]:
        components.append({"type": "input", "role": "keyword search"})
    if any(item["role"] == "bulk_keyword_input" for item in signals["inputs"]):
        components.append({"type": "textarea", "role": "bulk keyword input"})
    if signals["has_filter_context"]:
        components.append({"type": "filter", "role": "data filtering"})
    if signals["has_results_table"]:
        components.append({"type": "table", "role": "data results"})
    elif signals["has_results"]:
        components.append({"type": "list", "role": "data results"})
    if signals["has_suggestion_list"] or signals["has_expansion_context"]:
        components.append({"type": "list", "role": "keyword suggestions"})
    if signals["has_content_context"]:
        components.append({"type": "article", "role": "guide content"})
    return deduplicate_dicts(components, ("type", "role"))


def summarize_data_inputs(signals: dict[str, Any]) -> list[dict[str, str]]:
    inputs: list[dict[str, str]] = []
    if signals["has_keyword_input"]:
        inputs.append({"type": "input", "role": "keyword seed"})
    if any(item["role"] == "bulk_keyword_input" for item in signals["inputs"]):
        inputs.append({"type": "textarea", "role": "bulk keyword seed"})
    if signals["has_filter_context"]:
        inputs.append({"type": "filter", "role": "metric conditions"})
    return deduplicate_dicts(inputs, ("type", "role"))


def summarize_data_outputs(signals: dict[str, Any]) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    if signals["has_results_table"]:
        outputs.append({"type": "table", "role": "keyword metrics"})
    elif signals["has_results"]:
        outputs.append({"type": "list", "role": "keyword results"})
    if signals["has_suggestion_list"] or signals["has_expansion_context"]:
        outputs.append({"type": "list", "role": "related keyword suggestions"})
    if signals["has_content_context"]:
        outputs.append({"type": "article", "role": "guide articles"})
    return deduplicate_dicts(outputs, ("type", "role"))


def infer_user_flow(
    core_functions: list[str],
    site_type: list[str],
    ui_components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    component_roles = {item["role"] for item in ui_components}
    flows: list[dict[str, Any]] = []

    if "keyword_analysis" in core_functions:
        flows.append(
            {
                "name": "keyword_analysis_flow",
                "process": "키워드를 입력하고 검색량, CPC, 경쟁도 데이터를 조회",
                "output": "data results" if "data results" in component_roles else "keyword metrics",
            }
        )
    if "keyword_expansion" in core_functions:
        flows.append(
            {
                "name": "keyword_expansion_flow",
                "process": "기본 키워드에서 연관어와 추천 키워드를 확장",
                "output": "keyword suggestions",
            }
        )
    if "content_site" in site_type:
        flows.append(
            {
                "name": "content_to_tool_flow",
                "process": "가이드 콘텐츠에서 전략을 설명하고 도구 사용으로 연결",
                "output": "guide content",
            }
        )
    return deduplicate_dicts(flows, ("name", "process"))


def infer_feature_logic(core_functions: list[str], signals: dict[str, Any]) -> list[dict[str, str]]:
    feature_logic: list[dict[str, str]] = []

    if "keyword_analysis" in core_functions:
        logic = "입력 키워드의 검색량, CPC, 경쟁도 데이터를 조회"
        feature_logic.append({"feature": "keyword_analysis", "logic": logic})
    if "keyword_expansion" in core_functions:
        feature_logic.append(
            {
                "feature": "keyword_expansion",
                "logic": "기본 키워드에서 연관어, 추천어, 조합 키워드를 생성",
            }
        )
    if "scoring_system" in core_functions:
        if {"CPC", "검색량"} <= set(signals["important_keywords"]) and contains_any(full_text_from_signals(signals), ("경쟁", "competition", "난이도")):
            scoring_logic = "CPC + 검색량 + 경쟁도 기반 점수 계산"
        elif {"CPC", "검색량"} <= set(signals["important_keywords"]):
            scoring_logic = "CPC + 검색량 기반 점수 계산"
        else:
            scoring_logic = "키워드 지표를 조합해 우선순위 점수 계산"
        feature_logic.append({"feature": "keyword_scoring", "logic": scoring_logic})
    if "data_filtering" in core_functions:
        feature_logic.append(
            {
                "feature": "data_filtering",
                "logic": "검색량, CPC, 경쟁도 조건으로 결과를 필터링",
            }
        )
    if "content_guidance" in core_functions:
        feature_logic.append(
            {
                "feature": "content_guidance",
                "logic": "블로그/가이드 콘텐츠로 키워드 전략과 도구 사용법을 제공",
            }
        )

    return order_feature_logic(deduplicate_dicts(feature_logic, ("feature", "logic")))


def infer_monetization_model(core_functions: list[str], site_type: list[str], signals: dict[str, Any]) -> str:
    feature_set = set(core_functions)
    if "keyword_tool" in site_type and "scoring_system" in feature_set:
        return "CPC 기반 키워드 분석 SaaS"
    if "keyword_tool" in site_type and signals["has_metric_context"]:
        return "키워드 데이터 제공 서비스"
    if "content_site" in site_type and signals["has_ad_context"]:
        return "광고 기반 콘텐츠 수익"
    if "content_site" in site_type:
        return "콘텐츠 기반 유입 서비스"
    return "일반 웹서비스"


def infer_data_source(signals: dict[str, Any]) -> str:
    if signals["has_naver_context"] and signals["has_api_context"]:
        return "네이버 광고 API 추정"
    if signals["has_naver_context"] and signals["has_metric_context"]:
        return "네이버 검색 데이터 추정"
    if signals["has_crawling_context"]:
        return "크롤링 데이터 추정"
    if signals["has_metric_context"]:
        return "검색 데이터 추정"
    return "데이터 출처 불명"


def infer_business_logic(core_functions: list[str], signals: dict[str, Any]) -> list[str]:
    logic: list[str] = []
    keyword_set = set(signals["important_keywords"])
    signal_text = full_text_from_signals(signals)

    if "scoring_system" in core_functions:
        if {"CPC", "검색량"} <= keyword_set and contains_any(signal_text, ("경쟁", "competition", "난이도")):
            logic.append("검색량 + 경쟁도 조합 분석")
        logic.append("CPC 기반 키워드 점수화")
    if "keyword_analysis" in core_functions and "CPC" in keyword_set:
        logic.append("고CPC 키워드 우선 노출")
    if "data_filtering" in core_functions and "CPC" in keyword_set:
        logic.append("고가 키워드 필터링")
    if "keyword_expansion" in core_functions:
        logic.append("연관 키워드 추천 및 확장")
    return order_business_logic(deduplicate_strings(logic))


def build_features(
    core_functions: list[str],
    ui_components: list[dict[str, Any]],
    data_inputs: list[dict[str, Any]],
    data_outputs: list[dict[str, Any]],
    user_flow: list[dict[str, Any]],
    feature_logic: list[dict[str, Any]],
    business_logic: list[str],
) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    ui_role_map = {item["role"]: item for item in ui_components}
    input_role_map = {item["role"]: item for item in data_inputs}
    output_role_map = {item["role"]: item for item in data_outputs}
    flow_name_map = {item["name"]: item for item in user_flow}
    feature_name_map = {item["feature"]: item for item in feature_logic}

    for function_name in core_functions:
        blueprint = FEATURE_BLUEPRINTS.get(function_name)
        if blueprint is None:
            continue

        feature_ui = order_ui_components([ui_role_map[role] for role in blueprint["ui_roles"] if role in ui_role_map])
        feature_inputs = order_data_ports([input_role_map[role] for role in blueprint["input_roles"] if role in input_role_map])
        feature_outputs = order_data_ports([output_role_map[role] for role in blueprint["output_roles"] if role in output_role_map])

        logic_entries: list[str] = []
        for feature_name in blueprint["feature_names"]:
            feature = feature_name_map.get(feature_name)
            if feature:
                logic_entries.append(str(feature["logic"]))
        for flow_name in blueprint["flow_names"]:
            flow = flow_name_map.get(flow_name)
            if flow:
                logic_entries.append(str(flow["process"]))
        feature_business_logic = [
            item for item in business_logic if item in blueprint["business_logic_items"]
        ]
        logic_entries.extend(feature_business_logic)

        features.append(
            {
                "goal": blueprint["goal"],
                "description": blueprint["description"],
                "inputs": feature_inputs,
                "outputs": feature_outputs,
                "logic": deduplicate_strings(logic_entries),
                "ui": feature_ui,
            }
        )

    return features


def extract_api_patterns(soup: BeautifulSoup, html: str) -> list[dict[str, str]]:
    patterns: list[dict[str, str]] = []
    for form in soup.find_all("form"):
        action = str(form.get("action", ""))
        if action and ("/api/" in action or action.startswith("/")):
            patterns.append({"type": "form_action", "pattern": action})
    for tag in soup.find_all(True):
        for attr_name, attr_value in tag.attrs.items():
            values = attr_value if isinstance(attr_value, list) else [attr_value]
            for value in values:
                if isinstance(value, str) and "/api/" in value:
                    patterns.append({"type": f"{tag.name}.{attr_name}", "pattern": value})

    script_texts = [script.string or script.get_text(" ", strip=False) for script in soup.find_all("script")]
    raw_text = "\n".join([html] + [text for text in script_texts if text])
    for endpoint in API_ENDPOINT_REGEX.findall(raw_text):
        patterns.append({"type": "endpoint", "pattern": endpoint})
    for endpoint in FETCH_CALL_REGEX.findall(raw_text):
        patterns.append({"type": "fetch", "pattern": endpoint})
    for endpoint in XHR_OPEN_REGEX.findall(raw_text):
        patterns.append({"type": "xhr", "pattern": endpoint})
    for method, endpoint in AXIOS_CALL_REGEX.findall(raw_text):
        patterns.append({"type": f"axios_{method.lower()}", "pattern": endpoint})
    for endpoint in AJAX_URL_REGEX.findall(raw_text):
        patterns.append({"type": "ajax", "pattern": endpoint})
    return deduplicate_dicts(patterns, ("type", "pattern"))


def detect_important_keywords(text: str) -> list[str]:
    found: list[str] = []
    for canonical, keywords in IMPORTANT_KEYWORD_RULES:
        if any(keyword in text for keyword in keywords):
            found.append(canonical)
    return found


def extract_list_items(tag: Tag) -> list[str]:
    if tag.name == "dl":
        values = [clean_text(item.get_text(" ", strip=True)) for item in tag.find_all(["dt", "dd"], recursive=False)]
    else:
        values = [clean_text(item.get_text(" ", strip=True)) for item in tag.find_all("li", recursive=False)]
    return [value for value in values if value]


def classify_input_role(tag: Tag, label: str) -> str:
    input_type = str(tag.get("type", tag.name)).lower()
    haystack = component_haystack(tag, label)
    if input_type == "password" or "password" in haystack:
        return "password_field"
    if any(keyword in haystack for keyword in ("키워드", "keyword", "검색어", "seed", "주제")):
        if tag.name == "textarea" or input_type == "textarea":
            return "bulk_keyword_input"
        return "keyword_input"
    if input_type == "search" or any(keyword in haystack for keyword in ("search", "query", "find", "조회", "검색")):
        return "keyword_input"
    if input_type in {"checkbox", "radio"} or tag.name == "select" or any(keyword in haystack for keyword in FILTER_TERMS):
        return "filter_control"
    if input_type == "email" or "email" in haystack:
        return "email_field"
    if tag.name == "textarea":
        return "long_text"
    return "text_entry"


def classify_button_role(tag: Tag, label: str) -> str:
    haystack = component_haystack(tag, label)
    if any(keyword in haystack for keyword in ("확장", "추천", "연관", "combine", "expand", "suggest", "recommend")):
        return "expand_keywords"
    if any(keyword in haystack for keyword in ("filter", "apply", "sort", "refine", "필터", "정렬", "적용")):
        return "filter_action"
    if any(keyword in haystack for keyword in ("search", "find", "lookup", "analy", "조회", "검색", "분석")):
        return "run_analysis"
    return "generic_action"


def infer_form_role(form: Tag, child_input_roles: list[str], submit_labels: list[str]) -> str:
    joined = " ".join(submit_labels).lower()
    action = str(form.get("action", "")).lower()
    if "keyword_input" in child_input_roles or "bulk_keyword_input" in child_input_roles:
        if any(keyword in joined or keyword in action for keyword in ("확장", "추천", "연관", "combine", "expand")):
            return "keyword_expansion_form"
        return "keyword_search_form"
    if "filter_control" in child_input_roles:
        return "filter_form"
    return "data_entry_form"


def classify_table_role(headers: list[str], label: str) -> str:
    haystack = clean_text(" ".join(headers + [label])).lower()
    if contains_any(haystack, METRIC_TERMS):
        return "keyword_metrics"
    return "keyword_results"


def classify_list_role(tag: Tag, item_texts: list[str], label: str) -> str:
    if tag.find_parent("nav"):
        return "navigation"
    haystack = clean_text(" ".join(item_texts[:5] + [label])).lower()
    if contains_any(haystack, EXPANSION_TERMS):
        return "keyword_suggestions"
    if contains_any(haystack, CONTENT_TERMS):
        return "guide_list"
    return "keyword_results"


def infer_integrated_site_type(
    core_functions: list[str],
    important_keywords: list[str],
    content_exports: list[dict[str, Any]],
) -> list[str]:
    site_types: list[str] = []
    if important_keywords or any(name in core_functions for name in ("keyword_analysis", "keyword_expansion", "scoring_system")):
        site_types.append("keyword_tool")
    if content_exports or "content_guidance" in core_functions:
        site_types.append("content_site")
    if not site_types:
        site_types.append("general_website")
    return order_values(deduplicate_strings(site_types), SITE_TYPE_ORDER)


def slim_content_exports(content_exports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slimmed: list[dict[str, Any]] = []
    for item in content_exports:
        slimmed.append(
            {
                "index": item.get("index"),
                "title": item.get("title", ""),
                "source_file": item.get("source_file", ""),
                "html_file": item.get("html_file", ""),
                "markdown_file": item.get("markdown_file", ""),
            }
        )
    return slimmed


def full_text_from_signals(signals: dict[str, Any]) -> str:
    values: list[str] = []
    for collection_name in ("inputs", "buttons", "forms", "tables", "lists"):
        for item in signals.get(collection_name, []):
            values.extend(str(value) for value in item.values())
    return clean_text(" ".join(values)).lower()


def contains_any(text: str, keywords: tuple[str, ...] | list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def deduplicate_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = clean_text(str(value))
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def deduplicate_dicts(values: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    result: list[dict[str, Any]] = []
    for value in values:
        identity = tuple(clean_text(str(value.get(key, ""))) for key in keys)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(value)
    return result


def order_values(values: list[str], preferred_order: list[str]) -> list[str]:
    ranking = {name: index for index, name in enumerate(preferred_order)}
    return sorted(values, key=lambda item: (ranking.get(item, len(preferred_order)), item))


def order_feature_logic(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranking = {name: index for index, name in enumerate(FEATURE_LOGIC_ORDER)}
    return sorted(values, key=lambda item: (ranking.get(str(item.get("feature", "")), len(FEATURE_LOGIC_ORDER)), str(item.get("feature", ""))))


def select_best_monetization_model(
    values: list[str],
    core_functions: list[str],
    site_types: list[str],
    important_keywords: list[str],
) -> str:
    candidates = deduplicate_strings(values)
    if candidates:
        return max(candidates, key=monetization_model_score)
    if "keyword_tool" in site_types and "scoring_system" in core_functions:
        return "CPC 기반 키워드 분석 SaaS"
    if "keyword_tool" in site_types and important_keywords:
        return "키워드 데이터 제공 서비스"
    if "content_site" in site_types:
        return "콘텐츠 기반 유입 서비스"
    return "일반 웹서비스"


def monetization_model_score(value: str) -> tuple[int, int]:
    lowered = value.lower()
    signal_score = sum(
        1
        for keyword in ("saas", "cpc", "키워드", "광고", "데이터")
        if keyword in lowered
    )
    return (signal_score, len(lowered))


def select_best_data_source(values: list[str], important_keywords: list[str]) -> str:
    candidates = deduplicate_strings(values)
    if candidates:
        return max(candidates, key=data_source_score)
    if {"CPC", "검색량"} & set(important_keywords):
        return "검색 데이터 추정"
    return "데이터 출처 불명"


def data_source_score(value: str) -> tuple[int, int]:
    lowered = value.lower()
    signal_score = sum(
        1
        for keyword in ("api", "네이버", "검색", "크롤링")
        if keyword in lowered
    )
    return (signal_score, len(lowered))


def order_ui_components(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranking = {item: index for index, item in enumerate(UI_COMPONENT_ORDER)}
    return sorted(values, key=lambda item: (ranking.get((str(item.get("type", "")), str(item.get("role", ""))), len(UI_COMPONENT_ORDER)), str(item.get("role", ""))))


def order_data_ports(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred_order = [
        ("input", "keyword seed"),
        ("textarea", "bulk keyword seed"),
        ("filter", "metric conditions"),
        ("table", "keyword metrics"),
        ("list", "related keyword suggestions"),
        ("article", "guide articles"),
    ]
    ranking = {item: index for index, item in enumerate(preferred_order)}
    return sorted(values, key=lambda item: (ranking.get((str(item.get("type", "")), str(item.get("role", ""))), len(preferred_order)), str(item.get("role", ""))))


def merge_feature_logic_values(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for value in values:
        feature = clean_text(str(value.get("feature", "")))
        logic = clean_text(str(value.get("logic", "")))
        if not feature or not logic:
            continue
        existing = merged.get(feature)
        if existing is None or feature_logic_score(logic) > feature_logic_score(str(existing.get("logic", ""))):
            merged[feature] = {"feature": feature, "logic": logic}
    return list(merged.values())


def feature_logic_score(logic: str) -> tuple[int, int]:
    normalized = logic.lower()
    signal_score = sum(
        1
        for keyword in ("경쟁도", "추천어", "조합", "검색량", "cpc", "사용법")
        if keyword in normalized
    )
    return (signal_score, len(normalized))


def order_business_logic(values: list[str]) -> list[str]:
    preferred_order = [
        "고CPC 키워드 우선 노출",
        "검색량 + 경쟁도 조합 분석",
        "CPC 기반 키워드 점수화",
        "고가 키워드 필터링",
        "연관 키워드 추천 및 확장",
    ]
    ranking = {name: index for index, name in enumerate(preferred_order)}
    return sorted(values, key=lambda item: (ranking.get(item, len(preferred_order)), item))


def component_haystack(tag: Tag, label: str) -> str:
    return " ".join(
        [
            tag.name,
            str(tag.get("type", "")),
            label,
            str(tag.get("name", "")),
            str(tag.get("id", "")),
            str(tag.get("placeholder", "")),
            str(tag.get("aria-label", "")),
            " ".join(str(item) for item in tag.get("class", [])),
        ]
    ).lower()


def tag_label(tag: Tag, soup: BeautifulSoup) -> str:
    if tag.get("id"):
        label = soup.find("label", attrs={"for": tag.get("id")})
        if label:
            return clean_text(label.get_text(" ", strip=True))
    parent_label = tag.find_parent("label")
    if parent_label:
        return clean_text(parent_label.get_text(" ", strip=True))
    for key in ("aria-label", "placeholder", "name", "id", "value", "title"):
        value = tag.get(key)
        if value:
            return clean_text(str(value))
    text = clean_text(tag.get_text(" ", strip=True))
    return text or tag.name


def selector_hint(tag: Tag) -> str:
    if tag.get("id"):
        return f"#{tag.get('id')}"
    classes = tag.get("class", [])
    if classes:
        return "." + ".".join(str(item) for item in classes[:3])
    return tag.name


def contextual_label(tag: Tag, soup: BeautifulSoup) -> str:
    for ancestor in [tag] + list(tag.parents):
        if not isinstance(ancestor, Tag):
            continue
        heading = ancestor.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        if heading:
            text = clean_text(heading.get_text(" ", strip=True))
            if text:
                return text
    previous_heading = tag.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
    if previous_heading:
        return clean_text(previous_heading.get_text(" ", strip=True))
    return tag_label(tag, soup)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def full_text(soup: BeautifulSoup) -> str:
    return clean_text(soup.get_text(" ", strip=True)).lower()
