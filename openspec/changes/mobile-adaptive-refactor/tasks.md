# Tasks: mobile-adaptive-refactor

## 1. Foundation (flags, shared chrome)

- [x] 1.1 Add `MOBILE_EDITOR_NAV` and `MOBILE_BOTTOM_SHEET` env flags to `settings.py`
      (default off) + context processor exposure; document in `.env.example`
- [x] 1.2 Extract mobile chrome partial `survey/templates/editor/partials/_mobile_nav.html`
      (top strip + contextual bottom tab bar), rendered only when flag on; hidden ≥768px
- [x] 1.3 One-row mobile toolbar in `editor_base.html`: back · truncating title · version
      chip · ⋯ overflow sheet (publishing widget kept as the version chip with lifecycle
      actions; account/org in ⋯); template guard test run — OK
- [x] 1.4 Mobile breakpoint styles skeleton in `survey/assets/css/editor-mobile.css`:
      pane visibility via `data-active-pane`, one-row toolbar grid, bottom tab bar,
      44px targets; double-gated by body class + media query

## 2. Survey tab: Structure / Edit / Preview

- [x] 2.1 Pane switching JS (client-side, no reload; state survives pane round-trip)
- [x] 2.2 Structure drill-down: sections list → per-section question list → selects into
      Edit; breadcrumb back; Edit empty state ("pick a question in Structure")
- [x] 2.3 Touch reorder: long-press drag on ⠿ handle for sections and questions (verify
      existing DnD lib touch support; else minimal pointer-events handler per design D9/D1)
- [x] 2.4 Read-only banner responsive fix (no self-overlap, visible action button)
- [x] 2.5 Mobile full-screen question type picker from existing picker metadata; map types
      as distinct group; tap creates question + opens Edit; desktop dialog untouched
- [x] 2.6 Tests: editor layout at 390px has no horizontal overflow; picker mobile/desktop
      split; drill-down selection state (GIVEN/WHEN/THEN docstrings)

## 3. Autosave (all viewports)

- [x] 3.1 Debounced htmx autosave on question form inputs (800ms, `changed` guard),
      posting existing save endpoints; partial-response support where needed
- [x] 3.2 Saved-state indicator component: saved / saving / error-with-retry; error state
      loud, form content preserved on failure
- [x] 3.3 Remove explicit Save buttons behind the flag; desktop included
- [x] 3.4 Tests: autosave persists after settle; failure shows error state; no Save button
      rendered when flag on

## 4. Respondent bottom sheet — REVERTED (owner decision 2026-08-23)

