# Design: Rating Question Display Style

## Context

Rating questions render as `forms.ChoiceField(widget=RadioSelect)` (`survey/forms.py:212`). The section template wraps card questions and adds a `question-card--rating` modifier (`survey/templates/partials/survey_section_partial.html:40`); CSS in `survey/assets/css/main.css` (lines ~318–382) turns the radio labels into flex-wrap pill buttons. Worded 5-point scales break into ragged 2-2-1 rows in the 420px panel.

The approved mockup (`rating-question.mockup.html` in this folder) defines two replacement renderers:

- **`scale_strip`** (variant B, default): grid row of equal numbered cells, anchor labels (first/last option text) under the row, selected option's full label shown as a chip below the anchors.
- **`list_pips`** (variant C): vertical list of full-width option rows, each with a right-aligned pip indicator (n of N dots filled).

Both keep radio semantics — same POST data, same `Answer` storage, no scoring changes.

## Goals / Non-Goals

**Goals:**
- Per-question choice of renderer, editable in the WYSIWYG editor, persisted on `Question`.
- Replace the flex-wrap pill rendering entirely; existing questions silently get `scale_strip`.
- Round-trip through serialization export/import and survive versioning draft clone and editor copy/paste.
- Answer prepopulation (back-navigation) must restore the visual state in both renderers.

**Non-Goals:**
- Rating questions used as **sub-questions** in geo popups keep their current default radio rendering (popup forms render via `.as_p()`, out of scope here).
- No changes to other input types (`choice`, `range`, …) and no generic "display settings" framework — one CharField is enough until a second type needs it.
- No analytics changes: stored answer codes are unchanged.

## Decisions

**D1 — `Question.display_style` CharField, not JSON.**
`CharField(max_length=20, choices=[('scale_strip', …), ('list_pips', …)], default='scale_strip')`. A generic `display_settings` JSONField was considered and rejected (YAGNI, weaker validation, harder editor form binding). Field is ignored for non-rating types. One additive migration (leaf after `0036_merge_20260723_0838`; per parallel-worktree convention, re-check the leaf before merging the PR).

**D2 — Markup lives in the section template, not in custom widget classes.**
The form keeps a plain `RadioSelect`; `SurveySectionAnswerForm.__init__` sets `widget.display_style = question.display_style` alongside the existing `widget.question_type` (never `widget.input_type` — reserved). The section partial branches on a new `rating_display_style` template filter and iterates `{% for radio in field %}` inside two new sub-partials:
- `partials/rating_scale_strip.html` — cells with the option index, `data-label` with translated option name; anchors row from `field.field.choices` first/last; empty chip container.
- `partials/rating_list_pips.html` — option rows; pips rendered from `forloop.counter` / total.

Alternative — custom widget `template_name` — rejected: requires switching `FORM_RENDERER` to `TemplatesSetting` project-wide, more moving parts for the same DOM. The template already special-cases card questions, so branching there is consistent with existing structure.

**D3 — CSS replaces the old block; card modifier per style.**
`.question-card--rating` flex-wrap rules are deleted and replaced by `.rating-scale-strip` and `.rating-list-pips` blocks copied from the mockup (adapted to Django's radio DOM). Cell count is variable: the strip uses `grid-template-columns: repeat(<n>, 1fr)` via an inline style from the template (supports 7+ point scales). Edit in `survey/assets/css/`, then `collectstatic`.

**D4 — Minimal JS only for the scale strip chip.**
A small delegated script in `survey_section.html`: on `change` of a strip radio, copy its `data-label` into the chip; on load, do the same for a pre-checked radio (covers back-navigation prepopulation). `list_pips` is pure CSS via `:checked`/`:has()` (already used by current CSS, so browser support is unchanged). No framework, consistent with existing vanilla JS.

**D5 — Editor picker as a per-type block in the question modal.**
Add `display_style` to `QuestionForm.fields` (`survey/editor_forms.py:67`) rendered as two radio options with mini-previews (static inline SVG/CSS thumbnails, mirroring the mockup look). The block is shown/hidden by the same JS that toggles type-specific blocks in `question_form_modal.html` (visible only for `rating`). Saving reloads the live preview iframe — no extra wiring.

**D6 — Serialization is backward-compatible.**
Export adds `"display_style"` to the question dict in `survey/serialization.py` (next to `icon_class`, line ~110). Import reads `question_data.get("display_style", "scale_strip")` and validates against the two allowed values, falling back to the default on garbage — old archives and hand-edited files import cleanly.

**D7 — Cloning covered in one place.**
`clone_question()` in `survey/cloning.py` (explicit field list, line ~54) gains `display_style=question.display_style`. That single change covers versioning draft clones, editor duplicate, and copy/paste.

## Risks / Trade-offs

- **[Appearance of published surveys changes on deploy]** — intended: `scale_strip` replaces the broken pills everywhere. Creators who prefer words-always-visible switch to `list_pips` per question. No respondent data impact.
- **[Numbered cells can read as "grades" and bias answers]** → anchors + selected-label chip mitigate; creators can choose `list_pips`; documented in the editor picker labels.
- **[Rating sub-questions in geo popups still render as bare radios]** → unchanged from today; explicitly out of scope (noted as a possible follow-up).
- **[Django's RadioSelect DOM differs from the hand-written mockup DOM]** → sub-partials iterate `BoundField`/`BoundWidget` and emit their own markup, so CSS from the mockup is adapted once; covered by template tests.
- **[Migration number collision with parallel worktrees]** → additive single migration; verify leaf before merge (per project convention).

## Migration Plan

1. Additive migration (new field with default) — safe to deploy with old code running; no data backfill.
2. Deploy code + `collectstatic`.
3. Rollback = revert deploy; the extra DB column is inert for old code.

## Open Questions

None — default (`scale_strip`) and the two variants were confirmed by the user against the mockup.

## Amendment (после первой ревизии в редакторе)

**D8 — Survey-level default via `SurveyHeader.style_settings` JSONField.**
The user wants a survey-wide default style and, later, more appearance settings (fonts, palettes, sidebar position). A JSON container `style_settings` (default `{}`) with key `rating_display_style` avoids a migration per future setting. Reader helper `SurveyHeader.get_default_rating_display_style()` validates the value and falls back to `scale_strip`. Future settings are a follow-up change, not this one.

**D9 — `Question.display_style` becomes three-valued; `default` inherits.**
Values: `default` (new model default), `scale_strip`, `list_pips`. Effective style resolution happens once, in `SurveySectionAnswerForm.__init__`, which stamps the resolved value onto the widget — templates keep branching on two visual styles only. Migration 0037 is regenerated in place (branch not shared yet) to add both fields.

**D10 — Modal preview must show the real renderer and react to the picker.**
`question_preview_frame.html` duplicated the old card branch and never knew about display styles. Fix: reuse the same rating branch/partials as the section template, and let `editor_question_preview` accept a validated `?display_style=` override so the modal JS can reload the iframe on every picker change — preview reflects the choice before saving. Drive-by fix included: the modal IIFE's "populate existing choices" block ran before `window.addChoiceRow`/`serializeChoices` were assigned, killing the script when editing any question with choices (pre-existing on master; it also broke Apply-refresh of this very preview). The block moves to the end of the IIFE.

**Investigated — "changing one question changes all":** the save path (`editor_question_edit`) writes a single instance and section rendering resolves style per question (verified live: mixed styles on one page). The report traced back to the broken modal preview masking what was saved. Pinned with regression tests: mixed styles render independently; editing one question's style leaves siblings untouched.
