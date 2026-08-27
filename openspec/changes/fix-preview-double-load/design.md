# Design: fix-preview-double-load

## Context

The editor's Live preview panel (`survey/templates/editor/survey_detail.html`) is an
iframe (`#preview-frame`) whose `src` is set from four places: the initial template
render, the section-click handler, `activatePinned()` (settings/thanks entries), and
`refreshPreview()` (debounced 500ms). `refreshPreview()` is called by the
`sectionSaved`/`questionSaved` events, the language selector — and by a global
`htmx:afterSwap` listener that excludes only `#questionModalBody` and
`#mapPickerModalBody`. The HTMX swap into `#section-content` that accompanies every
section click therefore triggers a second, redundant load of a URL that was just
set explicitly. Confirmed via network log: two identical preview GETs per editor
open and per section switch.

An iframe navigation keeps the old document visible until the new one commits, then
shows blank until first paint (Leaflet + tiles). The duplicate navigation aborts the
first document during that blank phase and pins it for the whole second wait — on
the 0.5-CPU production instance this is the "43s white screen" seen in PostHog
replays. Constraints: the modal's `#question-preview-frame` is a separate mechanism
and out of scope; mobile nav (`editor_mobile_nav.js`) manipulates the
`.editor-preview` container and `.preview-header`, so the container structure must
survive; `.preview-frame` is styled by class in `editor_base.html`.

## Goals / Non-Goals

**Goals**
- Exactly one preview document load per user action.
- No visible blank-iframe phase during preview refreshes; stale content stays
  visible under a loading indicator until the new document is ready.
- Behavior covered by an automated regression test where practical (single-load
  guarantee), manual verification for the visual swap.

**Non-Goals**
- Server-side rendering speed of `editor_section_preview` (separate concern).
- The question modal preview (`#question-preview-frame`).
- Respondent-facing pages; public-results preview (`.pr-preview`).
- Kill switch: this is a JS/CSS-only change to editor chrome with no data risk;
  rollback is a revert.

## Decisions

**D1 — Fix the duplicate at the listener, not the click handler.** Add
`#section-content` to the `htmx:afterSwap` exclusion list. The click handler and
`sectionSaved`/`questionSaved` events already cover every path where a
`#section-content` swap must refresh the preview. Alternative considered: stop
setting `src` in the click handler and let afterSwap own it — rejected because
afterSwap would have to derive the section name from swap context (fragile) and
would serialize the panel load and preview load instead of running them in parallel.

**D2 — Double-buffer with two stacked iframes.** The panel holds two
`iframe.preview-frame` elements, absolutely positioned in the same slot; one is
`.active` (visible), the other hidden and inert. Every navigation writes `src` to
the hidden iframe; on its `load` event the visibility classes swap. All existing
`src`-writers (`buildPreviewUrl` consumers, `activatePinned`, `refreshPreview`)
funnel through one `loadPreview(url)` helper so there is a single navigation path.
Alternative considered: overlay-only (spinner over the single iframe, no buffer) —
rejected per owner decision: the commit-blank phase would still flash through under
the translucent overlay on slow loads. Alternative: `about:blank` interstitial —
that is the current failure mode.

**D3 — Latest-wins on concurrent refreshes.** `loadPreview` stamps each navigation
with a sequence number; a `load` event whose sequence is stale performs no swap.
Combined with the existing 500ms debounce in `refreshPreview`, rapid autosaves
settle on the newest URL (spec scenario "Rapid successive refreshes").

**D4 — Loading indicator as a panel overlay, not inside the iframe.** A spinner
element in `.editor-preview`, shown when `loadPreview` starts and hidden on swap.
Living outside the iframe it needs no template changes to `survey_section.html` and
also covers the tile-loading tail of the visible document's first seconds only
until `load` — accepted limitation (tiles stream in after swap; the map frame is
visible so it reads as loading, not breakage).

**D5 — `load`-event timeout fallback.** If the hidden iframe never fires `load`
(server error page still fires it; a hung connection does not), a 30s timer clears
the indicator and swaps anyway, so the panel cannot get stuck showing stale content
with an eternal spinner. Alternative: no fallback — rejected; a wedged preview with
no feedback is the exact failure mode this change removes.

## Risks / Trade-offs

- [Two iframes double the preview's memory footprint] → the inactive iframe is
  navigated to `about:blank` is NOT done (it would flash on next use); instead it
  simply holds the previous document. One extra survey-section document is
  acceptable; the modal preview already coexists with the panel today.
- [Scripts in the hidden iframe run off-screen (Leaflet sizes against a hidden
  container)] → the buffer iframe is hidden via `visibility:hidden`, not
  `display:none`, so it keeps layout dimensions and Leaflet initializes at the
  correct size; `invalidateSize` on swap as a belt-and-braces if testing shows
  gray tiles.
- [`htmx:afterSwap` exclusion misses a future swap target that should refresh the
  preview] → the exclusion is target-specific (`#section-content`), not a broader
  rule; new editor panels keep the old behavior by default.
- [Mobile preview overlay (`pane-preview-full`) interacts with absolute
  positioning] → container and `.preview-header` are untouched; verify the
  two-iframe slot under `MOBILE_EDITOR_NAV` at <768px during testing.

## Migration Plan

Single PR: template + CSS + `collectstatic`. No migrations, no env vars. Rollback =
git revert. Merge reaches production in minutes; the change is editor-chrome only,
so the blast radius is creators, not respondents.

## Open Questions

- None blocking. If Leaflet mis-sizes in the hidden buffer despite
  `visibility:hidden`, fall back to post-swap `invalidateSize` (D2 note).
