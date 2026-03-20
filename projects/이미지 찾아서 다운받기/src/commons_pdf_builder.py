from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "commons-pdf-builder/0.1 (local personal document generation script)"
DEFAULT_TIMEOUT = 30
IMAGE_HEIGHT = 82
MIN_REQUEST_INTERVAL = 0.8
MAX_RETRIES = 3

SECTION_RE = re.compile(r"^🔥\s*(\d+)\.\s*(.+)$")
THEME_RE = re.compile(r"^👉\s*핵심:\s*(.+)$")
NOTE_RE = re.compile(r"^(?:👉\s*)?(.*)$")
HANGUL_RE = re.compile(r"[가-힣]+")
NON_SEARCH_RE = re.compile(r"[^\w\s'().,&:-]+")
MULTISPACE_RE = re.compile(r"\s+")
PAREN_RE = re.compile(r"\((.*?)\)")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ArtworkItem:
    title_line: str
    description: str
    search_title: str
    search_artist: str

    @property
    def display_title(self) -> str:
        if self.search_artist:
            return f"{self.search_title} - {self.search_artist}"
        return self.search_title


@dataclass(frozen=True)
class PageGroup:
    section_number: int
    page_title: str
    theme: str
    items: list[ArtworkItem]


@dataclass(frozen=True)
class ResolvedArtwork:
    title: str
    image_path: Path
    description_url: str


def normalize_spaces(value: str) -> str:
    return MULTISPACE_RE.sub(" ", value).strip()


def strip_notes(value: str) -> str:
    value = HANGUL_RE.sub(" ", value)
    value = NON_SEARCH_RE.sub(" ", value)
    return normalize_spaces(value)


def base_artist(value: str) -> str:
    cleaned = value.split("(")[0]
    cleaned = HANGUL_RE.sub(" ", cleaned)
    return normalize_spaces(cleaned)


def parse_title_line(line: str) -> tuple[str, str]:
    parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
    if len(parts) == 2:
        return normalize_spaces(parts[0]), normalize_spaces(parts[1])
    return normalize_spaces(line), ""


def parse_note_line(line: str) -> str:
    match = NOTE_RE.match(line.strip())
    if not match:
        return normalize_spaces(line)
    value = match.group(1).strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1].strip()
    return normalize_spaces(value)


def parse_source_text(text: str) -> list[PageGroup]:
    lines = [line.rstrip() for line in text.splitlines()]
    groups: list[PageGroup] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        section_match = SECTION_RE.match(line)
        if not section_match:
            raise ManifestError(f"섹션 제목을 찾지 못했습니다: {line}")

        section_number = int(section_match.group(1))
        page_title = normalize_spaces(section_match.group(2))
        index += 1

        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            raise ManifestError(f"{page_title} 섹션의 핵심 문구가 없습니다.")

        theme_match = THEME_RE.match(lines[index].strip())
        if not theme_match:
            raise ManifestError(f"{page_title} 섹션의 핵심 문구 형식이 잘못되었습니다.")
        theme = normalize_spaces(theme_match.group(1))
        index += 1

        items: list[ArtworkItem] = []
        while index < len(lines):
            current = lines[index].strip()
            if not current:
                index += 1
                continue
            if SECTION_RE.match(current):
                break
            if current.startswith("👉 핵심:"):
                raise ManifestError(f"{page_title} 섹션에서 작품 목록 대신 핵심 문구가 다시 나왔습니다.")

            title_line = normalize_spaces(current)
            index += 1

            while index < len(lines) and not lines[index].strip():
                index += 1
            if index >= len(lines):
                raise ManifestError(f"{title_line} 작품 설명이 없습니다.")

            description_line = lines[index].strip()
            if SECTION_RE.match(description_line):
                raise ManifestError(f"{title_line} 작품 설명이 없습니다.")

            description = parse_note_line(description_line)
            search_title, search_artist = parse_title_line(title_line)
            items.append(
                ArtworkItem(
                    title_line=title_line,
                    description=description,
                    search_title=search_title,
                    search_artist=search_artist,
                )
            )
            index += 1

        if len(items) != 5:
            raise ManifestError(f"{page_title} 섹션의 작품 수가 5개가 아닙니다: {len(items)}")

        groups.append(
            PageGroup(
                section_number=section_number,
                page_title=page_title,
                theme=theme,
                items=items,
            )
        )
    return groups


