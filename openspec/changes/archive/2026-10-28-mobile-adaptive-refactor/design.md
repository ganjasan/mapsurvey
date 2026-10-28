# Design: mobile-adaptive-refactor

## Context

The editor is a server-rendered Django app (htmx 1.9 for partial updates, Bootstrap in the
editor, custom CSS on the landing). `editor_base.html` (917 lines) carries the toolbar and
page-tab chrome; the Survey tab renders a three-pane IDE layout (sections tree / question
editor / preview iframe). `base_survey_template.html` (878 lines) renders the respondent
page: full-screen Leaflet map with an absolutely-positioned question panel. `main.css`
already has `@media (max-width: 768px)` blocks, but the editor layout has no mobile
breakpoint at all — audit measured 719px of content on a 390px viewport.

Reference artifacts, both in this change folder / repo root:
- `editor-mobile.mockup.html` — approved v2 mockup (two-level contextual navigation).
- `mobile-ux-audit-2026-08-23.md` — audit findings; P1 items #5–#8 are addressed here.

Constraints: merge reaches prod in minutes (no staging gate); the repo convention is
server-rendered templates + htmx, no SPA framework; static edits go to `survey/assets/`
followed by `collectstatic`; multi-line Django comments must use `{% comment %}`.

## Goals / Non-Goals

**Goals:**
- Editor usable end-to-end on a 390px viewport: navigate structure, edit questions, create
  questions, review responses (charts/map), configure and preview the public results page.
- Respondent survey flow on mobile: map always visible, bottom-sheet question panel,
  visible confirmation of applied geometry.
- One pane vocabulary (Structure / Edit / Preview) across Survey and Public results.
- Autosave with saved-state indicator on all viewports.
- Landing readable without JS.

**Non-Goals:**
- No desktop layout changes (except replacing Save with autosave).
- No Responses data grid on mobile (follow-up: per-session cards).
- No rewrite to a client-side framework; htmx + CSS stays the architecture.
- Not fixing the separately-shipped P0s (chat widget, silent submit failure, track 400).

## Decisions

### D1. CSS-first adaptive layout, JS only for state
The three panes stay in the DOM exactly as today; below 768px a `.mobile-nav` controller
toggles `data-active-pane` on the layout root and CSS shows one pane full-screen. Bottom
tab bar and top strip are plain template additions hidden above 768px.
*Alternative rejected:* separate mobile templates — doubles template maintenance and
guarantees drift; the audit showed the content is fine, only layout fails.

### D2. Two-level contextual navigation (mockup v2)
Top strip = existing page tabs (server-side navigation, as today). Bottom bar = client-side
pane switching within the loaded page (no server round-trip; the panes are already in the
DOM). Responses' bottom bar maps to its existing Table/Map/Charts(+Performance) sub-views;
Public results maps its blocks list / block config / live preview onto Structure / Edit /
Preview.
*Alternative rejected:* bottom bar as first-level nav (4–5 tabs) — loses the approved
three-pane mental model and collides with Responses' own sub-views.

### D3. Drill-down is CSS state, not URL routing
Structure's two levels (sections → questions) and the Edit pane's "last touched question"
reuse the existing selection state (the desktop tree already tracks the selected
section/question). Back buttons pop the visual level; no new URLs. Deep-linking a question
on mobile is explicitly not required in v1.

### D4. Autosave via debounced htmx on existing save endpoints
Question form inputs get `hx-trigger="input changed delay:800ms, change"` posting the same
form the Save button posts today; response swaps a saved-state indicator ("● All changes
saved" / "Saving…" / error state with retry). The Save button is removed on all viewports
once the indicator is stable. Server side: reuse existing save views; add partial-response
support where a full re-render is currently returned.
*Alternative rejected:* localStorage draft + explicit save — invisible-save semantics are
what the owner approved, and the endpoints already exist.

### D5. Bottom sheet is a shared component
One CSS/JS component (`survey/assets/js/components/bottom_sheet.js` + styles) used by both
the respondent page and the editor preview. Three detents: peek (title + progress), half
(default), full (long question lists); map stays interactive above the sheet. The existing
crosshair Apply/Cancel flow is unchanged — after Apply, the sheet shows a per-question
"N added ✓" chip (audit finding #5).

### D6. Question type picker: same metadata, new mobile presentation
The picker already has grouped metadata guarded by drift tests (question-type-picker spec).
On mobile the dialog becomes a full-screen view; map types render as their own group at
the top of "on the map". Picking a type creates the question immediately (existing create
endpoint) and switches to the Edit pane.

### D7. Kill switch
`MOBILE_EDITOR_NAV` env var (default on in dev, on in prod after verification) gates the
editor mobile chrome via a template conditional adding/omitting a `mobile-nav-enabled`
class. Respondent bottom sheet gets its own `MOBILE_BOTTOM_SHEET` flag. Both default to
legacy layout when unset, so a bad deploy is reverted by env var, not rollback.

### D8. Landing reveal as enhancement
Sections are visible by default; a `js-reveal` class is added only by JS when
IntersectionObserver exists and `prefers-reduced-motion` is not set. No-JS and
reduced-motion users see static content.

## Risks / Trade-offs

- [Touch drag reorder on mobile is fragile] → It is the only reorder path (owner removed
  ▲▼). Use long-press activation with generous hit area on the ⠿ handle; if the existing
  desktop DnD library can't do touch long-press, scope a small dedicated handler; verify on
  a real device before enabling the flag in prod.
- [Autosave fires on every keystroke burst against prod] → 800ms debounce + `changed`
  guard; server endpoints are the same ones Save uses today, so load profile is similar to
  users clicking Save often. Watch PostHog error volume after rollout.
- [Autosave changes desktop behavior — the one intentional desktop change] → Keep the
  indicator prominent; error state must be loud (audit P0 #2 taught us silent failure is
  unacceptable). Roll out behind the same kill switch.
- [Bottom sheet vs Leaflet gesture conflicts] → Sheet drag handle is the only drag target;
  map pans everywhere else. Test pinch-zoom near the sheet edge on device.
- [917-line editor_base.html grows further] → Extract mobile chrome into
  `editor/partials/_mobile_nav.html`; run template guard tests right after each template
  edit (project rule).
- [No staging] → Flags default off in prod until each surface is device-verified on a PR
  preview (Render).

## Migration Plan

1. Ship CSS/JS + templates behind flags (both off in prod) — zero visible change.
2. Verify on Render PR preview with real devices (iOS Safari + Android Chrome).
3. Enable `MOBILE_BOTTOM_SHEET` in prod (respondent surface first — highest traffic,
   simplest rollback).
4. Enable `MOBILE_EDITOR_NAV` in prod.
5. Remove Save buttons (autosave indicator stable for ~a week), then remove flags in a
   cleanup change.
Rollback at any step = unset env var, redeploy (minutes).

## Open Questions

- ~~Touch reorder~~ — RESOLVED: SortableJS 1.15 (already in use) supports long-press via
  `delay + delayOnTouchOnly`; no custom handler needed.
- ~~Performance tab on mobile~~ — RESOLVED during implementation: shipped as the fourth
  bottom-bar item (it is the existing pane, no extra cost); rendering quality at 390px
  is checked in the device pass.
