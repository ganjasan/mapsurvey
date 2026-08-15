# Range renders as a slider, only

## Why

`range-scale-display` (merged early August) ungated `rating`'s display styles for `range`
questions, so a creator could render a range as a compact scale or a labelled list. Production
data now says that was the wrong coupling:

- Of 124 range questions, **122 render as the default slider**. The user whose nine-point named
  scale motivated the feature never switched styles.
- The only two non-default range questions belong to jhmp (Jannis Hamp), are named **"Rating"**,
  and use `list_pips` — the one real use of the feature is a creator imitating the `rating` type
  because he could not find it. That is a type-discoverability failure (now addressed by the
  question-type-picker change), not a range-rendering need.
- The creator-facing result is two types that can be configured to look identical while storing
  answers differently (`Answer.numeric` vs a choice code) — a distinction no picker hint can
  explain away while the "Display as" control keeps blurring it.

The taxonomy this change restores: **Range is the slider** — a numeric answer with numeric
validation. A labelled discrete scale is what `rating` is for, and the reworked type picker with
its live preview now actually leads creators there.

## What Changes

- `range` always renders as the slider. The "Display as" control is no longer offered for range
  questions in the editor; `DISPLAY_STYLE_TYPES` is `rating` only, on both sides of the
  form/template contract.
- Stored `display_style` values on range questions are ignored harmlessly (the same pattern the
  feature itself used for its no-choices fallback): the two production questions carrying
  `list_pips` render as sliders again, with stored answers and prepopulation untouched. No
  migration, no data change.
- The slider alignment fix from `range-scale-display` is untouched — it is geometry, not styles.
- `rating` behaviour is untouched, including survey-wide default inheritance.

Out of scope: merging range and rating into one scale type (that is the real long-term answer to
the duplication and belongs to backlog #102's scale-family work); contacting jhmp about his two
questions (his case is `rating`, and he is an active outreach contact).

## Capabilities

### Modified Capabilities

- `range-question-display`: the creator-choice requirement is removed; the capability now pins
  the opposite — a range question renders as the slider regardless of any stored display style.
  (The capability's spec currently lives as the un-archived `range-scale-display` delta; this
  delta supersedes its display-style requirements and keeps its storage and alignment ones.)

## Impact

- `survey/forms.py` — `DISPLAY_STYLE_TYPES`, `resolve_display_style`, the range branch of
  `_get_form_from_input_type` (choice-based-styles path removed).
- `survey/templatetags/question_utils.py` — `SCALE_STYLE_TYPES`.
- `survey/templates/editor/partials/question_form_modal.html` — the JS mirror of
  `DISPLAY_STYLE_TYPES`.
- `survey/tests.py` — `RangeDisplayStyleTest` rewritten to assert slider-always (stored styles
  ignored, storage/prepopulation invariants kept, rating inheritance kept).
- Stacked on `feature/question-type-picker` (PR #60): both changes edit the same form/template
  regions.