def register_fonts() -> tuple[str, str]:
    regular_font = "Helvetica"
    bold_font = "Helvetica-Bold"
    font_map = {
        "MalgunGothic": Path(r"C:\Windows\Fonts\malgun.ttf"),
        "MalgunGothic-Bold": Path(r"C:\Windows\Fonts\malgunbd.ttf"),
    }
    try:
        if font_map["MalgunGothic"].exists() and "MalgunGothic" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("MalgunGothic", str(font_map["MalgunGothic"])))
        if font_map["MalgunGothic-Bold"].exists() and "MalgunGothic-Bold" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("MalgunGothic-Bold", str(font_map["MalgunGothic-Bold"])))
        if "MalgunGothic" in pdfmetrics.getRegisteredFontNames():
            regular_font = "MalgunGothic"
        if "MalgunGothic-Bold" in pdfmetrics.getRegisteredFontNames():
            bold_font = "MalgunGothic-Bold"
    except Exception:
        pass
    return regular_font, bold_font


class WikimediaCommonsClient:
    def __init__(self, cache_dir: Path, thumb_width: int = 1200, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.cache_dir = cache_dir
        self.thumb_width = thumb_width
        self.timeout = timeout
        self._last_request_time = 0.0
        self._resolved_cache: dict[str, ResolvedArtwork] = {}
        self._image_url_cache: dict[str, list[str]] = {}
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def resolve_artwork(self, item: ArtworkItem) -> ResolvedArtwork:
        cache_key = item.display_title
        if cache_key in self._resolved_cache:
            return self._resolved_cache[cache_key]

        title, image_urls = self._find_best_match(item)
        image_path = self._download_image(image_urls, title)
        description_url = f"https://commons.wikimedia.org/wiki/{quote(title.replace(' ', '_'), safe=':_()')}"
        resolved = ResolvedArtwork(title=title, image_path=image_path, description_url=description_url)
        self._resolved_cache[cache_key] = resolved
        return resolved

    def _find_best_match(self, item: ArtworkItem) -> tuple[str, list[str]]:
        best_match: tuple[float, str, list[str]] | None = None
        for query in self._build_queries(item):
            payload = self._call_api(
                action="query",
                format="json",
                formatversion="2",
                generator="search",
                gsrsearch=query,
                gsrnamespace="6",
                gsrlimit="10",
                prop="imageinfo",
                iiprop="url|size",
                iiurlwidth=str(self.thumb_width),
            )
            pages = payload.get("query", {}).get("pages", [])
            for rank, result in enumerate(pages):
                title = result["title"]
                info = (result.get("imageinfo") or [{}])[0]
                urls = [url for url in [info.get("thumburl"), info.get("url")] if url]
                score = self._score_candidate(title, item, rank)
                if urls:
                    self._image_url_cache[title] = urls
                if urls and (best_match is None or score > best_match[0]):
                    best_match = (score, title, urls)
            if best_match and best_match[0] >= 6.0:
                break

        if not best_match:
            raise ManifestError(f"Commons에서 이미지를 찾지 못했습니다: {item.display_title}")
        return best_match[1], best_match[2]

    def _build_queries(self, item: ArtworkItem) -> Iterable[str]:
        full_query = strip_notes(f"{item.search_title} {item.search_artist}")
        title_only = strip_notes(item.search_title)
        artist_only = base_artist(item.search_artist)
        candidates = [full_query]
        if title_only and artist_only:
            candidates.append(normalize_spaces(f"{title_only} {artist_only}"))
        if title_only:
            candidates.append(title_only)
        seen: set[str] = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                yield candidate

    def _score_candidate(self, candidate_title: str, item: ArtworkItem, rank: int) -> float:
        candidate = strip_notes(candidate_title.removeprefix("File:"))
        title = strip_notes(item.search_title)
        artist = base_artist(item.search_artist)
        full = strip_notes(f"{item.search_title} {item.search_artist}")

        score = 0.0
        if title:
            score += 6.0 if title.lower() in candidate.lower() else 0.0
            score += SequenceMatcher(None, title.lower(), candidate.lower()).ratio() * 3.5
            score += self._token_overlap(title, candidate) * 0.5
        if artist:
            score += 3.0 if artist.lower() in candidate.lower() else 0.0
            score += SequenceMatcher(None, artist.lower(), candidate.lower()).ratio() * 1.8
            score += self._token_overlap(artist, candidate) * 0.4
        if full:
            score += SequenceMatcher(None, full.lower(), candidate.lower()).ratio() * 2.0

        year_hits = [value for value in PAREN_RE.findall(item.title_line) if value.isdigit()]
        for year in year_hits:
            if year in candidate_title:
                score += 1.2

        score -= rank * 0.15
        return score

    @staticmethod
    def _token_overlap(left: str, right: str) -> int:
        right_tokens = set(right.lower().split())
        return sum(1 for token in left.lower().split() if token in right_tokens)

    def _fetch_image_urls(self, title: str) -> list[str]:
        if title in self._image_url_cache:
            return self._image_url_cache[title]
        payload = self._call_api(
            action="query",
            format="json",
            formatversion="2",
            prop="imageinfo",
            titles=title,
            iiprop="url|size",
            iiurlwidth=str(self.thumb_width),
        )
        pages = payload.get("query", {}).get("pages", [])
        if not pages or "imageinfo" not in pages[0]:
            raise ManifestError(f"이미지 URL을 가져오지 못했습니다: {title}")
        info = pages[0]["imageinfo"][0]
        urls = [info.get("thumburl"), info.get("url")]
        resolved_urls = [url for url in urls if url]
        self._image_url_cache[title] = resolved_urls
        return resolved_urls

    def _download_image(self, urls: list[str], title: str) -> Path:
        last_error: Exception | None = None
        for url in urls:
            parsed = urlparse(url)
            suffix = Path(parsed.path).suffix or ".jpg"
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
            safe_stem = re.sub(r"[^0-9A-Za-z._-]+", "_", title.removeprefix("File:"))[:80].strip("_")
            target = self.cache_dir / f"{safe_stem}_{digest}{suffix}"
            if target.exists() and target.stat().st_size > 0:
                return target

            request = Request(url, headers={"User-Agent": USER_AGENT})
            try:
                content = self._read_bytes(request)
            except Exception as exc:
                last_error = exc
                continue
            target.write_bytes(content)
            return target

        if last_error:
            raise last_error
        raise ManifestError(f"이미지 다운로드 실패: {title}")

    def _call_api(self, **params: str) -> dict:
        url = f"{COMMONS_API_URL}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            return json.loads(self._read_bytes(request).decode("utf-8"))
        except HTTPError as exc:
            raise ManifestError(f"Commons API 요청 실패({exc.code}): {exc.reason}") from exc
        except URLError as exc:
            raise ManifestError(f"Commons API 연결 실패: {exc.reason}") from exc

    def _read_bytes(self, request: Request) -> bytes:
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    self._last_request_time = time.monotonic()
                    return response.read()
            except HTTPError as exc:
                self._last_request_time = time.monotonic()
                if exc.code == 429 and attempt < MAX_RETRIES - 1:
                    retry_after = exc.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 3.0 * (attempt + 1)
                    time.sleep(delay)
                    continue
                raise

        raise ManifestError("응답을 읽지 못했습니다.")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)


