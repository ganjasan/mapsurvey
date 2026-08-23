# Geo Multi-Feature UX

## Why

One geo question already accepts several features, but nothing in the respondent UI says so:
the draw button looks one-shot, and after the sub-question popup saves, drawing mode ends.
Creators conclude "one button = one pin" and clone the question — production has 189 geo
questions that are ordinal clones ("Mark the 1st/2nd/… location", "n°1…n°12") across 17
surveys where ~20 questions would do, and the worst section holds 14 copies. The cost is
real: 13 clones export as 13 one-feature GeoJSON layers, and every attribute sub-question
must be duplicated per clone. One creator even wrote "You may add multiple markers" in the
question text and still cloned it 13 times — knowledge doesn't survive a UI that contradicts it.

## What Changes

- **Respondent side** (`base_survey_template.html`, `leaflet_draw_button.html`): the draw
  button shows a per-question feature counter chip; after the first feature the button
  re-labels to an "add another" state; each question lists its placed features (with the
  saved sub-answers as a summary line) with re-open-popup and delete controls; saving the
  sub-question popup **re-arms drawing for the same question** instead of ending the flow;
  a question at its max disables its button.
- **Feature count limits**: new per-question `validation_settings.min_features` /
  `max_features` for geo questions (JSONB — no migration). When set, the respondent sees an
  "N of M marked" progress line; max is enforced in the UI and on the server; min is
  enforced on forward navigation alongside `required`.
- **Editor**: the question form modal gains min/max feature inputs for geo question types,
  saved through the existing `vs_*` path in `editor_question_edit`.
- **Not in this change**: the editor-side clone detector / "merge into one question" tool
  and the AI-draft validator rule (follow-ups; this change removes the reason clones get
  created, the detector cleans up after the fact).

## Capabilities

### New Capabilities
- `geo-multi-feature-input`: respondent-side multi-feature affordance and min/max feature
  limits for geo questions (point/line/polygon), including editor configuration.

### Modified Capabilities
<!-- none: openspec/specs/ has no existing capability specs; respondent geo input has no
     spec of record to delta against -->

## Impact

- `survey/templates/base_survey_template.html` — draw-flow JS: re-arm after popup save,
  per-question counters/lists, max enforcement, min validation on submit.
- `survey/templates/leaflet_draw_button.html` — counter chip, progress line, feature list
  containers.
- `survey/assets/css/main.css` — styles for chip, progress, feature list (then collectstatic).
- `survey/templates/editor/partials/question_form_modal.html` — min/max inputs for geo types.
- `survey/editor_views.py` — persist `vs_min_features`/`vs_max_features`.
- `survey/views.py` (or the dynamic form) — server-side min/max check on section POST.
- `survey/tests.py` — editor save round-trip, server-side limit enforcement, rendered
  markup assertions (test client misses HTML5/JS behaviour — assert on markup).
- No DB migration. Existing surveys unaffected: absent keys mean today's behaviour
  (unlimited, no progress UI).
