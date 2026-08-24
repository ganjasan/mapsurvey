# Tasks: mapless-sections

## 1. Model & serialization

- [x] 1.1 `SurveySection.layout` CharField (choices map/form, default `map`) + additive
      migration. Check migration leaves against master right before the PR
      ([[feedback-parallel-migration-conflicts]]).
- [x] 1.2 Serialize `layout` in `serialize_sections`; import with `map` fallback for
      absent/unknown values.
- [x] 1.3 Tests: round-trip keeps `form`; legacy archive (no key) imports as `map`.

## 2. Respondent rendering

- [x] 2.1 Server-rendered mode: `<body>` gets `survey-form-layout` class when the current
      section is `form` (no map flash on direct load); section partial carries
      `data-layout` for HTMX swaps.
- [x] 2.2 afterSwap hook toggles the body class from `data-layout`; skip `locateUser()`
      while in form mode.
- [x] 2.3 CSS: form mode turns `#info_page` into a centered column (max-width ~760px,
      static positioning) and hides `#map`, `#drawbar`, `#crosshair-overlay`, basemap
      switcher, `#showButton` — one grouped rule with a pointer to the design doc.
- [x] 2.4 Start label: head `form` section with a next section renders its submit as
      "Start" (translatable).
- [x] 2.5 Tests: form section markup (body class present, Start label); map section
      unchanged; direct-load flash guard (class present in initial HTML); template guard
      test after each template edit.

## 3. Editor gating

- [x] 3.1 `SurveySectionForm`: `layout` field (Map / Form); map-position fields hidden
      client-side when Form is selected; `clean` refuses `form` while the section has geo
      questions, naming them.
- [x] 3.2 Question type picker: hide the geo group when the section is `form`
      (modal gets the section layout); server-side rejection of geo `input_type` on
      create/save/preview into a form section.
- [x] 3.3 Tests: switch refused over geo questions; geo create rejected server-side;
      picker markup lacks geo group in form section; happy path persists `form`.

## 4. Scope added in review

- [x] 4.1 Creator-named forward button: `next_label` on section + translation model
      (migration 0058), editor field + per-language inputs, respondent resolution with
      Next/Finish fallback, serialization round-trip, tests. Replaces the Start
      heuristic (user decision 2026-08-23).
- [x] 4.2 Survey theming (#146): accent color in `style_settings` — settings-panel
      toggle + picker, respondent style block, hex validation at form/import/render,
      tests including the CSS-injection probe.

## 5. Ship & apply to Olney

- [x] 5.1 Full suite `./run_tests.sh survey`; verify on the worktree dev stand (walk
      intro→count→conditions as a respondent, both directions).
- [x] 5.2 PR referencing this change; after deploy flip the Olney demo's `intro` section
      to `form` and verify the live test link on phone + desktop.
