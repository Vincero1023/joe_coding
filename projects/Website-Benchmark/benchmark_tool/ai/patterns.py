from __future__ import annotations

import re
from collections import Counter
from typing import Any

from bs4 import BeautifulSoup, Tag

API_REGEX = re.compile(r"([\"'\(=:\s]|^)(/api/[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+)")


def tag_label(tag: Tag) -> str:
    text = " ".join(tag.stripped_strings)
    if text:
        return text
    for key in ("aria-label", "placeholder", "name", "id", "value", "type"):
        value = tag.get(key)
        if value:
            return str(value)
    return tag.name


def css_hint(tag: Tag) -> str:
    if tag.get("id"):
        return f"#{tag['id']}"
    classes = tag.get("class", [])
    if classes:
        return "." + ".".join(classes[:3])
    return tag.name


def extract_input_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tag in soup.find_all(["input", "textarea", "select"]):
        results.append(
            {
                "tag": tag.name,
                "type": tag.get("type", ""),
                "name": tag.get("name", ""),
                "id": tag.get("id", ""),
                "placeholder": tag.get("placeholder", ""),
                "label": tag_label(tag),
                "selector_hint": css_hint(tag),
            }
        )
    return results


def extract_button_components(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tag in soup.find_all(["button", "input"]):
        if tag.name == "input" and tag.get("type", "").lower() not in {"button", "submit", "reset"}:
            continue
        results.append(
            {
                "tag": tag.name,
                "type": tag.get("type", ""),
                "text": tag_label(tag),
                "id": tag.get("id", ""),
                "class_names": tag.get("class", []),
                "selector_hint": css_hint(tag),
            }
        )
    return results


def extract_api_patterns(soup: BeautifulSoup, html: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    for tag in soup.find_all(True):
        for attr_name, attr_value in tag.attrs.items():
            values = attr_value if isinstance(attr_value, list) else [attr_value]
            for value in values:
                if not isinstance(value, str) or "/api/" not in value:
                    continue
                matches.append(
                    {
                        "source": "attribute",
                        "tag": tag.name,
                        "attribute": attr_name,
                        "pattern": value,
                    }
                )

    for script in soup.find_all("script"):
        content = script.string or script.get_text(" ", strip=False)
        if not content or "/api/" not in content:
            continue
        for match in API_REGEX.finditer(content):
            matches.append(
                {
                    "source": "script",
                    "tag": "script",
                    "attribute": "text",
                    "pattern": match.group(2),
                }
            )

    if "/api/" in html and not matches:
        for match in API_REGEX.finditer(html):
            matches.append(
                {
                    "source": "html",
                    "tag": "document",
                    "attribute": "raw_html",
                    "pattern": match.group(2),
                }
            )

    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in matches:
        key = (item["source"], item["tag"], item["attribute"], item["pattern"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def component_summary(inputs: list[dict[str, Any]], buttons: list[dict[str, Any]]) -> dict[str, Any]:
    input_types = Counter(item["type"] or item["tag"] for item in inputs)
    button_types = Counter(item["type"] or item["tag"] for item in buttons)
    return {
        "input_count": len(inputs),
        "button_count": len(buttons),
        "input_types": dict(input_types),
        "button_types": dict(button_types),
    }
