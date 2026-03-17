from __future__ import annotations

import re
from collections import Counter
from typing import Any

from bs4 import BeautifulSoup, Tag

BUTTON_INPUT_TYPES = {"button", "submit", "reset"}
API_ENDPOINT_REGEX = re.compile(r"/api/[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", re.IGNORECASE)
FETCH_CALL_REGEX = re.compile(r"fetch\s*\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
XHR_OPEN_REGEX = re.compile(r"\.open\s*\(\s*[\"'][A-Z]+[\"']\s*,\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
AXIOS_CALL_REGEX = re.compile(r"axios\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
AJAX_URL_REGEX = re.compile(r"url\s*:\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
FUNCTION_ORDER = [
    "navigation",
    "search",
    "login",
    "registration",
    "filtering",
    "data_retrieval",
    "form_submission",
    "data_entry",
    "tabular_data_view",
    "listing_view",
    "file_upload",
    "contact_request",
]


def analyze_document(source_path: str, html: str, soup: BeautifulSoup) -> dict[str, Any]:
    inputs = extract_input_components(soup)
    buttons = extract_button_components(soup)
    forms = extract_form_components(soup)
    tables = extract_table_components(soup)
    lists = extract_list_components(soup)
    api_patterns = extract_api_patterns(soup, html)

    ui_components = inputs + buttons + forms + tables + lists
    data_inputs = build_data_inputs(inputs)
    data_outputs = build_data_outputs(tables, lists)
    core_functions = infer_core_functions(soup, inputs, buttons, forms, tables, lists, api_patterns)
    site_type = infer_site_type(soup, core_functions, forms, tables, lists, api_patterns)
    user_flow = infer_user_flow(core_functions, data_inputs, data_outputs, forms, buttons, api_patterns)
    feature_logic = infer_feature_logic(core_functions, inputs, buttons, forms, tables, lists, api_patterns, data_inputs, data_outputs)

    return {
        "site_type": site_type,
        "core_functions": core_functions,
        "ui_components": ui_components,
        "user_flow": user_flow,
        "data_inputs": data_inputs,
        "data_outputs": data_outputs,
        "api_patterns": api_patterns,
        "feature_logic": feature_logic,
    }


def merge_site_analyses(document_analyses: list[dict[str, Any]], content_exports: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    source_files = [str(item["source_file"]) for item in document_analyses]
    page_types = [str(item["analysis"]["site_type"]) for item in document_analyses]
    core_counter: Counter[str] = Counter()

    ui_groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    input_groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    output_groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    api_groups: dict[tuple[str, str], dict[str, Any]] = {}
    flow_groups: dict[str, dict[str, Any]] = {}
    feature_groups: dict[str, dict[str, Any]] = {}

    for document in document_analyses:
        source_file = str(document["source_file"])
        analysis = document["analysis"]

        for function_name in analysis["core_functions"]:
            core_counter[str(function_name)] += 1

        merge_ui_components(ui_groups, analysis["ui_components"], source_file)
        merge_data_inputs(input_groups, analysis["data_inputs"], source_file)
        merge_data_outputs(output_groups, analysis["data_outputs"], source_file)
        merge_api_patterns(api_groups, analysis["api_patterns"], source_file)
        merge_user_flows(flow_groups, analysis["user_flow"], source_file)
        merge_feature_logic(feature_groups, analysis["feature_logic"], source_file)

    core_functions = [name for name in FUNCTION_ORDER if core_counter[name] > 0]
    if not core_functions:
        core_functions = [name for name, _count in core_counter.most_common()]

    aggregated_api_patterns = sort_grouped_records(api_groups.values(), "count")
    content_exports = content_exports or []

    return {
        "pages_analyzed": len(document_analyses),
        "source_files": source_files,
        "site_type": infer_integrated_site_type(core_functions, page_types, aggregated_api_patterns, content_exports),
        "core_functions": core_functions,
        "ui_components": sort_grouped_records(ui_groups.values(), "count"),
        "user_flow": sort_grouped_records(flow_groups.values(), "count"),
        "data_inputs": sort_grouped_records(input_groups.values(), "count"),
        "data_outputs": sort_grouped_records(output_groups.values(), "count"),
        "api_patterns": aggregated_api_patterns,
        "feature_logic": sort_grouped_records(feature_groups.values(), "count"),
        "content_exports": content_exports,
    }


def extract_input_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tag in soup.find_all(["input", "textarea", "select"]):
        label = tag_label(tag, soup)
        role = classify_input_role(tag, label)
        results.append(
            {
                "component_type": tag.name,
                "category": "data_input",
                "role": role,
                "label": label,
                "name": tag.get("name", ""),
                "id": tag.get("id", ""),
                "input_type": tag.get("type", "") if tag.name == "input" else tag.name,
                "selector_hint": selector_hint(tag),
                "form_action": parent_form_action(tag),
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
                "category": "action",
                "role": classify_button_role(tag, label),
                "label": label,
                "id": tag.get("id", ""),
                "button_type": tag.get("type", tag.name),
                "selector_hint": selector_hint(tag),
                "form_action": parent_form_action(tag),
            }
        )
    return results


def extract_form_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for form in soup.find_all("form"):
        child_inputs = [
            classify_input_role(tag, tag_label(tag, soup))
            for tag in form.find_all(["input", "textarea", "select"])
        ]
        submit_labels = [
            tag_label(tag, soup)
            for tag in form.find_all(["button", "input"])
            if tag.name == "button" or tag.get("type", "").lower() in BUTTON_INPUT_TYPES
        ]
        results.append(
            {
                "component_type": "form",
                "category": "workflow_container",
                "role": infer_form_role(form, child_inputs, submit_labels),
                "label": contextual_label(form, soup),
                "method": form.get("method", "get").upper(),
                "action": form.get("action", ""),
                "field_count": len(form.find_all(["input", "textarea", "select"])),
                "submit_actions": submit_labels,
                "selector_hint": selector_hint(form),
            }
        )
    return results


def extract_table_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        headers = [clean_text(cell.get_text(" ", strip=True)) for cell in table.find_all("th")]
        rows = table.find_all("tr")
        results.append(
            {
                "component_type": "table",
                "category": "data_output",
                "role": "tabular_data",
                "label": contextual_label(table, soup),
                "headers": [header for header in headers if header],
                "row_count": max(len(rows) - 1, 0) if headers else len(rows),
                "selector_hint": selector_hint(table),
            }
        )
    return results


def extract_list_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tag in soup.find_all(["ul", "ol", "dl"]):
        if tag.name == "dl":
            item_texts = [clean_text(item.get_text(" ", strip=True)) for item in tag.find_all(["dt", "dd"], recursive=False)]
        else:
            item_texts = [clean_text(item.get_text(" ", strip=True)) for item in tag.find_all("li", recursive=False)]
        item_texts = [item for item in item_texts if item]
        results.append(
            {
                "component_type": "list",
                "category": "data_output" if tag.find_parent("nav") is None else "navigation",
                "role": "navigation_list" if tag.find_parent("nav") else "listing_data",
                "label": contextual_label(tag, soup),
                "list_type": tag.name,
                "item_count": len(item_texts),
                "items_preview": item_texts[:3],
                "selector_hint": selector_hint(tag),
            }
        )
    return results


def build_data_inputs(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    results: list[dict[str, Any]] = []
    for item in inputs:
        key = (str(item["name"]), str(item["label"]), str(item["selector_hint"]))
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "name": item["name"] or item["id"] or item["label"],
                "label": item["label"],
                "type": item["input_type"],
                "role": item["role"],
                "source": "form_control",
            }
        )
    return results


def build_data_outputs(tables: list[dict[str, Any]], lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for table in tables:
        results.append(
            {
                "name": table["label"] or "table_output",
                "type": "table",
                "role": table["role"],
                "fields": table["headers"],
                "volume_hint": table["row_count"],
            }
        )
    for listing in lists:
        if listing["role"] == "navigation_list":
            continue
        results.append(
            {
                "name": listing["label"] or "list_output",
                "type": "list",
                "role": listing["role"],
                "fields": [],
                "volume_hint": listing["item_count"],
            }
        )
    return results


def infer_core_functions(
    soup: BeautifulSoup,
    inputs: list[dict[str, Any]],
    buttons: list[dict[str, Any]],
    forms: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    lists: list[dict[str, Any]],
    api_patterns: list[dict[str, Any]],
) -> list[str]:
    text = full_text(soup)
    roles = {item["role"] for item in inputs + buttons + forms}
    has_nav = len(soup.find_all("a")) >= 2 or bool(soup.find("nav"))
    has_results = bool(tables) or any(item["role"] != "navigation_list" and item["item_count"] >= 2 for item in lists)
    has_api = bool(api_patterns)
    ordered_features = [
        ("navigation", has_nav),
        ("search", "search_field" in roles or "search_form" in roles or "search_action" in roles or "search" in text),
        ("login", "login_form" in roles or "login_action" in roles or ("password_field" in roles and any(role in roles for role in {"email_field", "username_field"}))),
        ("registration", "registration_form" in roles or "registration_action" in roles or "create account" in text or "sign up" in text),
        ("filtering", "filter_control" in roles or "filter_form" in roles or "filter_action" in roles),
        ("data_retrieval", has_results or has_api or "fetch" in text or "xhr" in text),
        ("form_submission", bool(forms)),
        ("data_entry", bool(inputs)),
        ("tabular_data_view", bool(tables)),
        ("listing_view", any(item["role"] != "navigation_list" and item["item_count"] >= 2 for item in lists)),
        ("file_upload", "file_upload" in roles),
        ("contact_request", "contact_form" in roles or "contact_action" in roles),
    ]
    return [name for name, matched in ordered_features if matched]


def infer_site_type(
    soup: BeautifulSoup,
    core_functions: list[str],
    forms: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    lists: list[dict[str, Any]],
    api_patterns: list[dict[str, Any]],
) -> str:
    text = full_text(soup)
    feature_set = set(core_functions)
    if {"login", "data_retrieval"}.issubset(feature_set) and api_patterns:
        return "web_application"
    if "login" in feature_set or "registration" in feature_set:
        return "authentication_portal"
    if "search" in feature_set or "filtering" in feature_set or tables or api_patterns:
        return "data_portal"
    if forms and "form_submission" in feature_set:
        return "workflow_form_site"
    if "guide" in text or "manual" in text or ("listing_view" in feature_set and not forms):
        return "content_site"
    if "pricing" in text or "plan" in text or "checkout" in text:
        return "commerce_or_marketing_site"
    return "general_website"


def infer_user_flow(
    core_functions: list[str],
    data_inputs: list[dict[str, Any]],
    data_outputs: list[dict[str, Any]],
    forms: list[dict[str, Any]],
    buttons: list[dict[str, Any]],
    api_patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    feature_set = set(core_functions)
    outputs = [item["name"] for item in data_outputs] or ["page state or confirmation"]
    button_labels = [button["label"] for button in buttons if button["label"]]
    api_targets = [item["pattern"] for item in api_patterns[:3]]
    flows: list[dict[str, Any]] = []

    def inputs_by_role(role: str) -> list[str]:
        return [item["label"] or item["name"] for item in data_inputs if item["role"] == role]

    if "search" in feature_set:
        flows.append(
            {
                "name": "search_flow",
                "input": inputs_by_role("search_field") or [item["label"] for item in data_inputs[:2]],
                "process": "User enters search criteria and triggers a query through form submission or a client-side request.",
                "output": outputs,
            }
        )
    if "filtering" in feature_set:
        flows.append(
            {
                "name": "filter_flow",
                "input": [item["label"] for item in data_inputs if item["role"] == "filter_control"],
                "process": "Selected filter values narrow or reorder the currently displayed dataset.",
                "output": outputs,
            }
        )
    if "login" in feature_set:
        flows.append(
            {
                "name": "login_flow",
                "input": inputs_by_role("email_field") + inputs_by_role("username_field") + inputs_by_role("password_field"),
                "process": "Credential fields are submitted for authentication, usually through a form action or API endpoint.",
                "output": ["authenticated session or protected content"],
            }
        )
    if "registration" in feature_set:
        flows.append(
            {
                "name": "registration_flow",
                "input": [item["label"] for item in data_inputs if item["role"] in {"email_field", "username_field", "password_field", "text_entry"}],
                "process": "Account details are collected and posted to create a new user or workspace.",
                "output": ["new account record or registration confirmation"],
            }
        )
    if "form_submission" in feature_set and "login" not in feature_set:
        flows.append(
            {
                "name": "submission_flow",
                "input": [item["label"] for item in data_inputs[:4]],
                "process": f"Form data is submitted using {forms[0]['method'] if forms else 'form'} logic and optional API integration.",
                "output": ["confirmation message, saved record, or refreshed page"],
            }
        )
    if "data_retrieval" in feature_set and not any(flow["name"] == "search_flow" for flow in flows):
        flows.append(
            {
                "name": "data_retrieval_flow",
                "input": button_labels[:2] or ["page load or navigation event"],
                "process": "The page requests structured data from server-side or client-side endpoints.",
                "output": outputs + api_targets[:1],
            }
        )
    return flows


def infer_feature_logic(
    core_functions: list[str],
    inputs: list[dict[str, Any]],
    buttons: list[dict[str, Any]],
    forms: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    lists: list[dict[str, Any]],
    api_patterns: list[dict[str, Any]],
    data_inputs: list[dict[str, Any]],
    data_outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    feature_set = set(core_functions)
    output_labels = [item["name"] for item in data_outputs]
    feature_logic: list[dict[str, Any]] = []

    if "search" in feature_set:
        feature_logic.append(
            {
                "feature": "search",
                "evidence": collect_evidence(inputs, buttons, forms, api_patterns, {"search_field", "search_action", "search_form"}, {"search", "query", "find"}),
                "logic": f"Search inputs accept criteria, then the page returns matching results through {', '.join(output_labels) or 'result views'}.",
            }
        )
    if "login" in feature_set:
        feature_logic.append(
            {
                "feature": "login",
                "evidence": collect_evidence(inputs, buttons, forms, api_patterns, {"password_field", "login_action", "login_form", "email_field", "username_field"}, {"login", "auth", "session", "sign"}),
                "logic": "Credential-like inputs and submit controls indicate an authentication step before protected content is shown.",
            }
        )
    if "registration" in feature_set:
        feature_logic.append(
            {
                "feature": "registration",
                "evidence": collect_evidence(inputs, buttons, forms, api_patterns, {"registration_action", "registration_form", "email_field", "password_field"}, {"register", "signup", "account", "join"}),
                "logic": "User profile or account fields suggest a create-account workflow with backend persistence.",
            }
        )
    if "filtering" in feature_set:
        feature_logic.append(
            {
                "feature": "filtering",
                "evidence": collect_evidence(inputs, buttons, forms, api_patterns, {"filter_control", "filter_action", "filter_form"}, {"filter", "sort", "status", "type"}),
                "logic": "Selector-style controls and apply actions indicate filtering or narrowing of visible data.",
            }
        )
    if "data_retrieval" in feature_set:
        retrieval_evidence = [table["label"] for table in tables] + [listing["label"] for listing in lists if listing["role"] != "navigation_list"]
        retrieval_evidence += [item["pattern"] for item in api_patterns[:3]]
        feature_logic.append(
            {
                "feature": "data_retrieval",
                "evidence": ordered_unique([item for item in retrieval_evidence if item]),
                "logic": "Tables, lists, or network calls indicate that the page retrieves and renders structured records or content collections.",
            }
        )
    if "form_submission" in feature_set:
        feature_logic.append(
            {
                "feature": "form_submission",
                "evidence": ordered_unique([form["action"] or form["label"] for form in forms] + [item["label"] for item in data_inputs[:3]]),
                "logic": "Form controls are grouped into submit-capable workflows that send user-provided data for processing.",
            }
        )
    return feature_logic


def extract_api_patterns(soup: BeautifulSoup, html: str) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for form in soup.find_all("form"):
        action = str(form.get("action", ""))
        if action and ("/api/" in action or action.startswith("/")):
            patterns.append({"type": "form_action", "pattern": action, "source": "form"})
    for tag in soup.find_all(True):
        for attr_name, attr_value in tag.attrs.items():
            values = attr_value if isinstance(attr_value, list) else [attr_value]
            for value in values:
                if isinstance(value, str) and "/api/" in value:
                    patterns.append({"type": "endpoint", "pattern": value, "source": f"{tag.name}.{attr_name}"})

    script_texts = [script.string or script.get_text(" ", strip=False) for script in soup.find_all("script")]
    raw_script = "\n".join(text for text in script_texts if text)
    raw_text = "\n".join([html, raw_script])
    for endpoint in API_ENDPOINT_REGEX.findall(raw_text):
        patterns.append({"type": "endpoint", "pattern": endpoint, "source": "html_or_script"})
    for endpoint in FETCH_CALL_REGEX.findall(raw_text):
        patterns.append({"type": "fetch", "pattern": endpoint, "source": "script"})
    for endpoint in XHR_OPEN_REGEX.findall(raw_text):
        patterns.append({"type": "xhr", "pattern": endpoint, "source": "script"})
    for method, endpoint in AXIOS_CALL_REGEX.findall(raw_text):
        patterns.append({"type": f"axios_{method.lower()}", "pattern": endpoint, "source": "script"})
    for endpoint in AJAX_URL_REGEX.findall(raw_text):
        patterns.append({"type": "ajax", "pattern": endpoint, "source": "script"})
    if "XMLHttpRequest" in raw_text:
        patterns.append({"type": "xhr_object", "pattern": "XMLHttpRequest", "source": "script"})
    if "fetch(" in raw_text:
        patterns.append({"type": "fetch_call", "pattern": "fetch", "source": "script"})

    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in patterns:
        key = (str(item["type"]), str(item["pattern"]), str(item["source"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def merge_ui_components(groups: dict[tuple[str, str, str, str], dict[str, Any]], components: list[dict[str, Any]], source_file: str) -> None:
    for component in components:
        identity = normalize_identity(component.get("label") or component.get("selector_hint") or component.get("component_type"))
        key = (str(component.get("component_type", "")), str(component.get("category", "")), str(component.get("role", "")), identity)
        group = groups.setdefault(
            key,
            {
                "component_type": component.get("component_type", ""),
                "category": component.get("category", ""),
                "role": component.get("role", ""),
                "count": 0,
                "examples": [],
                "source_files": [],
                "details": [],
            },
        )
        group["count"] += 1
        group["examples"] = ordered_unique(group["examples"] + [str(component.get("label", ""))])
        group["source_files"] = ordered_unique(group["source_files"] + [source_file])
        details = []
        for key_name in ("input_type", "button_type", "method", "action"):
            value = component.get(key_name)
            if value:
                details.append(str(value))
        if component.get("headers"):
            details.extend(str(item) for item in component["headers"][:3])
        if component.get("items_preview"):
            details.extend(str(item) for item in component["items_preview"][:2])
        group["details"] = ordered_unique(group["details"] + details)


def merge_data_inputs(groups: dict[tuple[str, str, str], dict[str, Any]], data_inputs: list[dict[str, Any]], source_file: str) -> None:
    for item in data_inputs:
        key = (str(item.get("type", "")), str(item.get("role", "")), normalize_identity(item.get("label") or item.get("name")))
        group = groups.setdefault(
            key,
            {
                "name": item.get("name", ""),
                "label": item.get("label", ""),
                "type": item.get("type", ""),
                "role": item.get("role", ""),
                "count": 0,
                "source_files": [],
            },
        )
        group["count"] += 1
        group["source_files"] = ordered_unique(group["source_files"] + [source_file])


def merge_data_outputs(groups: dict[tuple[str, str, str], dict[str, Any]], data_outputs: list[dict[str, Any]], source_file: str) -> None:
    for item in data_outputs:
        key = (str(item.get("type", "")), str(item.get("role", "")), normalize_identity(item.get("name")))
        group = groups.setdefault(
            key,
            {
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "role": item.get("role", ""),
                "fields": list(item.get("fields", [])),
                "count": 0,
                "source_files": [],
                "max_volume_hint": 0,
            },
        )
        group["count"] += 1
        group["source_files"] = ordered_unique(group["source_files"] + [source_file])
        group["fields"] = ordered_unique(group["fields"] + list(item.get("fields", [])))
        group["max_volume_hint"] = max(int(group["max_volume_hint"]), int(item.get("volume_hint", 0) or 0))


def merge_api_patterns(groups: dict[tuple[str, str], dict[str, Any]], api_patterns: list[dict[str, Any]], source_file: str) -> None:
    for item in api_patterns:
        key = (str(item.get("type", "")), str(item.get("pattern", "")))
        group = groups.setdefault(
            key,
            {
                "type": item.get("type", ""),
                "pattern": item.get("pattern", ""),
                "count": 0,
                "source_files": [],
                "sources": [],
            },
        )
        group["count"] += 1
        group["source_files"] = ordered_unique(group["source_files"] + [source_file])
        group["sources"] = ordered_unique(group["sources"] + [str(item.get("source", ""))])


def merge_user_flows(groups: dict[str, dict[str, Any]], flows: list[dict[str, Any]], source_file: str) -> None:
    for item in flows:
        key = str(item.get("name", "flow"))
        group = groups.setdefault(
            key,
            {
                "name": item.get("name", ""),
                "input": [],
                "process": item.get("process", ""),
                "output": [],
                "count": 0,
                "source_files": [],
            },
        )
        group["count"] += 1
        group["input"] = ordered_unique(group["input"] + list(item.get("input", [])))
        group["output"] = ordered_unique(group["output"] + list(item.get("output", [])))
        group["source_files"] = ordered_unique(group["source_files"] + [source_file])


def merge_feature_logic(groups: dict[str, dict[str, Any]], feature_logic: list[dict[str, Any]], source_file: str) -> None:
    for item in feature_logic:
        key = str(item.get("feature", "feature"))
        group = groups.setdefault(
            key,
            {
                "feature": item.get("feature", ""),
                "evidence": [],
                "logic": item.get("logic", ""),
                "count": 0,
                "source_files": [],
            },
        )
        group["count"] += 1
        group["evidence"] = ordered_unique(group["evidence"] + list(item.get("evidence", [])))
        group["source_files"] = ordered_unique(group["source_files"] + [source_file])


def infer_integrated_site_type(core_functions: list[str], page_types: list[str], api_patterns: list[dict[str, Any]], content_exports: list[dict[str, Any]]) -> str:
    feature_set = set(core_functions)
    page_type_counter = Counter(page_types)
    if {"login", "data_retrieval"}.issubset(feature_set):
        return "web_application"
    if {"search", "filtering", "data_retrieval"} & feature_set and api_patterns:
        return "data_portal"
    if content_exports and len(content_exports) >= max(2, len(page_types) // 2) and "login" not in feature_set:
        return "content_site"
    return page_type_counter.most_common(1)[0][0] if page_type_counter else "general_website"


def collect_evidence(
    inputs: list[dict[str, Any]],
    buttons: list[dict[str, Any]],
    forms: list[dict[str, Any]],
    api_patterns: list[dict[str, Any]],
    relevant_roles: set[str],
    api_keywords: set[str],
) -> list[str]:
    evidence = [str(item["label"]) for item in inputs if item["role"] in relevant_roles]
    evidence += [str(item["label"]) for item in buttons if item["role"] in relevant_roles]
    evidence += [str(item["label"] or item["action"]) for item in forms if item["role"] in relevant_roles]
    for item in api_patterns:
        pattern = str(item["pattern"]).lower()
        if any(keyword in pattern for keyword in api_keywords):
            evidence.append(str(item["pattern"]))
    return ordered_unique(evidence)


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


def parent_form_action(tag: Tag) -> str:
    form = tag.find_parent("form")
    return str(form.get("action", "")) if form else ""


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


def classify_input_role(tag: Tag, label: str) -> str:
    input_type = str(tag.get("type", tag.name)).lower()
    haystack = " ".join([tag.name, input_type, label, str(tag.get("name", "")), str(tag.get("id", "")), str(tag.get("placeholder", "")), " ".join(str(item) for item in tag.get("class", []))]).lower()
    if input_type == "password" or "password" in haystack:
        return "password_field"
    if input_type == "search" or any(keyword in haystack for keyword in ["search", "keyword", "query", "find"]):
        return "search_field"
    if input_type == "email" or "email" in haystack:
        return "email_field"
    if any(keyword in haystack for keyword in ["username", "user name", "login id", "userid", "account id"]):
        return "username_field"
    if input_type in {"checkbox", "radio"} or tag.name == "select" or any(keyword in haystack for keyword in ["filter", "sort", "category", "status", "date", "type"]):
        return "filter_control"
    if input_type == "file":
        return "file_upload"
    if tag.name == "textarea":
        return "long_text"
    return "text_entry"


def classify_button_role(tag: Tag, label: str) -> str:
    haystack = " ".join([label, str(tag.get("name", "")), str(tag.get("id", "")), str(tag.get("type", "")), " ".join(str(item) for item in tag.get("class", []))]).lower()
    if any(keyword in haystack for keyword in ["search", "find", "lookup"]):
        return "search_action"
    if any(keyword in haystack for keyword in ["filter", "apply", "sort", "refine"]):
        return "filter_action"
    if any(keyword in haystack for keyword in ["login", "log in", "sign in"]):
        return "login_action"
    if any(keyword in haystack for keyword in ["sign up", "register", "create account", "join"]):
        return "registration_action"
    if any(keyword in haystack for keyword in ["contact", "message", "request demo", "send"]):
        return "contact_action"
    if any(keyword in haystack for keyword in ["submit", "save", "create", "update", "continue"]):
        return "submit_action"
    return "generic_action"


def infer_form_role(form: Tag, child_input_roles: list[str], submit_labels: list[str]) -> str:
    joined_submit = " ".join(submit_labels).lower()
    action = str(form.get("action", "")).lower()
    if "password_field" in child_input_roles and any(role in child_input_roles for role in {"email_field", "username_field"}):
        if any(keyword in joined_submit or keyword in action for keyword in ["sign up", "register", "create", "join"]):
            return "registration_form"
        return "login_form"
    if "search_field" in child_input_roles:
        return "search_form"
    if "filter_control" in child_input_roles and len(child_input_roles) <= 4:
        return "filter_form"
    if "file_upload" in child_input_roles:
        return "upload_form"
    if any(keyword in joined_submit or keyword in action for keyword in ["contact", "message", "support", "demo"]):
        return "contact_form"
    return "data_entry_form"


def normalize_identity(value: Any) -> str:
    return clean_text(str(value or "")).lower()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def full_text(soup: BeautifulSoup) -> str:
    return clean_text(soup.get_text(" ", strip=True)).lower()


def ordered_unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        cleaned = clean_text(str(value))
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        results.append(cleaned)
    return results


def sort_grouped_records(records: Any, sort_key: str) -> list[dict[str, Any]]:
    return sorted(list(records), key=lambda item: (-int(item.get(sort_key, 0)), str(item.get("role", item.get("feature", item.get("name", ""))))))
