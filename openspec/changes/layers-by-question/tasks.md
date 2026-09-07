# Tasks — layers-by-question

## 0. Prerequisites
- [ ] 0.1 Archive `overlay-features` and `respondent-shared-map` (sync their deltas into main
      specs) — this change's MODIFIED requirements need them there
- [ ] 0.2 Owner decisions on the two open questions in design.md (type name; legend line
      for "Marks" layers)

## 0b. Bugs found while testing (owner: they ride this branch)
- [x] Response table empty on a draft copy: columns keyed on the lineage representative
      (`_get_ordered_questions`), delta spec `responses-overview`

- [x] Objects questions have no response-table column (always empty)
- [x] Duration from the session row: `last_activity_at` (section submit, page-leave beacon),
      `end_datetime` (thanks page), migration 0075 backfills from events; export/import carry it

- [x] Deleting a question did not refresh the preview (empty HTMX response): `HX-Trigger`
- [x] Source geo question undeletable behind an orphaned "Marks" layer: refuse only while an
      Objects question shows it; orphaned question-layers go with their last reader / source

- [x] Stuck editor after a 409 (alert requested while the confirm fades out): dialogs queue
      behind a closing one (`editor_dialog.js`)
- [x] Source-question refusal counts readers of the same header only; the layer is kept while
      any header shows it; nameless legend line falls back to the layer name

- [x] "Respondent sees" ignored the picked layer / panel mode; Tips block for the type
- [x] Sub-question added or deleted inside the modal did not reach the section row (OOB replace)
- [x] Autosave did not refresh the Live preview (`questionSaved` from editor_autosave.js)

- [x] Row buttons dead after any autosave (outerHTML replacement bypassed htmx): `htmx.process`
      on the fresh row; sub-question autosave answers with the parent's row, forms target
      `#questions-list > [data-question-id=parent]`

- [x] Closing the modal deleted a configured but unnamed Objects question: only an empty draft
      goes (`if_empty`), and a layer pick names an unnamed question after the layer

- [x] Sub-question adder (chips vs button) depended on the type picked FIRST: both are in the
      markup, toggled by the current type like the block title

- [x] Production follow-up (2026-09-07): marks layers created before #160 never materialised
      ("0 features" next to 28 answers) → migration 0077 backfills every empty question layer;
      0074's raw layer names on Objects questions → `layers.default_question_name`
      ("Existing dog bins", "Other respondents' marks"), also used by the picker's auto-name

## 1. Model
- [x] 1.1 `Question.panel_mode` (`list`/`legend`, default `list`) + migration
- [x] 1.2 `Question.collects_objects` property (layer_objects with ≥1 sub-question)
- [x] 1.3 Data migration: Objects question per (map section × visible unbound layer), across
      canonical / versions / draft copies; idempotent; historical-model `layer_owner`
- [ ] 1.4 (next release) migration dropping `SurveySection.hidden_layers`

## 2. Server
- [x] 2.1 `layers.section_layers(section)`; `build_map_layers_metadata(survey, section=None)`
      returns bound layers only when a section is given, with question id + panel_mode
- [x] 2.2 Respondent page, editor preview pass the section; Responses map passes none
- [x] 2.3 `QuestionForm`: one layer per section (D4); hide/ignore `min_objects` without
      sub-questions; `panel_mode` radio
- [x] 2.4 Everything that counts object answers reads `collects_objects`: answered state,
      `min_objects` validation, progress, results table, export sheet, public block
- [x] 2.5 Section form: remove the checklist and `reference_layers_submitted` handling; layout
      help text
- [x] 2.6 Serialization: stop writing `hidden_layers`; convert it on import (D6) via the pure
      helper shared with 1.3
- [x] 2.7 `cloning.py`: intra-survey copy keeps the binding; cross-survey paste drops it (verify,
      already the rule)
- [x] 2.8 Layer card in Survey settings: "shown in: <sections>"; delete refusal names sections

## 3. Respondent
- [x] 3.1 `reference_layers.html`: drop `data-hidden-layers`; render from per-section metadata
- [x] 3.2 `layer_objects_block.html`: `legend` mode line (swatch/rule legend, name, count,
      toggle synced with the layers control); `list` mode unchanged
- [x] 3.3 No counter / answered chip for display-only questions

## 4. Editor
- [x] 4.0 Objects settings block rebuilt per direction A of `mockups/Main.dc.html` (owner pick
      2026-09-07): one card — layer + "Upload new…", segmented panel mode with per-mode help,
      search only for list, minimum inside "Ask about each object", status pill
- [ ] 4.1 Objects form: "Upload a new layer…" entry (D7) reusing the settings upload flow
- [x] 4.2 Section question list row: panel mode word next to the layer badge
- [x] 4.3 Type picker hint copy for "Objects on the map" (per 0.2)

- [x] 4.4 "Respondent sees" draws the panel like direction B: real objects, category chips,
      tallies on shared-map layers (`layers.preview_panel`, editor previews only)

## 4b. Sharing per sub-question + quick-add (owner 2026-09-07, journey.md)
- [x] `Question.share_with_respondents` + migration 0076 seeding from layer flags
- [x] `layers.shared_kinds`, tallies/comments for any layer (metadata, GeoJSON per request, card)
- [x] Source block (label field, approve-first) under the picker; layer tallies/comments settings removed
- [x] "Others see" switches on sub-question rows (`editor_question_share`); checkbox in the sub-question form
- [x] Quick-add chips 👍/👎 · Rating · Comment · Other… (`QUICK_SUBQUESTIONS`)
- [x] Serialization + cloning carry the flag; legacy archives seeded from layer flags
- [ ] (next release) drop `SurveyMapLayer.show_tallies` / `show_comments` with `hidden_layers`

- [x] Export: no objects CSV for display-only questions; layer results GeoJSON aggregates scoped to
      the exported header (draft/version sub-questions no longer add empty columns)
- [x] Live check of sub-question results: uploaded GeoJSON layer + marks layer → respondent
      tallies/comments, Responses per-object table, objects CSVs, results GeoJSON

## 5. Tests (GIVEN / WHEN / THEN)
- [x] 5.1 Metadata per section: bound only, order, Responses map unaffected
- [x] 5.2 Data migration: creates per section × layer, honours `hidden_layers`, skips bound,
      idempotent, walks versions and draft copies
- [x] 5.3 Form: duplicate layer refused; `min_objects` ignored without sub-questions
- [x] 5.4 Display-only question: section submits with nothing answered; no progress step
- [x] 5.5 Import: old archive with/without `hidden_layers`; new archive untouched; export has
      no `hidden_layers` key
- [x] 5.6 Legend mode renders the line; list mode unchanged (template assertions + browser)
- [x] 5.7 Baseline + after-changes full suite

## 6. Ship
- [x] 6.1 Browser pass on the dev stand with the dog-bin survey (both modes, preview, Responses)
- [ ] 6.2 Offer commit / push / PR; PR 2 for 1.4 one release later
