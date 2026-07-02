## 1. Shared nav CSS

- [x] 1.1 In `editor_base.html`: add CSS for navbar action dropdowns (`.nav-action` + menu), the publishing-widget dropdown sections (Collection/Discovery/Results/Version, toggle rows), and the ⚙ icon button. Reuse existing `.survey-nav-tab(s)` for the three space tabs.

## 2. Publishing widget + lifecycle extraction (F7)

- [x] 2.1 New `editor/partials/_publishing_widget.html`: status chip → dropdown with Collection (transitions), Discovery (visibility toggle), Results page (from `survey.public_results_page`), Version (version + draft actions). Owner-only interactive; static chip otherwise.
- [x] 2.2 New `editor/partials/_lifecycle_scripts.html`: move `doTransition`, `showPublishConfirm`, `doPublishFromTesting`, draft-publish JS + the publish/discard modals out of `survey_detail.html`; add `toggleVisibility()` calling the new endpoint.
- [x] 2.3 New view+URL `editor_survey_visibility` (POST, owner): set `visibility` to `public`/`private`; return JSON. No other fields touched.

## 3. Workspace nav restructure (F1/F2/F3/F4/F8)

- [x] 3.1 Rewrite `editor/partials/_survey_nav_tabs.html` into the workspace nav: survey name slot, publishing widget include, three space tabs (Build/Results/Publish), `Share ▾`, `Preview ▾`, `⚙`. Drop the Share tab and the deprecated Settings tab.
- [x] 3.2 `Share ▾` menu: Copy survey link, QR code, Tracking links… (→ `editor_survey_share`), Copy results link (when results page live).
- [x] 3.3 `Preview ▾` menu: Survey as respondent (`survey` url), Results page (`editor_public_results_preview`).
- [x] 3.4 `survey_detail.html`: use `active_tab="build"`, drop the inline status dropdown (now in the widget), include `_lifecycle_scripts.html`, keep draft-copy affordances.
- [x] 3.5 `analytics_dashboard.html` + `public_results.html`: `active_tab="results"`/`"publish"`, include `_lifecycle_scripts.html`.

## 4. Results space (F5) — DEVIATED from the mockup, see note

The mockup drew a flat Table/Map/Charts/Performance sidebar. In reality the Data
workspace is a **split-pane IDE** (Table/Map/Charts can be shown simultaneously in
resizable/splittable panes — the Data Management epic's split-pane-tree). A flat
sidebar would delete that capability, a regression. So F5 was scoped down:

- [x] 4.1 Rename the space to **Results** (nav label) and keep the split-pane Data workspace intact; Data/Performance become internal sub-navigation of the Results space rather than a peer of the top spaces.
- [x] 4.2 Add a **Download data** action to the Results sub-bar (the mockup's "download in Results"); the dashboard overflow menu keeps export/backup.
- [x] 4.3 Verify the split-pane Table/Map/Charts + Performance still work against real data on :8010 (HTMX, map init, charts) — no regression.
- [ ] 4.4 (Deferred / to discuss) A true unified left-sidebar for Results that *preserves* split-pane power — not attempted; flagged to the user.

## 5. Dashboard cards (F6/F10/F14)

- [x] 5.1 `editor.html` grid + list cards: actions Build / Results / Publish / Share / More; drop the Settings link; remove BETA badges; add a "Results live" chip from `public_results_page`.
- [x] 5.2 Ensure Download stays reachable (overflow menu keeps export/backup; primary download now also in Results).

## 6. Verification

- [x] 6.1 `./run_tests.sh survey` — zero regressions (URLs/view names unchanged, so existing tests should pass; fix any that assert on old tab labels).
- [x] 6.2 Browser pass on :8010: three spaces switch; Share▾/Preview▾ work; publishing widget toggles status + visibility + shows results link; Results sidebar; dashboard cards.
- [x] 6.3 Add/adjust tests: `editor_survey_visibility` toggles field + owner-gated; publishing widget renders on all three spaces; nav shows Build/Results/Publish (no Editor/Settings tab).
