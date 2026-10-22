## Context

The respondent places a point today in two steps. First the draw button (`.drawpoint`) shows the crosshair overlay. Then *Apply* builds an `L.marker` and fires `draw:created`. A persistent `draw:created` handler in `base_survey_template.html` reads `currentQ`, binds the sub-question pop-up and adds the marker to `editableLayers`. `refreshGeoQuestionUI` derives counts, caps and the button's disabled state from `editableLayers`. A click on the map itself has no listener, which is the dead click from issue #342.

Per-question settings live in two places:
- `validation_settings` (JSON). It does NOT ride the survey ZIP.
- Dedicated columns such as `spray_brush`, which do ride the ZIP.

## Goals / Non-Goals

**Goals:**
- One more entry point into the existing point flow, with zero divergence from the button: same marker, same pop-up, same caps.
- Editor and respondent decide eligibility through one rule.

**Non-Goals:**
- Tap-to-draw for lines, polygons or spray, because those need a mode.
- Choosing among several geo questions on one page. That is ambiguous by definition, and the epic's place-types-in-popup questions address it.
- Changing the crosshair flow.

## Decisions

1. **A column, not `validation_settings`.** The field is `Question.tap_to_place = BooleanField(default=False)`. `validation_settings` does not ride the ZIP, and the setting must survive export, import and AI materialisation, as `spray_brush` does. Cloning and draft copies copy every column, so they need no code.

2. **One eligibility helper**: `question_types.tap_to_place_active(question, section_geo_count)`. It is true when the question is top-level, is `point`, has `tap_to_place` set, and the section's top-level geo-question count is 1. The count comes from `section.question_set.filter(parent_question_id=None, input_type__in=GEO_TYPES).count()`.
   - The respondent form already iterates the section's questions, so it counts them once.
   - The editor's list rendering counts per section once, through a `geo_count` passed into the row context or computed by a template filter on the section.
   - The rule is static and ignores whether another geo question is currently hidden by a visibility rule. A hidden second question is still "another map question on this page" to the creator, and a static rule keeps the editor badge truthful.

3. **The server says so, and the JS obeys.** The respondent button gets `data-tap-to-place="1"` only when the helper is true, and the hint is rendered only then. The browser does not re-count geo questions.

4. **Respondent click path.** `map.on('click')` finds `button.drawpoint[data-tap-to-place]` in `#info_page`. It does nothing in any of these cases:
   - there is no such button, or the button is disabled (cap reached);
   - the button sits inside a hidden or disabled question card (visibility rule; checked through the geo input's `disabled` attribute, as the required check does);
   - `spray.active`, `currentDrawFeature`, `currentEditLayer` or the crosshair overlay is visible;
   - a pop-up was open at `preclick`;
   - the click target is inside `.leaflet-marker-icon`, `.leaflet-popup` or `.leaflet-control`.

   Otherwise the handler waits 300 ms, which a `dblclick` cancels. It then sets `currentQ`, hides the panel exactly as the button does, builds the marker with the button's `data-color`/`data-icon` and fires `draw:created`, the same call crosshair *Apply* makes.
   - In Leaflet 1.4, an interactive layer that listens for clicks swallows the map click (`_findEventTargets`), so layer objects and markers need no extra code. The DOM check is a backstop for canvases and controls.
   - The pop-up check happens at `preclick` because Leaflet closes pop-ups at `preclick`; by `click` the pop-up is already gone.
   - Alternative considered: placing on `mouseup` without a delay. Rejected, because every double-tap zoom would drop a mark.

5. **Editor.**
   - The switch is a checkbox `tap_to_place` in `QuestionForm`. It is shown only for `point` and hidden by the modal's existing type → field `show()` table.
   - `clean_tap_to_place` forces false unless `input_type == 'point'` and the question is top-level.
   - Not structural in `versioning.py`, which needs no code because only listed fields are structural.
   - The live preview passes the field through, so the preview button carries the attribute too.

## Risks / Trade-offs

- [Risk] The 300 ms delay makes a tapped mark feel slightly slower than an instant one. → Mitigation: it is the standard double-tap window, and the pop-up opening is the feedback.
- [Risk] A respondent who meant to pan with a short tap gets a mark. → Mitigation: Leaflet does not fire `click` after a drag. A stray mark has Delete in its pop-up, and the setting is opt-in per question.
- [Risk] A creator turns the setting on and later adds a second geo question, and the setting silently stops working. → Mitigation: the grey badge and the tooltip name the reason. Spec scenario.

## Migration Plan

An additive migration with default False, so no data step is needed. Rollback: switch the setting off per question. Reverting the code leaves an unused column.
