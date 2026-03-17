from __future__ import annotations

import argparse
from pathlib import Path

from analyzer.content_extractor import export_content_candidates, extract_content_candidates
from analyzer.site_analyzer import analyze_document, merge_site_analyses
from core.exporter import export_json
from core.loader import load_html_directory

BASE_DIR = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze all HTML files in the input folder and export an integrated site JSON.")
    parser.add_argument(
        "--input-dir",
        dest="input_dir",
        default=str(BASE_DIR / "input"),
        help="Directory that contains HTML files. Default: benchmark_tool/input",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default=str(BASE_DIR / "output"),
        help="Directory for site_analysis.json and extracted content. Default: benchmark_tool/output",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    documents = load_html_directory(args.input_dir)
    if not documents:
        raise SystemExit("No HTML files found in the input directory.")

    document_analyses: list[dict[str, object]] = []
    content_candidates: list[dict[str, object]] = []

    for source_path, html, soup in documents:
        analysis = analyze_document(str(source_path), html, soup)
        document_analyses.append({"source_file": source_path.name, "analysis": analysis})
        content_candidates.extend(extract_content_candidates(str(source_path), html, soup))

    output_dir = Path(args.output_dir).expanduser().resolve()
    content_exports = export_content_candidates(content_candidates, output_dir / "content")
    integrated_analysis = merge_site_analyses(document_analyses, content_exports)
    output_path = export_json(integrated_analysis, str(output_dir / "site_analysis.json"))

    print(f"Analyzed {len(documents)} HTML file(s) -> {output_path}")
    print(f"Extracted {len(content_exports)} content file set(s) -> {output_dir / 'content'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
