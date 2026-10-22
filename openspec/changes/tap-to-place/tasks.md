## 1. Model and rule

- [x] 1.1 Add `Question.tap_to_place` BooleanField(default=False) + migration
- [x] 1.2 Add `question_types.tap_to_place_active(question, section_geo_count)` and a section geo-count helper

## 2. Editor

- [x] 2.1 `QuestionForm`: field, label, checkbox widget, `clean_tap_to_place` (point + top-level only)
- [x] 2.2 Question modal: switch + note, shown only for `point` via the type → field table
- [x] 2.3 Live preview (`editor_question_preview_live`) passes the field through
- [x] 2.4 Question row badge "tap to place", greyed with tooltip when not in effect

## 3. Persistence

- [x] 3.1 ZIP export writes `tap_to_place`; import reads it (missing → False)
- [x] 3.2 AI materialize default False

## 4. Respondent

- [x] 4.1 `forms.py` passes `tap_to_place` to the point button only when the rule holds; `leaflet_draw_button.html` renders `data-tap-to-place` and the hint
- [x] 4.2 `base_survey_template.html`: map click handler (guards, preclick popup check, dblclick-cancelled delay, fires `draw:created` like crosshair Apply)
- [x] 4.3 Hint string through `{% trans %}` (no catalog edit: recent respondent strings, e.g. spraycan, are untranslated too)

## 5. Verification

- [x] 5.1 Tests (GIVEN/WHEN/THEN): default off; non-point forced off; rule with 1 vs 2 geo questions and sub-questions; respondent HTML attribute + hint present/absent; ZIP round trip and old archive; live-survey toggle is in place
- [x] 5.2 Browser check on the dev server: tap places + pop-up, double-click zoom no mark, cap, second geo question disables, button still works
- [x] 5.3 Changelog entry `survey/changelog/<date>-tap-to-place.html`
- [x] 5.4 Owner review: marks placed with the button could not be opened. A question without `icon_class` passes `data-icon=""`, and `L.Icon.FontAwesome` given no class draws an empty clickable icon while the pin shows only in the non-interactive shadow pane. The bug predates this change; with tap-to-place on, a click on such a pin even dropped a second mark. Fixed in two places: `_newPointMarker` defaults the icon and colour (as restore and Edit already did), and the tap handler ignores clicks on `.leaflet-fa-markers`.
