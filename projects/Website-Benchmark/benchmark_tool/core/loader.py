from __future__ import annotations

import re
from codecs import lookup
from pathlib import Path

from bs4 import BeautifulSoup

HTML_EXTENSIONS = {".html", ".htm"}
FALLBACK_ENCODINGS = ("utf-8", "utf-8-sig", "cp949", "euc-kr", "iso-8859-1", "latin-1")
BOM_ENCODINGS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)
META_CHARSET_RE = re.compile(br"<meta[^>]+charset=['\"]?\s*([A-Za-z0-9._-]+)", re.IGNORECASE)
META_CONTENT_RE = re.compile(br"<meta[^>]+content=['\"][^>]*charset=([A-Za-z0-9._-]+)", re.IGNORECASE)


def load_html_file(file_path: str) -> tuple[Path, str, BeautifulSoup]:
    path = Path(file_path).expanduser().resolve()
    html = decode_html_bytes(path.read_bytes())
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


def decode_html_bytes(data: bytes) -> str:
    encodings = build_encoding_candidates(data)
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode(encodings[0] if encodings else "utf-8", errors="replace")


def build_encoding_candidates(data: bytes) -> list[str]:
    candidates: list[str] = []
    for encoding in (detect_bom_encoding(data), sniff_meta_charset(data), *FALLBACK_ENCODINGS):
        normalized = normalize_encoding_name(encoding)
        if not normalized or normalized in candidates:
            continue
        candidates.append(normalized)
    return candidates or ["utf-8"]


def normalize_encoding_name(encoding: str | None) -> str | None:
    if not encoding:
        return None
    cleaned = encoding.strip().strip("\"'").lower()
    try:
        return lookup(cleaned).name
    except LookupError:
        return None


def detect_bom_encoding(data: bytes) -> str | None:
    for marker, encoding in BOM_ENCODINGS:
        if data.startswith(marker):
            return encoding
    return None


def sniff_meta_charset(data: bytes) -> str | None:
    head = data[:4096]
    for pattern in (META_CHARSET_RE, META_CONTENT_RE):
        match = pattern.search(head)
        if not match:
            continue
        return match.group(1).decode("ascii", errors="ignore")
    return None
