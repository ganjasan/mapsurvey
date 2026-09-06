# editor-small-bugs-batch

## Why

A batch of small editor defects found by the owner while testing 2026-09-06. Each is a
few lines; they ship together in one PR.

## What Changes

### 1. "New Question" on a published survey does nothing

Expected: the "This survey is live and collecting responses / Open a new version" sheet.
Actual: nothing. Read-only controls are `disabled` with `pointer-events:none` so the
click reaches their parent, and the intercept listener only recognises `.form-group`,
`.question-item`, `.add-question-btn` itself and the section card heading. The
section panel's New Question button sits in an anonymous `div`, so the click matches
nothing. Fix: when the click lands on a parent inside `#editor-main`/`.sidebar-footer`,
treat it as edit intent if the pointer is over a disabled child control.

### 2. A "Marks" layer shows 0 features although the geo question has answers

A `question`-sourced layer is materialised only at the end of a respondent's section POST.
A layer created after collection started, or answers arriving through ZIP response import,
never reach it — "0 features" until the next respondent happens to submit. Fix:
`layers.backfill_question_layer` materialises every session that already answered the
source question; called on layer creation (`_resolve_layer_choice`) and after
`import_responses_from_archive`.

## Capabilities

### Modified Capabilities

- `survey-editor`: read-only intercept covers every disabled edit control.
- `shared-map-layer`: a `question` layer is backfilled from existing answers on creation and on response import.

## Impact

- `survey/templates/editor/survey_detail.html`, `survey/layers.py`, `survey/editor_views.py`,
  `survey/serialization.py`, `survey/tests.py`. No migration.
