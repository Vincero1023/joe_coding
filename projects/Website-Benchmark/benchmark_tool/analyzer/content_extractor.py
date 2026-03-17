from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

CONTENT_KEYWORDS = [
    "\uac00\uc774\ub4dc",
    "\ubc29\ubc95",
    "\uc0ac\uc6a9",
    "\uc0ac\uc6a9\ubc95",
    "\uc124\uba85",
    "\ub3c4\uc6c0\ub9d0",
    "\uba54\ub274\uc5bc",
    "\ub9e4\ub274\uc5bc",
    "guide",
    "manual",
    "how to",
    "usage",
    "help",
    "description",
]
MIN_TEXT_LENGTH = 180
MIN_TEXT_LENGTH_WITHOUT_KEYWORD = 260


def extract_content_candidates(source_path: str, html: str, soup: BeautifulSoup) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    selected_tags: list[Tag] = []

    for tag in soup.find_all(["article", "section", "div"]):
        if any(parent in selected_tags for parent in tag.parents if isinstance(parent, Tag)):
            continue
        candidate = build_content_candidate(tag, source_path, soup)
        if not candidate:
            continue
        candidates.append(candidate)
        selected_tags.append(tag)
    return candidates


def export_content_candidates(candidates: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    exports: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        html_name = f"guide_{index}.html"
        markdown_name = f"guide_{index}.md"
        html_path = output_dir / html_name
        markdown_path = output_dir / markdown_name

        html_path.write_text(candidate["html_snapshot"], encoding="utf-8")
        markdown_path.write_text(candidate["markdown"], encoding="utf-8")

        exports.append(
            {
                "index": index,
                "title": candidate["title"],
                "source_file": candidate["source_file"],
                "html_file": html_name,
                "markdown_file": markdown_name,
                "text_length": candidate["text_length"],
                "keyword_hits": candidate["keyword_hits"],
            }
        )
    return exports


def build_content_candidate(tag: Tag, source_path: str, soup: BeautifulSoup) -> dict[str, Any] | None:
    if tag.find_parent("nav") or tag.find_parent("footer"):
        return None

    text = clean_text(tag.get_text(" ", strip=True))
    if len(text) < MIN_TEXT_LENGTH:
        return None

    heading = tag.find(["h1", "h2", "h3"])
    heading_text = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    haystack = f"{heading_text} {text}".lower()
    keyword_hits = [keyword for keyword in CONTENT_KEYWORDS if keyword.lower() in haystack]

    if not heading_text and not keyword_hits:
        return None
    if not keyword_hits and len(text) < MIN_TEXT_LENGTH_WITHOUT_KEYWORD:
        return None
    if len(tag.find_all(["input", "button", "form"])) > 8 and len(text) < 400:
        return None

    title = heading_text or contextual_title(tag, soup) or Path(source_path).stem
    return {
        "source_file": Path(source_path).name,
        "title": title,
        "text_length": len(text),
        "keyword_hits": keyword_hits,
        "html_snapshot": build_html_snapshot(tag, title, source_path),
        "markdown": build_markdown(tag, title, source_path, keyword_hits),
    }


def build_html_snapshot(tag: Tag, title: str, source_path: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "  <head>\n"
        "    <meta charset=\"utf-8\" />\n"
        f"    <title>{escape(title)}</title>\n"
        "  </head>\n"
        "  <body>\n"
        f"    <!-- source: {escape(Path(source_path).name)} -->\n"
        f"{indent_html(str(tag), 4)}\n"
        "  </body>\n"
        "</html>\n"
    )


def build_markdown(tag: Tag, title: str, source_path: str, keyword_hits: list[str]) -> str:
    lines = [f"# {title}", "", f"- Source: `{Path(source_path).name}`"]
    if keyword_hits:
        lines.append(f"- Keywords: {', '.join(keyword_hits)}")
    lines.append("")

    seen: set[str] = set()
    for element in tag.find_all(["h1", "h2", "h3", "p", "li", "dt", "dd"], recursive=True):
        text = clean_text(element.get_text(" ", strip=True))
        if not text or text in seen:
            continue
        seen.add(text)
        if element.name in {"h1", "h2", "h3"}:
            level = int(element.name[1])
            lines.append(f"{'#' * level} {text}")
            lines.append("")
        elif element.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
            lines.append("")

    if len(lines) <= 4:
        lines.extend([clean_text(tag.get_text("\n", strip=True)), ""])
    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def contextual_title(tag: Tag, soup: BeautifulSoup) -> str:
    previous_heading = tag.find_previous(["h1", "h2", "h3"])
    if previous_heading:
        return clean_text(previous_heading.get_text(" ", strip=True))
    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True))
    return ""


def clean_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def indent_html(value: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else line for line in value.splitlines())