def truncate_lines(lines: list[str], font_name: str, font_size: int, width: float, max_lines: int) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    trimmed = lines[: max_lines - 1]
    last = lines[max_lines - 1]
    ellipsis = "..."
    while last and pdfmetrics.stringWidth(last + ellipsis, font_name, font_size) > width:
        last = last[:-1]
    trimmed.append((last + ellipsis).strip())
    return trimmed


def draw_wrapped_text(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    top_y: float,
    width: float,
    font_name: str,
    font_size: int,
    leading: int,
    max_lines: int,
    centered: bool = False,
) -> float:
    lines = simpleSplit(text, font_name, font_size, width)
    lines = truncate_lines(lines, font_name, font_size, width, max_lines)
    cursor_y = top_y
    pdf.setFont(font_name, font_size)
    for line in lines:
        if centered:
            pdf.drawCentredString(x + width / 2, cursor_y, line)
        else:
            pdf.drawString(x, cursor_y, line)
        cursor_y -= leading
    return top_y - cursor_y


def fit_image(image_path: Path, max_width: float, fixed_height: float) -> tuple[float, float]:
    image = ImageReader(str(image_path))
    width, height = image.getSize()
    if height == 0:
        return max_width, fixed_height
    scaled_width = width * (fixed_height / height)
    if scaled_width <= max_width:
        return scaled_width, fixed_height
    scale = max_width / width
    return max_width, height * scale


