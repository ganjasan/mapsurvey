## Why

"Create empty" on `/editor/surveys/new/` does nothing until the AI brief is filled in. The
button is a `type="submit"` inside `#create-form`, and the brief's `goal` textarea renders
with the HTML5 `required` attribute, so the browser refuses to submit the whole form and
the POST never leaves the page. The creator gets a native "Please fill out this field"
tooltip pointing at the AI brief — while asking for a survey *without* AI.

This is not theoretical. On 2026-08-19 a creator who had registered three minutes earlier
clicked "Create empty" twice, 28 seconds apart, stayed on the page both times (no
`$pageview` in between — the request never reached the server), then gave up and used the
AI path instead. He ended up deleting the generated draft section by section and left a
thumbs-down on the AI feedback strip on the way out. The one negative AI verdict we have
was cast by someone who did not want AI in the first place.

The server side was never the problem: the `action=empty` branch in `editor_views.py`
requires no brief and creates the survey with a default first section. It is simply
unreachable.

The existing `ai-survey-generation` spec already states that "the existing Create empty
path SHALL remain available and behaviorally unchanged in all cases." The implementation
violates a requirement that was written correctly — so this change tightens the wording to
name the failure mode explicitly and adds the regression test that was missing.

## What Changes

- **`SurveyBriefForm` stops emitting HTML5 `required`** (`use_required_attribute = False`).
  `goal` stays required on the server, where it is already validated — the only thing that
  goes away is the browser-level block that made an unrelated button dead.
- **The "Generate draft" path is unchanged.** An empty `goal` still fails
  `brief_form.is_valid()` in `_start_survey_generation`, which already renders
  `generation_invalid.html` into the status slot with a per-field error list, without a
  page reload. The error moves from a native tooltip to the panel we control — which is
  where the other brief errors already appear.
- **Regression tests** for both directions: "Create empty" with a blank brief creates the
  survey; "Generate draft" with a blank goal still refuses and names the field.

## Impact

- Affected specs: `ai-survey-generation`
- Affected code: `survey/editor_forms.py` (one attribute), `survey/tests.py`
- No migration, no template change, no change to the AI code path itself.
- Ships behind nothing: the manual path becoming reachable cannot break the AI path, and
  the AI path's validation is unchanged and covered by a test.
