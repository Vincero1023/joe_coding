from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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

    def test_markdown_report_contains_inventory_and_flows(self) -> None:
        report = analyze_source(self.build_sample_dir(), max_pages=10)
        markdown = render_markdown(report)

        self.assertIn("# Website Benchmark Report", markdown)
        self.assertIn("## Page Inventory", markdown)
        self.assertIn("## Cross-Page Patterns", markdown)
        self.assertIn("Landing -> pricing -> demo/contact", markdown)


if __name__ == "__main__":
    unittest.main()
