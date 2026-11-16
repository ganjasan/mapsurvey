## Context

`data.dataviews.result(view, lang)` returns masked engagement steps, a masked cross-tab and grid
cells. `ReportBlock.view` (RESTRICT) exists since #703 and nothing sets it yet. A report's map
block is always a grid (`data.aggregate.grid`).

## Goals / Non-Goals

**Goals:** show the two table kinds of #692 as blocks; let an author show marks; live numbers in
text. **Non-Goals:** coverage and density as block choices (the map block keeps its grid; choosing
a view for a map comes with templates, #705); scoping a block by a saved Responses filter; a chart
of two questions (the table is the v1 form of a cross-tab).

## Decisions

1. **A view block makes its view.** `services.add_view_block` calls `data.services.create_view`
   on the home survey's responses dataset (or reuses an identical one) and stores the FK. The
   author never visits Data to add a block, and the refusal rules (question types, two different
   questions) stay Data's.
2. **The report's K, not the survey's.** `dataviews.result(view, lang, k=report K)`: a report has
   its own threshold; any other reader of a view keeps `k_for_survey`.
3. **Reports draw, Data computes.** `_view_payload` adds only presentation: the table rows zipped
   with their cells, bar heights as percentages of the busiest period. No count is produced in
   `reports/`.
4. **Marks are a per-block switch in `config`** (`{"marks": true}`), off by default, with a
   sentence in the editor that says what it means. The payload is geometry only — no answer id, no
   session, no sub-answers, no popups. The exception is written into `public-aggregates` rather
   than left as a contradiction between two specs.
5. **Tokens, not a number-binding UI.** `{responses}` in the text is typed like any word, survives
   copy-paste and the report file, and needs no editor widget. `reports.tokens.Tokens` computes
   lazily and once per render; every value passes `mask`. A token that cannot be filled is left as
   written so the author sees it. A frozen snapshot stores the filled text and the filled opening
   paragraph.
6. **The engagement series is CSS bars**, no chart library call: three numbers and a strip is what
   the hand-made reports show, and it prints.

## Risks / Trade-offs

- [Marks can identify a home] → the default is the grid; the switch names the risk; the decision
  and the responsibility are the survey owner's by the owner's ruling.
- [A token in a report without a home survey] → left as written; the editor shows the token help
  only when there is a home survey.
- [Deleting a view block leaves its view in Data] → harmless and reusable; `delete_view` there
  works once nothing uses it.

## Migration Plan

`reports/0004`: choices only. Rollback: revert.