- [x] 4.x Built, then removed in review: the legacy panel/crosshair flow works and the
      sheet was never explicitly approved as a respondent-flow mockup. Kept from this
      group: tap-phrased Leaflet.draw tooltips via pointer:coarse (flag-independent).
      The MOBILE_BOTTOM_SHEET flag, bottom-sheet assets and the "N added" chip are gone
      (master's geo-multi counters cover the confirmation need).

## 5. Responses & Public results mobile

- [x] 5.1 Responses: contextual bottom bar (Table / Map / Charts / Performance); mobile
      default = Charts; stat tiles + charts + map render at 390px (Performance may fall
      back behind Charts per design open question — decide and record)
- [x] 5.2 Public results: Structure (block list, same card+handle pattern) / Edit (block
      config) / Preview (live page); status card with publish state, visibility, URL
- [x] 5.3 Tests: bottom bar items per active page tab; public-results panes render at 390px

## 6. Landing & metadata

- [x] 6.1 Landing scroll-reveal → progressive enhancement: content visible by default,
      `js-reveal` only with IntersectionObserver and no `prefers-reduced-motion`
- [x] 6.2 Survey pages: `<title>` = survey name; `html[lang]` = content language (sections
      + thanks page)
- [x] 6.3 Tests: landing sections visible in no-JS rendered HTML; title/lang assertions

## 7. Verification & rollout

- [x] 7.1 `collectstatic` done; full suite: 1417 tests, 0 regressions. The single failure
      (`test_nav_shows_three_lifecycle_spaces`) predates this change — commit 607784f
      renamed the workspace tabs without updating the test; fixed here (test-only)
- [ ] 7.2 Device pass on Render PR preview (iOS Safari + Android Chrome): editor nav,
      reorder long-press, autosave, bottom sheet vs pinch-zoom, type picker
- [x] 7.3 Update `CLAUDE.md` (flags, mobile nav pattern); rollout order noted (bottom
      sheet → editor nav → autosave/Save removal)

## 8. Dashboard (added in review, variant A of dashboard mockup)

- [x] 8.1 Adaptive header: <768 = [search-icon · New Survey · overflow] + count label;
      768–1023 = [search field · New Survey · overflow]; >=1024 = title + search left,
      New Survey + overflow right (Show Archived and Import are P4 and live in the
      overflow on ALL widths — owner decision)
- [x] 8.2 View toggle moved next to the list it controls (right-aligned above the
      collection); <768 it lives in the overflow menu; list view is the mobile default
- [x] 8.3 Compact mobile list rows: no action strip, single KPI, ellipsised name
- [x] 8.4 Help bubble re-anchored to bottom (Tawk pins with top: from the layout
      viewport -> hidden behind the phone URL bar until scroll); lifted above the
      editor tab bar on mobile
- [x] 8.5 Tests: DashboardVariantATest (flag on/off)

## 9. Create-survey wizard (variant A of create mockup)

- [x] 9.1 Restructure survey_create.html into blocks (goal-brief / map / legacy fields) with
      wizard chrome behind MOBILE_EDITOR_NAV: <1024 = steps (goal -> full-screen map ->
      create), >=1024 = merged two-column with reordered blocks; flag off = legacy page
- [x] 9.2 Full-screen map step: map owns the viewport (search, basemap, zoom, center pin);
      fixes pan-vs-scroll and the stray absolute search icon
- [x] 9.3 AMENDED in review: only the NAME leaves the flow (derived from the goal;
      validate_url_name relaxed to Unicode "contains a word char" — creators brief in
      any language, no migration). LANGUAGES returned to step 1 by owner decision:
      picking them up front lets the draft generate translations immediately
- [x] 9.4 Draft path = primary ("Draft my survey"), empty path = secondary ("Start with an
      empty survey"); no "AI" wording in UI copy
- [x] 9.5 Generation progress: draft path returns to the (now full-width) goal pane and
      scrolls the existing #generation-slot poller into view — no new progress UI
- [x] 9.6 Tests: wizard markup behind flag on/off; empty-path creates survey without name
      input; brief-path posts existing generation endpoint (GIVEN/WHEN/THEN)
- [x] 9.7 Geocode-prefill of the map step (no AI): capitalized-word candidates from the
      goal (+ stripped Russian locative endings) resolved via the existing Photon
      geocoder; map aimed only while untouched. "Лучшие места в Бишкеке" -> Bishkek,
      verified live
- [x] 9.8 Polish from review: Cancel removed with wizard on (navbar back covers it),
      sparkles emoji instead of the FA6-only icon, map-step catch-all hide (inline
      display:block label leak), frame-hint pill on the map step

## 10. Survey status line & controls (variant C mockup, approved)

- [x] 10.1 Mobile status line replaces the ctx-bar (<768, flagged): per-status text +
      per-status primary action (draft->Publish, testing->Share test link,
      published->Edit+Share, closed->Edit); response count live
- [x] 10.2 Test-mode sheet: copy tokenized link on top, access password, explainer,
      Publish at the bottom
- [x] 10.3 Edit-intercept on published surveys (mobile): any edit-intent tap opens the
      "opros opublikovan" sheet -> Otkryt novuyu versiyu (editor_create_draft) or
      Prodolzhit pravku (existing draft)
- [x] 10.4 ... menu on survey pages gains Share... and Discard (danger); HEAD badge
      removed; section cards get question counts
- [x] 10.5 Desktop: ctx-bar subtitle becomes the live status text (minimal desktop change)
- [x] 10.6 Tests: status line per status, intercept sheet markup, share menu item,
      counts (GIVEN/WHEN/THEN)

## 11. Survey <-> Public results parity (pr-parity mockup, approved)

- [x] 11.1 Status chip moves from the shared navbar into each tab's status line
      (it describes the tab's entity); navbar tabs get colored status dots for
      both entities (Survey + Public results); flag-gated
- [x] 11.2 Colored chip semantics on both tabs: grey=inactive (Draft/Not
      published), amber=Testing, green=Open/Live, sky=Closed/Frozen (with date)
- [x] 11.3 Public results status line (same anatomy as Survey): chip opens the
      page lifecycle menu (Publish/Unpublish, Freeze/Unfreeze); primary per
      state -- not published->Publish page (disabled+hint until the survey is
      published), live->Share (copies /r/ link)+Freeze+Open as visitor,
      frozen->Update snapshot
- [x] 11.4 Old pr-ctxbar buttons (Preview private/Copy public link/Live
      page/Unpublish/Publish page) and the green live banner render only with
      the flag off; navbar Share/Preview menus stay only on Responses (no
      status line there)
- [x] 11.5 Secondary status text dropped from both status lines (approved v3);
      block rows get type badges; mobile statusbar wraps instead of clipping
- [x] 11.6 Edit button acts directly (draft link/back-to-draft/create version);
      the edit-intercept sheet fires on taps on the disabled editing surface
      instead
- [x] 11.7 Tests: PublicResultsStatusLineTest (per-state chip+primary, dots,
      badges, flag off), SurveyStatusLineTest updated for the chip move
      (GIVEN/WHEN/THEN)
