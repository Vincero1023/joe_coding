# Step Log

Use this workflow before each change:

1. Run `powershell -ExecutionPolicy Bypass -File .\tools\start-step.ps1 -Name <step-name> -Note "<what changes next>"`
2. Make the code change.
3. If needed, roll back with `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name <step-name>`

## step-001-current-state
- Created: 2026-03-14T15:55:51+09:00
- Note: Baseline before next fix
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-001-current-state`

## step-002-debug-logging-and-guards
- Created: 2026-03-14T16:00:52+09:00
- Note: Tighten price guards and store debug details for failed Agoda scans
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-002-debug-logging-and-guards`

## step-003-guided-price-detection
- Created: 2026-03-14T16:04:19+09:00
- Note: Use only user-guided price anchors: start-price then one-night fallback
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-003-guided-price-detection`

## step-004-failure-debug-details
- Created: 2026-03-14T16:07:54+09:00
- Note: Store scan failure diagnostics and show them in popup for discussion
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-004-failure-debug-details`

## step-005-popup-debug-visibility
- Created: 2026-03-14T16:15:51+09:00
- Note: Rewrite popup rendering so failed results visibly show debug details and open final URL
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-005-popup-debug-visibility`

## step-006-dom-price-attributes
- Created: 2026-03-14T16:28:00+09:00
- Note: Prefer Agoda DOM price attributes before text anchors and improve failure diagnostics
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-006-dom-price-attributes`

## step-007-results-tab-workflow
- Created: 2026-03-14T16:44:07+09:00
- Note: Open a dedicated results tab for live scan progress, links, and post-scan review
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-007-results-tab-workflow`

## step-008-version-1-0-catalog-rules
- Created: 2026-03-14T22:06:07+09:00
- Note: Save version 1.0 rollback point and replace catalog rules with the new campaign sets
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-008-version-1-0-catalog-rules`

## step-009-system-documentation
- Created: 2026-03-14T22:20:20+09:00
- Note: Add a full system architecture and operation document for the extension
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-009-system-documentation`

## step-010-new-site-update-saved
- Created: 2026-03-14T22:25:35+09:00
- Note: Save the current state including the latest site updates, version 1.0 catalog rules, results tab workflow, and system documentation
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-010-new-site-update-saved`

## step-011-version-1-2-mark
- Created: 2026-03-14T22:28:03+09:00
- Note: Mark the current state as version 1.2 and update version references in docs
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-011-version-1-2-mark`

## step-012-parallel-scan-engine
- Created: 2026-03-14T22:30:42+09:00
- Note: Refactor background scan engine from sequential tabs to a pooled parallel runner with tab reuse and fast price wait
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-012-parallel-scan-engine`

## step-013-stabilize-parallel-navigation
- Created: 2026-03-14T22:44:32+09:00
- Note: Keep worker-pool parallelism, but make reused scan tabs wait for a real navigation cycle before scraping.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-013-stabilize-parallel-navigation`

## step-014-dom-ready-navigation-wait
- Created: 2026-03-14T22:48:49+09:00
- Note: Replace strict tab complete wait with post-navigation DOM-ready wait for reused parallel scan tabs, and relax aggressive time budgets.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-014-dom-ready-navigation-wait`

## step-015-page-text-guided-fallback
- Created: 2026-03-14T23:00:34+09:00
- Note: Add whole-page visible-text fallback for exact 시작가/1박 guided price detection and relax price wait.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-015-page-text-guided-fallback`

## step-016-restore-real-cids
- Created: 2026-03-14T23:09:11+09:00
- Note: Replace symbolic placeholder campaign ids with previously verified numeric Agoda cids so scan pages render real prices again.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-016-restore-real-cids`

## step-017-restore-stable-waits
- Created: 2026-03-14T23:15:57+09:00
- Note: Keep parallel worker tabs, but restore the previously stable Agoda wait timing: full load, settle delay, and longer price wait.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-017-restore-stable-waits`

## step-018-hybrid-page-ready-wait
- Created: 2026-03-14T23:22:31+09:00
- Note: Use hybrid Agoda page readiness for reused scan tabs: accept full load or DOM-ready after navigation to avoid endless loading timeouts.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-018-hybrid-page-ready-wait`

## step-019-strict-korean-anchors
- Created: 2026-03-14T23:37:50+09:00
- Note: Restrict guided price anchors to the user's exact rules: 시작가 then next amount, otherwise 1박 then previous amount. Avoid broad English from/per-night false positives.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-019-strict-korean-anchors`

## step-020-reduce-concurrency-to-3
- Created: 2026-03-14T23:58:05+09:00
- Note: Reduce parallel scan worker/tab count from 6 to 3 to lower simultaneous Agoda page load pressure.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-020-reduce-concurrency-to-3`

## step-021-version-1-3-mark
- Created: 2026-03-15T00:05:02+09:00
- Note: Version 1.3 baseline: stable parallel scanner with concurrency 3, verified numeric cids, hybrid page readiness, and strict Korean price anchors.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-021-version-1-3-mark`

