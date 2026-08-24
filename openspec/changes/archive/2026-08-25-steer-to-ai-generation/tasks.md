## 1. Kill switch

- [x] 1.1 Add `CREATE_STEER_AI` to `mapsurvey/settings.py` (env var, default `True`, same idiom as `MOBILE_EDITOR_NAV`) and expose it via the existing context processor; document it in `.env.example`
- [x] 1.2 Test: with the flag off, the create page renders the pre-change markup — flat brief panel, no disclosure, no autofocus, no intercept container

## 2. Single-field brief (desktop + wizard, flag on)

- [x] 2.1 Wrap audience, map-target, and use-case chips in `<details class="ai-more"><summary>Add details (optional)</summary>…</details>` in `survey_create.html`; render `open` when any of those fields is bound with a value or has errors
- [x] 2.2 Add `autofocus` to the goal textarea, emitted only when the name field is hidden (wizard flag on) so focus is never contested
- [x] 2.3 Style the disclosure for both layouts (summary as a quiet link-like row; chips/fields unchanged inside); check the wizard goal step at 390px
- [x] 2.4 Tests: unbound form ⇒ collapsed; bound audience value ⇒ `open` rendered; flag off ⇒ no `<details>` in markup

## 3. Empty-path intercept

- [x] 3.1 Add the inline prompt markup (hidden container near `.create-actions` / wizard goal footer): offer text, "Generate draft" primary, "Create empty anyway" secondary; `{% comment %}` for any multi-line template notes
- [x] 3.2 Implement `maybeOfferDraft(surface)`: capture-phase guard on `#empty-btn` click and inside `wizardNext('empty')`; fires only when flag on + AI available + goal non-empty + not yet shown this page load; `preventDefault` + `stopPropagation`, show prompt, latch
- [x] 3.3 Wire prompt actions: accept ⇒ desktop `#generate-btn` click / wizard `wizardNext('draft')`; decline ⇒ resume the original empty flow (guard latched)
- [x] 3.4 Tests: rendered markup contains the intercept container only with flag on + `ai_available`; blank-goal empty POST still creates a survey (existing `test_create_empty_works_with_an_untouched_brief` stays green)
- [x] 3.5 Browser-drive the intercept (desktop + wizard viewport): filled goal → empty click → prompt; decline → empty survey; accept → generation starts (test client can't see JS behavior)

## 4. Wizard empty path skips the map step

- [x] 4.1 Change `wizardNext('empty')` (flag on): after the intercept guard, set `path='empty'`, run `ensureName()`, click `#empty-btn` directly instead of `wizardGoto('map')`
- [x] 4.2 Verify hidden `map_lat/lng/zoom` are always populated at submit time from the initial map sync (including before/after async geolocation lands)
- [x] 4.3 Flag off: wizard empty path still goes to the map step (assert in test from 1.2 or a dedicated one)
- [x] 4.4 Browser-drive at mobile viewport: blank goal → "Skip and start from scratch" → lands in the editor with no "Where?" step; draft path still shows the map step

## 5. Intercept analytics

- [x] 5.1 Capture `ai_empty_intercept` (`outcome`: shown/accepted/declined, `surface`: desktop/wizard) via `window.posthog && posthog.capture(...)` at the three interaction points; no brief text in properties
- [x] 5.2 Verify no-op safety with PostHog absent (empty `POSTHOG_PROJECT_KEY` — local dev default)

## 6. Verification

- [x] 6.1 Run the template-comment guard test immediately after template edits, then `./run_tests.sh survey` for the create/wizard test classes
- [x] 6.2 Full-page pass at 390px and ≥1024px with flag on and off (four states): no layout regressions on the create page
- [x] 6.3 Update `openspec/backlog/INDEX.md` / backlog item status if this change closes a tracked idea

## 7. Example brief chips

- [x] 7.1 Add the "Try an example" chip row above the goal textarea (flag on + AI available): 3 prewritten geo-survey briefs; click fills goal, focuses it, marks the chip active
- [x] 7.2 Capture `ai_example_chip` (chip label only — static copy, no user text) via the same PostHog guard
- [x] 7.3 Tests: chips rendered with flag on + provider; absent with flag off; browser-drive one chip → goal filled
