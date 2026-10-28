## 1. Domain rule and model

- [x] 1.1 `survey/other_option.py`: suffix `-other`, `field_name`, `is_other_field`, `other_code`, `other_text`, `clamp_single_other`, `answer_text`, `display`, `export_column`, `export_cell`
- [x] 1.2 `Question.other_choice_code()`, `Answer.other_text()`, `Answer.choice_display()` delegate to the module
- [x] 1.3 Tests (GIVEN/WHEN/THEN): module rules without DB; flag inert on rating; double flag collapses

## 2. Respondent rendering

- [x] 2.1 `forms.py`: `OtherChoiceWidgetMixin` (create_option + option template), `OtherChoiceRadioSelect`, `OtherChoiceCheckboxSelectMultiple`, mixin on `ChoiceDropdownWidget`; `_get_form_from_input_type` uses them; `__init__` and `single_question_form` stamp `other_choice` / `other_value`
- [x] 2.2 Templates: `partials/choice_option_other.html` (wrapper + input, hidden and disabled unless selected); `choice_dropdown.html` wrapper beneath the control and a sync call in `pick()`
- [x] 2.3 `survey/assets/js/other_option.js` (delegated change, DOMContentLoaded, htmx:afterSwap, `window.syncOtherWriteins`); script tag in `base_survey_template.html` and `question_preview_frame.html`; sync calls after restore in `onPopupOpen` and the layer-objects `popupopen`; `collectstatic`
- [x] 2.4 Tests: rendered card carries the input hidden+disabled; prefilled and visible on revisit; dropdown variant renders the wrapper

## 3. Storage and revisit

- [x] 3.1 Top-level save stores `other_text`; section GET adds `initial['<code>-other']`
- [x] 3.2 Geo sub-answers: skip `-other` property keys before the question lookup, attach the text; `existing_geo_answers` branches on input type and emits `<code>-other`
- [x] 3.3 Object answers: `_save_object_answers` skips `-other` codes and attaches the text; `_existing_object_answers` branches on input type and emits `<code>-other`
- [x] 3.4 Tests: all three save paths, tamper (text without the option) and empty write-in; revisit round-trips for section, geo popup and object popup

## 4. Read surfaces

- [x] 4.1 `_answer_cell` returns the export dict for flagged questions on every row (unanswered included); the GeoJSON sub-question loop merges dict cells; per-object CSV verified
- [x] 4.2 `analytics.py`: `_subanswer_display`, `format_session_answers`, `_format_cell` use `Answer.choice_display()`
- [x] 4.3 Tests: CSV column pair, GeoJSON pair, multichoice, unanswered row keeps the column, no flag no column; drawer and table display; `_stats_choices`, public results and object aggregates carry no text

## 5. Editor

- [x] 5.1 `question_form_modal.html`: "Other" column shown for choice/multichoice only; `addChoiceRow(code, name, other)` as a hoisted declaration; exclusive checkbox handler; `serializeChoices` writes `other: true`; reload passes the flag
- [x] 5.2 `editor_views.py`: `_clamp_single_other` applied in `_guard_choice_codes` and in `editor_question_preview_live`
- [x] 5.3 Tests: save keeps one flag; reopen renders the checkbox checked; preview clamps; cloning and ZIP round-trip keep the flag; modal renders for a star-rating question with no choices

## 6. Verify and ship

- [x] 6.1 `./run_tests.sh survey`
- [x] 6.2 Browser on the worktree dev server: card, dropdown, geo popup, object popup, revisit of each, export ZIP, Responses drawer, public results, star-rating modal console clean
- [ ] 6.3 PR, merge; backlog card for the AI schema follow-up; reply to the BC3 creator
