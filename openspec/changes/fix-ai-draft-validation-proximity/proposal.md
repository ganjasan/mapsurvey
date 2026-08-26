## Why

On `/editor/surveys/create/`, clicking "Draft my survey" with an empty goal renders the
validation error as a summary banner in `#generation-slot` — at the bottom of the left
column, far below the field that caused it. The empty field itself is not highlighted in
any way, so the creator has to read the banner, parse the field label out of "What do you
want to find out?: This field is required.", and scroll back up to find it. Errors should
appear at (or as close as possible to) their source, and the offending field should be
visibly marked. (The mobile wizard already does the highlight-in-place half of this for
the goal field in `wizardNext('draft')`; the desktop HTMX path has nothing.)

A second, related confusion on the same screen: in the mobile wizard the step-1 primary
button says "✨ Draft my survey", which reads as "the survey will be created now" — but it
actually advances to the map step, where a separate "✨ Create draft survey" button
submits. The step-1 copy must communicate that a next step follows.

## What Changes

- The HTMX validation-failure response for the generate action carries per-field errors,
  and client-side handling marks each offending brief/create field in place: red border
  on the input plus an inline message directly under it (e.g. "This field is required.").
- Fields inside the collapsed "Add details (optional)" disclosure that carry an error
  force the disclosure open, so an error is never hidden.
- The first offending field is scrolled into view / focused, so the creator lands on the
  source rather than on a banner below the fold.
- The bottom summary banner ("Check the form before generating a draft.") is dropped for
  field-level validation errors; non-field failures (provider not configured) keep their
  existing `#generation-slot` presentation.
- Inline error marks are cleared when the creator edits the field or re-submits.
- The mobile wizard step-1 draft button copy changes to signal a next step (e.g.
  "✨ Next — choose the place") instead of implying immediate creation; the map-step
  submit button keeps its "✨ Create draft survey" copy.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `ai-survey-generation`: adds a requirement that generate-action validation failures are
  presented at the field level (in-place highlight + adjacent message, disclosure forced
  open, first error focused) instead of a detached summary banner at the bottom of the
  column; and that the mobile wizard step-1 draft button copy communicates a following
  step rather than immediate creation.
- `survey-editor`: the "Survey creation" requirement's wizard-draft-path scenario quotes
  the step-1 button copy — updated to the new label.

## Impact

- `survey/editor_views.py` — `_start_survey_generation` invalid branch: return structured
  per-field errors instead of a flat label-prefixed list.
- `survey/templates/editor/partials/generation_invalid.html` — repurposed/simplified for
  non-field failures.
- `survey/templates/editor/survey_create.html` — client-side handling that applies/clears
  field highlights and inline messages, opens the disclosure, focuses the first error.
- `survey/tests.py` — tests for the invalid-generate response shape and rendered markup.
