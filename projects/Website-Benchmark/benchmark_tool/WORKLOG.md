# Worklog

## 2026-03-17 17:45
- Expanded the plan from single-file analysis to multi-file integration across the entire `input/` directory.
- Split responsibilities into a site analyzer and a separate content extractor for guide/manual-style sections.
- Added a simple Windows batch launcher request to the current work scope.

## 2026-03-17 18:00
- Fixed the local batch launcher path so `benchmark_tool\\run.bat` runs from its own directory without an invalid nested path.
- Added `run_benchmark_tool.bat` at the repository root for one-step execution from the project folder.
- Re-ran the analyzer to confirm integrated JSON export and content extraction still succeed after the launcher updates.

## 2026-03-17 18:06
- Normalized the content keyword list in `content_extractor.py` to ASCII-safe unicode escape literals so Korean keyword matching remains stable even when the shell encoding is noisy.
- Recompiled the analyzer modules and executed `python benchmark_tool\\main.py` again after the keyword cleanup.
- Confirmed the integrated `site_analysis.json` and `output/content/` exports are still generated.

## 2026-03-17 20:58
- Added `benchmark_tool/USAGE_KO.md` to document the analyzer purpose, run commands, output files, and how to read `site_analysis.json`.
- Documented the current AI-oriented `features` schema, including how `goal`, `description`, `inputs`, `outputs`, `logic`, and `ui` should be interpreted.
- Linked the new guide from `benchmark_tool/README.md` so the current entry point points to the up-to-date JSON decoding guide.
