from __future__ import annotations

import argparse
import sys
from pathlib import Path

from analyzer import analyze_source
from report import render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze a website or static HTML files and generate a Markdown benchmark report."
    )
    parser.add_argument("source", help="A URL, a local HTML file, or a directory containing HTML files.")
    parser.add_argument(
        "-o",
        "--output",
        default="report.md",
        help="Path to the generated Markdown report. Default: report.md",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum number of pages to analyze for directory or URL inputs. Default: 5",
    )
    parser.add_argument(
        "--crawl-depth",
        type=int,
        default=1,
        help="How deep to crawl same-domain links when the source is a URL. Default: 1",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Network timeout in seconds for URL inputs. Default: 10",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        site_analysis = analyze_source(
            args.source,
            max_pages=max(1, args.max_pages),
            crawl_depth=max(0, args.crawl_depth),
            timeout=max(1, args.timeout),
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(site_analysis), encoding="utf-8")

    if site_analysis.load_issues:
        print(f"Encountered {len(site_analysis.load_issues)} load issue(s).", file=sys.stderr)
    print(f"Analyzed {len(site_analysis.pages)} page(s) and wrote {output_path}")
    return 0 if site_analysis.pages else 1
