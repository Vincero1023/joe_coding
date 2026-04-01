# Current State

Last updated: 2026-04-01

## Goal

This extension currently targets five actions on the active YouTube video page:

1. Open transcript in a new tab
2. Copy transcript to clipboard
3. Download transcript as `.txt`
4. Build a summary prompt and open the selected AI target in temporary mode when supported
5. Build a manual-writing prompt in Markdown format for information / explainer videos

## Active Build

- `service_worker.js` build id: `2026-04-01-self-healing-fetch-pipeline`
- `popup.js` build label: `1.5.3-self-healing-fetch-pipeline`

## Recent Change Log

### 2026-04-01 self-healing fetch pipeline

- Root cause: transcript recovery paths were wired manually, so fixes could land in one fallback while another path lagged behind or a prepared recovery path stayed unused
- User-facing symptom: the extension could repeat the same failing fetch order on every run even after one path had clearly degraded
- Fix applied: `fetchTranscriptForVideo()` now builds a data-driven step pipeline, persists per-path health, adapts the next fetch order based on recent success/failure, and includes the existing temporary watch-tab recovery path in the real execution flow
- Practical result: repeated failures are less likely to loop through the same dead path order, and future recovery paths are less likely to be forgotten during edits

### 2026-04-01 mobile player caption fallback

- Root cause: several YouTube watch pages now return empty timedtext bodies for web caption URLs, and the previous Android player fallback version could fail with HTTP 400 `Precondition check failed`
- User-facing symptom: actions such as `summarize` could fail after exhausting current-page, source-tab, textTracks, and watch-html fallbacks
- Fix applied: both `fetchTranscriptViaWatchPage()` and the source-tab injected recovery path now try newer mobile player clients (`iOS`, updated `Android`) and reuse their caption track URLs when web caption URLs are empty
- Practical result: transcript fetch no longer depends as heavily on the web timedtext / transcript-panel path for videos where mobile player caption URLs still work

### 2026-03-14 transcript DOM compatibility fix

- Root cause: YouTube watch pages now render transcript rows as `transcript-segment-view-model` / `.ytwTranscriptSegmentViewModelHost` instead of only `ytd-transcript-segment-renderer`
- User-facing symptom: action `open` could fail with `source tab extract failed: transcript panel dom empty`
- Parallel platform symptom: direct timedtext requests could return HTTP 200 with empty body, and some `youtubei` transcript / player calls could fail with HTTP 400 `Precondition check failed`
- Fix applied: `collectDomLines()` in `service_worker.js` now reads both legacy transcript rows and the newer transcript row view-model nodes
- Practical result: source-tab DOM extraction is again the primary recovery path for normal watch pages when direct caption endpoints are unstable

### 2026-03-09 feature upgrade baseline

- Added popup debug panel
- Added Markdown export from transcript viewer
- Added summary preset selection
- Added manual preset selection
- Strengthened transcript readability reflow
- Strengthened transcript-related button discovery in the source-tab extraction path

## Main Files

- `manifest.json`
- `popup.html`
- `popup.js`
- `popup.css`
- `service_worker.js`
- `transcript.html`
- `transcript.js`
- `transcript.css`
- `offscreen.html`
- `offscreen.js`

## Current Flow

### Transcript fetch

Primary path in `service_worker.js`:

1. `resolveActiveVideoTab()`
2. `fetchTranscriptForVideo(videoId, sourceTabId)`
3. `fetchTranscriptFromCurrentPage(...)`
4. Fallback: `fetchTranscriptViaSourceTab(...)`
5. Final fallback: `fetchTranscriptViaWatchPage(...)`

Important notes:

- The most reliable path right now is the in-page extraction path when caption tracks are present.
- When direct caption endpoints are unstable, the source-tab DOM path and mobile player caption fallback are the main recovery paths.
- YouTube direct timedtext fetches can return empty responses depending on current YouTube behavior.
- The source-tab DOM extraction path was strengthened to find transcript-related buttons more aggressively.
- Modern watch pages can render transcript rows as `transcript-segment-view-model` instead of `ytd-transcript-segment-renderer`.

### Action behavior

- `open`: saves `lastResult` and opens `transcript.html` in a new tab
- `copy`: copies transcript via page clipboard or offscreen document fallback
- `download`: saves transcript as a text file through `chrome.downloads.download`
- `summarize`: builds a prompt, stores it in `lastResult`, opens the AI page, and tries prompt insertion
- `manualize`: builds a manual-focused prompt, stores it in `lastResult`, opens the AI page, and tries prompt insertion

### Debug visibility

Popup debug panel now also shows:

- fetch strategy order used for the latest run
- preferred top-level recovery path based on recent history
- per-path success/failure counts and current failure streak

## Added Features

### Popup debug panel

Popup now shows a debug panel with:

- last successful transcript path
- ordered attempt list
- last stored error message and code

Debug state is stored in:

- `STORAGE_KEYS.debugState`

### Markdown export

Transcript viewer supports:

- `Download TXT`
- `Download MD`

Markdown export includes:

- title
- video URL
- language and track
- fetched time
- AI prompt when available
- transcript body
- debug metadata when available

### Summary presets

Popup now includes summary preset selection for:

- `default`
- `sermon`
- `lecture`
- `blog`
- `study`

Preset application updates the editable summary template textarea before saving.

### Manual presets

Popup now includes manual preset selection for:

- `default`
- `tutorial`
- `reference`

Manual presets are designed to push AI output toward usable Markdown manuals instead of generic summaries.

## Transcript Formatting

Transcript text is reformatted for readability in:

- `reflowTranscriptForReading()`
- `splitIntoReadableParagraphs()`
- `splitIntoSentences()`

Current paragraph logic uses:

- sentence boundaries
- paragraph sentence count
- paragraph character length
- topic-shift starters such as `however`, `for example`, `but`, `however`, `하지만`, `예를 들어`
- question / prompt endings

## Known Recovery Steps

If behavior looks wrong after edits:

1. Open `chrome://extensions`
2. Remove the unpacked extension completely
3. Reload this exact folder again as unpacked
4. Verify popup build label and behavior

## Quick Sanity Checks

Run from this folder:

```powershell
node --check service_worker.js
node --check popup.js
node --check transcript.js
node --check content_shortcuts.js
node --check offscreen.js
```

## Known Constraints

- YouTube transcript availability varies by video
- Some videos expose no usable caption data to direct fetch
- Some direct caption URLs now return HTTP 200 with an empty body
- Some `youtubei` transcript / player requests now fail with HTTP 400 `Precondition check failed`
- Newer mobile player clients can still expose usable caption tracks when the web client path is empty
- AI site auto-insertion is best-effort and depends on current site DOM
- Manual generation quality depends on transcript completeness and model response quality

## If It Breaks Again

Start from these checkpoints:

1. Does the popup status show a concrete error message?
2. Is the popup build label `1.5.3-self-healing-fetch-pipeline` or newer?
3. Does `open` create `transcript.html` in a new tab?
4. What does the popup debug panel show for the latest fetch path and attempts?
5. Does `fetchTranscriptFromCurrentPage()` fail first?
6. Does `fetchTranscriptViaSourceTab()` still find transcript UI?
7. After opening transcript UI, do transcript rows exist as `transcript-segment-view-model` nodes?
8. Is the failure only in `summarize` / `manualize` model selection or prompt insertion?