## step-022-version-1-4-link-rules
- Created: 2026-03-15T00:05:13+09:00
- Note: Version 1.4 update: add newly observed random CID link rules and update version/docs from the 1.3 baseline.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-022-version-1-4-link-rules`

## step-023-priority-mobile-tab-pool
- Created: 2026-03-15T00:11:25+09:00
- Note: Add priority ordering and mobile/desktop scenario variants while keeping concurrency fixed at 3 and reusing a 3-tab hidden scan pool.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-023-priority-mobile-tab-pool`

## step-024-version-1-5-mark
- Created: 2026-03-15T00:21:37+09:00
- Note: Mark current working scanner state as version 1.5.0 after priority ordering, mobile variants, and stable 3-tab reuse.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-024-version-1-5-mark`

## step-025-upgrade-pass-review
- Created: 2026-03-15T00:24:07+09:00
- Note: Validate current implementation against requested scan-tab-pool, priority, mobile/desktop variants, and result streaming; patch only gaps while keeping concurrency fixed at 3.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-025-upgrade-pass-review`

## step-026-stable-scan-pool-priority-mobile-saved
- Created: 2026-03-15T00:32:17+09:00
- Note: Save current stable state with fixed 3-tab scan pool, priority ordering, and desktop/mobile variant scanning.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-026-stable-scan-pool-priority-mobile-saved`

## step-027-reservation-price-tracker
- Created: 2026-03-15T00:34:15+09:00
- Note: Add reservation tracking, saved reservation storage, reservation list page, manual/automatic rescans, and price-drop notifications using the existing Agoda scan engine.
- Files: `background.js`, `popup.js`, `popup.html`, `popup.css`, `catalog.js`, `manifest.json`, `README.md`
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-027-reservation-price-tracker`

## step-028-reservation-tracker-implemented
- Created: 2026-03-15T00:51:35+09:00
- Note: Implement Reservation Price Tracker with saved reservations, manual and alarm-based rescans, notifications, and dedicated tracker UI.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-028-reservation-tracker-implemented`

## step-029-korean-ui-and-manual-reservation-entry
- Created: 2026-03-15T00:58:26+09:00
- Note: Translate UI and user-facing messages to Korean, add direct reservation URL registration, and mark version 2.0.0.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-029-korean-ui-and-manual-reservation-entry`

## step-030-version-2-0-korean-manual-reservation
- Created: 2026-03-15T01:07:49+09:00
- Note: Mark version 2.0.0 after Korean UI unification and direct reservation URL registration.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-030-version-2-0-korean-manual-reservation`

## step-031-guided-scope-price-fallback
- Created: 2026-03-15T09:59:45+09:00
- Note: When Agoda price attributes appear as 0 first, fall back to scoped/page snippets around 시작가 or 1박 and continue as soon as a real amount is visible.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-031-guided-scope-price-fallback`

## step-032-fix-guided-matchall-fallback
- Created: 2026-03-15T10:05:56+09:00
- Note: Fix guided fallback regex matching so 시작가 and 1박 fallback works on machines where Agoda price attributes stay at 0 first.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-032-fix-guided-matchall-fallback`

## step-033-fix-currency-code-whitelist
- Created: 2026-03-15T10:09:28+09:00
- Note: Stop treating airport or route codes like ICN as currency codes; only recognize known currency codes and keep Agoda result currency aligned with KRW defaults.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-033-fix-currency-code-whitelist`

## step-034-ignore-flight-widget-baseline-price
- Created: 2026-03-15T10:19:12+09:00
- Note: Exclude flight and transport widgets like ICN-PEK passenger fare blocks from Agoda baseline price extraction, and prefer lower amounts on tied 시작가 candidates.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-034-ignore-flight-widget-baseline-price`

## step-035-agoda-best-branding-and-ui-refresh
- Created: 2026-03-15T10:25:45+09:00
- Note: Rename product to Agoda Best, add polished icons/favicon, refine popup/results/reservations layouts, and document the full project history for the 2.0 release.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-035-agoda-best-branding-and-ui-refresh`

## step-036-agoda-best-v2-docs-icons-layout
- Created: 2026-03-15T10:33:10+09:00
- Note: Finalize Agoda Best 2.0 branding, documentation, Korean UI text, and extension icons.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-036-agoda-best-v2-docs-icons-layout`

## step-037-agoda-best-2-0-mark
- Created: 2026-03-15T10:48:49+09:00
- Note: Mark Agoda Best 2.0 branding, Korean UI, documentation, and icon refresh as a rollback point.
- Files: (none)
- Rollback: `powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name step-037-agoda-best-2-0-mark`

