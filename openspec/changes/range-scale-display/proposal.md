## Why

The `range` question renders as a native slider whose labels do not line up with anything. The
endpoint labels sit flush to the element's edges while the thumb is 22px wide, so the positions the
labels point at are positions the thumb can never reach; the tick row above them uses a different
padding again (`main.css:271-287`), so the two rows do not even agree with each other. Intermediate
choices get an anonymous tick and no text at all (`forms.py:52-67`), so on a 9-point named scale
seven of the nine names are invisible to the respondent.

Both were reported by the user who asked for endpoint labels in the first place (backlog #5, shipped)
— the feature landed and still does not read correctly, which is worse than not having shipped it.

The platform already solved this problem, but only for `rating`. That type has two display styles
selected per question via `Question.display_style`, with a survey-wide default: `scale_strip` lays
the choices out as a CSS grid with anchor labels under the ends — aligned, because the cells span
the full width — and `list_pips` gives each choice its own row with the label in full. `list_pips`
is a complete answer to invisible intermediate labels, and it needs no new invention.

`range` was simply left behind. The editor's own "Display as" control even draws the `default`
option as a slider icon, so the UI already thinks in these terms; the control is just gated to
`rating` questions (`question_form_modal.html:213-216`).

## What Changes

- Fix the slider's label and tick alignment so both rows agree with each other and with the
  positions the thumb can actually occupy.
- Offer `range` questions the same "Display as" choice `rating` already has: the slider (default),
  `scale_strip`, or `list_pips`, reusing the existing templates and CSS rather than adding a third
  rendering.
- Ungate the "Display as" control in the question editor for `range`.
- Keep `default` meaning *slider* for `range`. Existing range questions are unaffected unless their
  creator opts into another style.

**No change to what is stored.** The save path branches on `question.input_type`, not on the widget
(`views.py:873-878`), so a `range` answer keeps landing in `Answer.numeric` whichever way it is
rendered. Export, analytics and existing responses are untouched, and a creator can switch styles
mid-survey without splitting their data.

Not in scope: continuous (non-stepped) and vertical scales, and ranking — backlog #102. This change
takes the slice of #102 that falls out of work already done, and leaves the parts that need new
widgets.

## Capabilities

### New Capabilities
- `range-question-display`: how a `range` question is presented to the respondent — the slider's
  geometry and labelling, the set of display styles available to the creator, and which one applies
  when.

### Modified Capabilities

None. `rating`'s display styles are not specified in `openspec/specs/` today, so there is no
existing requirement to amend; this change specifies `range` only and leaves `rating` behaviour
exactly as it is.

## Impact

- `survey/forms.py` — `RangeWidget`, and `_get_form_from_input_type`, which must now know the
  display style to decide the field type.
- `survey/assets/css/main.css` — slider alignment; the rating style blocks are reused unchanged.
- `survey/templates/partials/survey_section_partial.html` — the render branch currently keyed on
  `rating`.
- `survey/templates/editor/partials/question_form_modal.html` — ungate "Display as".
- `survey/models.py` — `display_style` help text, which says "only used by rating questions".
- No migration: `display_style` already exists on `Question` with the values needed.
- Backlog #99 closed; part of #102 closed.
