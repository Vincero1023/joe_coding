# benchmark_tool

Analyzes every HTML file in `input/`, builds one integrated site analysis, and extracts guide-like content into `output/content/`.

Korean usage and JSON field guide:

- `benchmark_tool/USAGE_KO.md`

## Structure

```text
benchmark_tool/
  analyzer/
  core/
  input/
  output/
    site_analysis.json
    content/
      guide_1.html
      guide_1.md
  main.py
```

## Run

Drop HTML files into `benchmark_tool/input/` and run:

```bash
python benchmark_tool/main.py
```

## Outputs

- `output/site_analysis.json`
- `output/content/guide_N.html`
- `output/content/guide_N.md`

## Analysis Scope

- Integrated UI components across all HTML files
- Core feature inference
- User flows
- Data input/output structure
- API patterns
- Guide/help/manual-style content extraction
