## Why

Point questions are the most-skipped question type: 31.8 % of respondents answer them, against 40–97 % for other types (analysis of 2026-06-10). Respondents click the map first and nothing happens. A customer running a Polish survey reported on 2026-10-07 that testers "immediately tried clicking on the map, not realizing that they need to click the question first". When a page has exactly one geo question, a map click can only mean that question, so making respondents press the button first has no benefit (issue #342, epic #343).

## What Changes

- New per-question setting on `point` questions: **"A tap on the map places a mark"**, stored as `Question.tap_to_place`. It is off by default, so existing surveys behave as they do today.
- The setting takes effect only while the question is the **only top-level geo question** (`point`/`line`/`polygon`/`spraycan`) on its section. A single helper decides this, and both the editor and the respondent page use it.
- Respondent page: with the setting in effect, a click or tap on an empty part of the map places the mark. This goes through the same path as the button + crosshair *Apply*, so the result is the same feature and the same pop-up. The button stays and still works.
- A click is ignored in each of these cases:
  - it lands on a marker, a pop-up, a control or an interactive layer object;
  - a draw, crosshair, spray or edit mode is active;
  - a pop-up is open;
  - the question has reached `max_features`;
  - the question is hidden by a visibility rule;
  - it is part of a double-click or double-tap. Double-tap zoom never places a mark.
- Respondent panel hint under the button: "Tap the map to mark a place — or use the button."
- Editor:
  - a switch in the point question's settings, with the note "Works only while this is the only map question on its page";
  - a "tap to place" badge on the question row, which turns grey with a reason in its tooltip when another geo question shares the section.
- The setting is travelling data:
  - it rides the survey ZIP export/import, duplication and draft copies;
  - AI-generated drafts default it to off;
  - on a live survey it is a safe in-place edit, not a structural one.
- The setting does not apply to `line`, `polygon` or `spraycan`, because drawing those needs a mode.

## Capabilities

### New Capabilities
- `point-tap-to-place`: a per-question setting that lets a map click place a point mark when the question is the only geo question on its section. Covers the editor control, the eligibility rule, respondent behaviour and persistence.

### Modified Capabilities
<!-- none: the crosshair flow (mobile-point-crosshair) and multi-feature caps (geo-multi-feature-input) are unchanged; this change adds a second entry point that reuses them -->

## Impact

- **Model**: `Question.tap_to_place` BooleanField with a migration (additive, default False).
- **Server**:
  - `survey/question_types.py`: eligibility helper;
  - `survey/forms.py`: the respondent button carries `data-tap-to-place`;
  - `survey/editor_forms.py` and `survey/editor_views.py`: field and save;
  - `survey/serialization.py`: export/import;
  - `survey/ai/materialize.py`: default.
- **Templates/JS**:
  - `leaflet_draw_button.html`: data attribute and hint;
  - `base_survey_template.html`: map click handler;
  - `editor/partials/question_form_modal.html`: the switch;
  - `editor/partials/question_list_item.html`: the badge.
- **Tests**: `survey/tests.py`.
- **No API or URL changes.** Rollback is to leave the setting off.
