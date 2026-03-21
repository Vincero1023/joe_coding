from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from docx import Document as DocxDocument

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commons_pdf_builder import ArtworkItem, PageGroup, parse_source_text, render_docx, render_pdf


class FakeCommonsClient:
    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path

    def resolve_artwork(self, item: ArtworkItem):
        return type(
            "ResolvedArtwork",
            (),
            {
                "title": item.display_title,
                "image_path": self.image_path,
                "description_url": "https://commons.wikimedia.org/",
            },
        )()


def test_parse_source_text_returns_ten_groups() -> None:
    source_path = ROOT / "data" / "passion_source.txt"
    groups = parse_source_text(source_path.read_text(encoding="utf-8"))

    assert len(groups) == 10
    assert all(len(group.items) == 5 for group in groups)
    assert groups[0].theme == "따르라 / 생명을 버림"


def test_render_pdf_creates_output(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (300, 450), (120, 80, 40)).save(image_path)

    groups = [
        PageGroup(
            section_number=1,
            page_title="테스트 페이지",
            theme="테스트 핵심",
            items=[
                ArtworkItem(
                    title_line=f"작품 {index}  화가",
                    description="설명 문장",
                    search_title=f"작품 {index}",
                    search_artist="화가",
                )
                for index in range(1, 6)
            ],
        )
    ]
    output_path = tmp_path / "result.pdf"

    warnings = render_pdf(groups, output_path, FakeCommonsClient(image_path))

    assert warnings == []
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_render_docx_creates_editable_output(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (300, 450), (120, 80, 40)).save(image_path)

    groups = [
        PageGroup(
            section_number=1,
            page_title="?뚯뒪???섏씠吏",
            theme="?뚯뒪???듭떖",
            items=[
                ArtworkItem(
                    title_line=f"?묓뭹 {index}  ?붽?",
                    description="?ㅻ챸 臾몄옣",
                    search_title=f"?묓뭹 {index}",
                    search_artist="?붽?",
                )
                for index in range(1, 6)
            ],
        )
    ]
    output_path = tmp_path / "result.docx"

    warnings = render_docx(groups, output_path, FakeCommonsClient(image_path))

    assert warnings == []
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    document = DocxDocument(output_path)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)

    assert "1." in text
    assert "?ㅻ챸 臾몄옣" in text
    assert "Source: https://commons.wikimedia.org/" in text
    assert len(document.inline_shapes) == 5
