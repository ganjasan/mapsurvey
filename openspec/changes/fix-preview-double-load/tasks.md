# Tasks: fix-preview-double-load

## 1. Deduplicate preview loads

- [x] 1.1 Add `#section-content` to the `htmx:afterSwap` exclusion list in `survey_detail.html` so the swap that accompanies a section click no longer triggers `refreshPreview()`
- [x] 1.2 Verify by network log (Playwright): editor open and section switch each produce exactly one GET of the preview URL; language change and `sectionSaved`/`questionSaved` still refresh

## 2. Double-buffered iframe with loading indicator

- [x] 2.1 Replace the single `#preview-frame` with a two-iframe buffer slot inside `.editor-preview` (same `.preview-frame` class styling; absolute stacking; hidden buffer uses `visibility:hidden` to preserve layout size), plus a loading-overlay element in the panel
- [x] 2.2 Implement `loadPreview(url)` in `survey_detail.html`: navigate the hidden iframe, show the overlay, sequence-stamp the request (latest-wins), swap visibility classes on `load`, hide overlay; 30s timeout fallback swaps and clears the overlay if `load` never fires
- [x] 2.3 Route all existing `src`-writers through `loadPreview`: initial section activation, section-click handler, `activatePinned()` (settings → `about:blank`, thanks → thanks-preview URL), `refreshPreview()`, and the empty-state path after section delete
- [x] 2.4 Add overlay/spinner styles (scoped to the editor preview panel) and run `collectstatic` — styles placed inline in editor_base.html next to the existing preview-panel styles; no asset files changed, collectstatic not required

## 3. Verification

- [x] 3.1 Playwright with throttled `/preview/` responses: stale content stays visible during the wait, overlay shows, new section swaps in with no blank frame; rapid double refresh settles on the latest URL
- [x] 3.2 Check Leaflet map renders at correct size after a hidden-buffer load (apply `invalidateSize` on swap only if gray/mis-sized tiles appear)
- [x] 3.3 Mobile check (<768px, `MOBILE_EDITOR_NAV` on): full-screen preview pane still works with the two-iframe slot and back button
- [x] 3.4 Run template guard test and the survey editor test suite (`./run_tests.sh survey`)
