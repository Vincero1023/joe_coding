from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

HTML_EXTENSIONS = {".html", ".htm"}


def load_html_file(file_path: str) -> tuple[Path, str, BeautifulSoup]:
    path = Path(file_path).expanduser().resolve()
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    return path, html, soup


def load_html_directory(directory_path: str) -> list[tuple[Path, str, BeautifulSoup]]:
    directory = Path(directory_path).expanduser().resolve()
    html_files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in HTML_EXTENSIONS
    )
    return [load_html_file(str(path)) for path in html_files]
