# Proposal: mobile-adaptive-refactor

## Why

The 2026-08-23 mobile UX audit (`mobile-ux-audit-2026-08-23.md`, repo root) found the
respondent survey flow barely usable on phones (question panel hides the map, 17px collapse
control, no feedback after placing geometry) and the editor effectively unusable (719px
content on a 390px viewport, 4-row wrapped toolbar, one-word-per-line preview column).
Creators increasingly open the editor from phones, and respondents are majority-mobile for
civic surveys; both surfaces must become genuinely adaptive. The owner explicitly decided
against a "desktop-only" editor fallback — the editor is in scope.

## What Changes

- **Editor gets two-level contextual navigation below 768px** (per approved mockup
  `editor-mobile.mockup.html`): top strip = existing page tabs (Survey · Responses ·
  Public results); bottom tab bar = panes of the active page. Survey and Public results
  share one pane vocabulary — **Structure / Edit / Preview**; Responses gets
  Table / Map / Charts / Performance. Desktop layout is untouched.
- **Structure pane drills down**: sections list → section's questions → question opens in
  Edit. Reordering via long-press drag on the handle only.
- **Question creation becomes a full-screen type picker** on mobile, with the three map
  types as a first-class group; picking a type creates the question and opens Edit.
- **Autosave replaces the explicit Save button — on desktop too** ("All changes saved"
  indicator line). This is the only intentional desktop behavior change.
- **Respondent survey page moves to a bottom-sheet pattern on mobile**: map always visible,
  question panel as a draggable sheet; visible confirmation after a geometry is applied;
  instruction copy matches the actual crosshair interaction.
- **The 4-row editor toolbar collapses to one row** on mobile: back · title · version chip ·
  ⋯ overflow (Share / Settings / Versions / Publish / account).
- **Landing content renders without scroll-triggered JS**: sections visible by default,
  reveal animation only as progressive enhancement (`IntersectionObserver` +
  `prefers-reduced-motion`).
- **Survey pages get a real `<title>` and `lang` attribute** (survey name / content language).
- Mobile Responses tab leads with Charts; summary stats + charts + map ship first.

## Capabilities

### New Capabilities
- `editor-mobile-navigation`: two-level contextual navigation of the editor below 768px —
  top page-tab strip, contextual bottom pane bar, shared Structure/Edit/Preview vocabulary,
  drill-down inside Structure, one-row toolbar with overflow menu.
- `editor-autosave`: autosave of editor changes with a saved-state indicator, replacing the
  explicit Save button on all viewports.
- `respondent-bottom-sheet`: bottom-sheet question panel over an always-visible map on the
  respondent survey page (mobile), including post-apply geometry confirmation and
  interaction-accurate instruction copy.
- `survey-page-metadata`: respondent survey pages carry a meaningful `<title>` and
  `html[lang]`.

### Modified Capabilities
- `survey-editor`: the "Survey editor layout" requirement gains mobile-breakpoint behavior
  (panes become full-screen views; desktop three-pane layout unchanged).
- `question-type-picker`: on mobile the picker is a full-screen view with map types grouped
  first-class; desktop dialog behavior unchanged.
- `landing-page`: below-the-fold content must be visible without JavaScript; scroll-reveal
  becomes progressive enhancement honoring `prefers-reduced-motion`.

## Out of Scope

- Responses data grid on mobile (per-session cards — a follow-up change).
- Audit P0 fixes shipping separately: chat-widget overlap on `/accounts/register/`,
  silent htmx submit failure, `/surveys/track/event/` 400.
- Any redesign of desktop layouts beyond the autosave control.

## Impact

- **Templates**: `survey/templates/editor/editor_base.html`, `editor.html`, editor
  partials; `base_survey_template.html` and section/answer templates;
  `landing.html`/`base_landing.html`.
- **Static assets**: editor and respondent CSS/JS under `survey/assets/` (new breakpoint
  styles, bottom-sheet component, tab-bar component, autosave client) — edited in
  `survey/assets/`, then `collectstatic`.
- **Views/endpoints**: autosave needs htmx-friendly partial-save endpoints in the editor
  views; no data-model changes anticipated.
- **Tests**: template guard tests per feedback rules; GIVEN/WHEN/THEN docstrings; assertions
  on rendered markup (test client does not catch dead controls).
- **Risk**: merge-to-prod is minutes with no staging gate — ship behind an env-var kill
  switch (`MOBILE_EDITOR_NAV`-style flag) so the editor nav can be reverted instantly.
