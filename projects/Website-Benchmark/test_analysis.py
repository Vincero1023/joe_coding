from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError

from analyzer import analyze_source
from report import render_markdown


class WebsiteBenchmarkTests(unittest.TestCase):
    def build_sample_dir(self) -> str:
        workspace = Path(__file__).resolve().parent
        self.tempdir = TemporaryDirectory()
        temp_path = Path(self.tempdir.name)
        for name in ("sample_home.html", "sample_pricing.html", "sample_contact.html"):
            temp_path.joinpath(name).write_text(workspace.joinpath(name).read_text(encoding="utf-8"), encoding="utf-8")
        return str(temp_path)

    def tearDown(self) -> None:
        if hasattr(self, "tempdir"):
            self.tempdir.cleanup()

    def test_directory_analysis_collects_multiple_pages(self) -> None:
        report = analyze_source(self.build_sample_dir(), max_pages=10)

        self.assertEqual(len(report.pages), 3)

        feature_names = {feature.name for feature in report.feature_summary}
        self.assertIn("Pricing / subscription", feature_names)
        self.assertIn("Contact or lead capture", feature_names)

        component_names = {component.name for component in report.common_components}
        self.assertIn("Header", component_names)
        self.assertIn("Footer", component_names)
        self.assertIn("Hero section", component_names)

    def test_nested_hero_section_is_captured_from_header(self) -> None:
        report = analyze_source("sample_home.html")

        section_kinds = {section.kind for section in report.pages[0].sections}
        component_names = {component.name for component in report.pages[0].components}

        self.assertIn("header", section_kinds)
        self.assertIn("hero", section_kinds)
        self.assertIn("Hero section", component_names)

    def test_markdown_report_contains_inventory_and_flows(self) -> None:
        report = analyze_source(self.build_sample_dir(), max_pages=10)
        markdown = render_markdown(report)

        self.assertIn("# Website Benchmark Report", markdown)
        self.assertIn("## Page Inventory", markdown)
        self.assertIn("## Cross-Page Patterns", markdown)
        self.assertIn("Landing -> pricing -> demo/contact", markdown)

    def test_non_utf8_html_file_is_decoded_with_declared_charset(self) -> None:
        with TemporaryDirectory() as tempdir:
            html_path = Path(tempdir) / "sample_cp949.html"
            html = """
            <html>
              <head>
                <meta charset="cp949">
                <title>문의 페이지</title>
              </head>
              <body>
                <main>
                  <h1>상담 신청</h1>
                  <form action="/contact" method="post">
                    <input name="email" />
                    <textarea name="message"></textarea>
                    <button>보내기</button>
                  </form>
                </main>
              </body>
            </html>
            """
            html_path.write_bytes(html.encode("cp949"))

            report = analyze_source(str(html_path))
            markdown = render_markdown(report)

            self.assertEqual(report.pages[0].title, "문의 페이지")
            self.assertEqual(report.pages[0].encoding, "cp949")
            self.assertIn("문의 페이지", markdown)
            self.assertIn("- Encoding: `cp949`", markdown)

    def test_url_failures_are_reported_in_load_notes(self) -> None:
        with patch("analyzer.urlopen", side_effect=URLError("timed out")):
            report = analyze_source("https://example.com", max_pages=1, timeout=1)
            markdown = render_markdown(report)

        self.assertEqual(len(report.pages), 0)
        self.assertEqual(len(report.load_issues), 1)
        self.assertIn("## Load Notes", markdown)
        self.assertIn("URL error: timed out", markdown)


if __name__ == "__main__":
    unittest.main()
