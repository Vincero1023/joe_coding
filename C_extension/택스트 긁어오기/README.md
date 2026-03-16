# Text Copy Helper (Chrome Extension)

Unlock copy protections, capture the clicked frame/page in near-original layout, open it in a helper popup, and copy either:

- HTML
- Markdown

This extension is DOM-based (not OCR). It now prioritizes visual fidelity by keeping original styles and links, while still allowing HTML/Markdown copy.

## Important

Use this only on content you are allowed to copy (your own writing or content with permission/licensing).

## Files

- `manifest.json`: MV3 extension manifest
- `background.js`: action click handler + page extraction
- `shortcut-listener.js`: page-level shortcut listener for capture/download trigger
- `options.html` / `options.css` / `options.js`: shortcut settings UI
- `viewer.html`: helper viewer page
- `viewer.css`: viewer styles
- `viewer.js`: sanitization + clipboard + HTML->Markdown conversion

## Install (Developer Mode)

1. Open `chrome://extensions`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select this project folder (the folder containing `manifest.json`).

## Usage

### 1) Shortcut flow (auto HTML download)

1. Open extension settings and set your preferred shortcut.
   - `chrome://extensions` -> `Text Copy Helper` -> `Extension options`
   - Default shortcut: `Ctrl + Shift + H`
2. Choose capture mode:
   - `Standard mode`: unlock patch applied for higher capture success.
   - `Safe mode (test)`: unlock patch skipped (lower intrusion, possible quality drop).
3. Go to the page you want to capture.
4. Press the configured shortcut.
5. Click the target frame/page once.
6. The extension captures and downloads an `.html` file immediately.

### 2) Action button flow (viewer)

1. Open the page you want to capture.
2. (Optional) Select a text range first if you only want part of the page.
3. Click the extension action button (`Text Copy Helper`).
4. Click once inside the target frame/page area you want to capture.
5. A popup window opens with a visual snapshot (style/layout preserved as much as possible).
6. Click:
   - `Download HTML` (save as `.html` file)
   - `Download TXT` (save as `.txt` file)
   - `Copy HTML`
   - or `Copy Markdown`
7. Press `Esc` if you want to cancel pick mode before clicking.

Right-click unlock only:

1. Right-click page
2. Click `Text Copy Helper: Unlock right-click and text selection`

## How extraction works

- In `Standard mode`, first injects an unlock patch (right-click/select/copy restriction release).
- In `Safe mode`, unlock patch injection is skipped.
- Default is `Safe mode` to reduce intrusive page patching.
- Action click starts frame pick mode and captures only the first frame/page you click.
- Captures full body + head styles (scripts removed for safety).
- Preserves link/image URLs and rewrites links to open in a new tab.
- Converts relative URLs to absolute URLs for better portability.
- Loads the snapshot into an iframe viewer and allows clipboard copy.

## Known limitations

- Highly dynamic pages that depend on runtime JavaScript may differ from the live page because scripts are removed in the snapshot.
- Complex widgets can still convert imperfectly to Markdown.
- Some cross-origin frames may not be script-accessible due to browser security policy.
- Chrome internal pages (`chrome://`, Web Store) are blocked by browser policy.