def render_pdf(groups: list[PageGroup], output_path: Path, client: WikimediaCommonsClient) -> list[str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    regular_font, bold_font = register_fonts()

    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    page_width, page_height = A4
    margin_x = 34
    margin_top = 34
    margin_bottom = 28
    slot_gap = 6
    content_width = page_width - (margin_x * 2)
    title_block = 68
    slot_height = (page_height - margin_top - margin_bottom - title_block - (slot_gap * 4)) / 5
    warnings: list[str] = []

    for group in groups:
        top_y = page_height - margin_top
        pdf.setTitle("Wikimedia Commons Passion PDF")
        pdf.setFont(bold_font, 17)
        pdf.drawCentredString(page_width / 2, top_y, f"{group.section_number}. {group.page_title}")
        draw_wrapped_text(
            pdf,
            f"핵심: {group.theme}",
            margin_x,
            top_y - 22,
            content_width,
            regular_font,
            10,
            12,
            2,
            centered=True,
        )

        current_top = top_y - title_block
        for item_index, item in enumerate(group.items, start=1):
            print(f"[{group.section_number}-{item_index}] {item.display_title}")
            slot_bottom = current_top - slot_height
            pdf.roundRect(margin_x, slot_bottom, content_width, slot_height, 8, stroke=1, fill=0)
            inner_x = margin_x + 12
            inner_width = content_width - 24
            text_top = current_top - 15

            draw_wrapped_text(
                pdf,
                item.description,
                inner_x,
                text_top,
                inner_width,
                regular_font,
                9,
                11,
                2,
            )

            image_bottom = slot_bottom + 22
            title_y = slot_bottom + 8
            try:
                resolved = client.resolve_artwork(item)
                draw_width, draw_height = fit_image(resolved.image_path, inner_width, IMAGE_HEIGHT)
                image_x = inner_x + (inner_width - draw_width) / 2
                image_y = image_bottom + max(0, (IMAGE_HEIGHT - draw_height) / 2)
                pdf.drawImage(str(resolved.image_path), image_x, image_y, width=draw_width, height=draw_height, preserveAspectRatio=True, mask="auto")
            except Exception as exc:
                warning = f"{group.section_number}-{item_index}: {item.display_title} / {exc}"
                warnings.append(warning)
                pdf.setFont(regular_font, 9)
                pdf.setFillColorRGB(0.6, 0.1, 0.1)
                pdf.drawCentredString(page_width / 2, image_bottom + (IMAGE_HEIGHT / 2), "이미지를 찾지 못했습니다.")
                pdf.setFillColorRGB(0, 0, 0)

            draw_wrapped_text(
                pdf,
                item.display_title,
                inner_x,
                title_y + 10,
                inner_width,
                bold_font,
                8,
                10,
                1,
                centered=True,
            )
            current_top = slot_bottom - slot_gap

        pdf.showPage()

    pdf.save()
    return warnings


def load_groups(source_path: Path) -> list[PageGroup]:
    return parse_source_text(source_path.read_text(encoding="utf-8"))


def build_pdf(source_path: Path, output_path: Path, cache_dir: Path) -> list[str]:
    groups = load_groups(source_path)
    client = WikimediaCommonsClient(cache_dir=cache_dir)
    return render_pdf(groups, output_path, client)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wikimedia Commons 이미지로 PDF를 생성합니다.")
    parser.add_argument("source", type=Path, help="섹션 원문 텍스트 파일 경로")
    parser.add_argument("--output", type=Path, default=Path("output/passion_artwork.pdf"), help="생성할 PDF 경로")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/commons"), help="다운로드 캐시 폴더")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    warnings = build_pdf(args.source, args.output, args.cache_dir)
    print(f"PDF 생성 완료: {args.output}")
    if warnings:
        print("")
        print("확인 필요 항목:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
