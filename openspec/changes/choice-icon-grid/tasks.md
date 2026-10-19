## 1. One display-style table

- [x] 1.1 Add `DISPLAY_STYLES_BY_TYPE` and `allowed_display_styles(input_type)` to `survey/question_types.py` (rating / choice / multichoice per design D5)
- [x] 1.2 Add `('icon_grid', 'Icon grid')` to `DISPLAY_STYLE_CHOICES`, update the field's help_text, generate the AlterField migration (check `origin/master` for a parallel migration number first)
- [x] 1.3 Point `SurveySectionAnswerForm.DISPLAY_STYLE_TYPES` / `STYLES_BY_TYPE` / `resolve_display_style` at the table
- [x] 1.4 Point `QuestionForm.clean()` (`editor_forms.py`), `editor_question_preview_live`, the saved-question preview's `display_style` override and `serialization._import_question` at the table
- [x] 1.5 Tests: a stored style on the wrong type falls back (dropdown on multichoice, icon_grid on text); every caller accepts `icon_grid` for choice and multichoice

## 2. Choice extras (`icon`, `group`)

- [x] 2.1 `normalise_choice_extras(choices)`: trim, drop blank/non-string, cap group 60 / icon 64, keep other keys and order
- [x] 2.2 Call it wherever `choices_json` is parsed (create, edit, autosave, live preview) and in ZIP import
- [x] 2.3 `marker_icons.is_drawable(value)` (the existing `is_known` means "catalogued"): true for a catalogued map-set name or any Font Awesome class form, false for an unknown `set:name` or blank
- [x] 2.4 Tests: keys stored when set, absent when blank, export CSV unchanged, ZIP round-trip identical, pre-change archive imports identically

## 3. Respondent widget

- [x] 3.1 `ChoiceIconGridRadio` and `ChoiceIconGridCheckbox` in `survey/forms.py` (with `OtherChoiceWidgetMixin`); `create_option` adds `icon` (only if known) and `group`; `get_context` builds consecutive group runs
- [x] 3.2 Wire them in `_get_form_from_input_type` for `choice` and `multichoice` when the resolved style is `icon_grid`
- [x] 3.3 Template `choice_icon_grid.html`: runs → optional escaped heading → tiles (label wraps hidden-but-focusable input, `{% marker_icon %}`, 2-line clamped label with `title`); `cig-tile--on` on checked; write-in input once under the grid; `data-cig-collapse` and "Show all options" button for choice only
- [x] 3.4 CSS in `main.css` (tile min width ≈84 px, wrap, highlight via `:has()` + `cig-tile--on`, collapsed state hides off-row tiles and other runs' headings); accent colour in `base_survey_template.html` like the dropdown
- [x] 3.5 Once-bound delegated script: toggle `cig-tile--on`; on change of a collapsible grid measure rows by `offsetTop`, mark off-row tiles, set `cig-collapsed`; "Show all" expands; collapse prefilled grids on `DOMContentLoaded` and when a pop-up opens (find the respondent map's popup-open path; fallback `focusin`/`pointerenter`); recompute on resize; unmeasurable ⇒ stay expanded
- [x] 3.6 Bump the preview frame's Font Awesome link to the catalog version (5.15.4)
- [x] 3.7 Tests: tile per option in order, same POST value as the list, multichoice stores both codes, required error, known icon renders sprite, unknown icon renders none, three groups → three headings, no groups → no heading, group escaped, collapse markup only on choice, write-in field rendered once and stored, preview_live renders the grid

## 4. Editor

- [x] 4.1 Display as: Icon grid card with a mini-tile thumb (`data-types="choice multichoice"`), List card also for multichoice, JS `DISPLAY_STYLE_TYPES` gains `multichoice`, card filter by token membership
- [x] 4.2 Choices table: Icon and Group header/row cells, `choices-editor--grid` toggled by the checked style, values kept when hidden
- [x] 4.3 `IconPicker.attach` on every row's icon input, including rows added later and rows rebuilt from existing choices
- [x] 4.4 `serializeChoices()` writes `icon`/`group` only when non-empty; row builder reads them back from existing choices
- [x] 4.5 Live preview reacts to style and to icon/group edits (schedulePreview)
- [x] 4.6 Tests: modal renders the card for multichoice, saving `icon_grid` persists, choices_json with icon/group persists

## 5. AI generation, changelog, docs

- [x] 5.1 (no-op: survey/ai has no display_style or choice-key enumeration) If the AI schema/prompt enumerates `display_style` or choice keys, add `icon_grid` and `icon`/`group` with an example
- [x] 5.2 Changelog entry `survey/changelog/<date>-icon-grid.html` (kind: new)
- [x] 5.3 CLAUDE.md: one paragraph on the display-style table and the choice extras

## 6. Verify

- [ ] 6.1 `./run_tests.sh survey` baseline before and once after; summarise the delta
- [x] 6.2 Browser check on the dev server: 17 options with icons and three groups in a point pop-up on a phone width and in "Respondent sees"; pick collapses to the row, "Show all" expands, multichoice stays open
- [x] 6.3 `openspec validate choice-icon-grid --strict`
