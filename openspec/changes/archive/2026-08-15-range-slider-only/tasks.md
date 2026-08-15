# Tasks — range renders as a slider, only

## 1. Decouple

- [x] 1.1 `survey/forms.py`: `DISPLAY_STYLE_TYPES = ('rating',)`; drop the range branch from
      `resolve_display_style` (falls through the not-in-types check); remove the
      choice-based-styles path from the range field builder.
- [x] 1.2 `survey/templatetags/question_utils.py`: `SCALE_STYLE_TYPES = {'rating'}`.
- [x] 1.3 `question_form_modal.html`: JS `DISPLAY_STYLE_TYPES = ['rating']`.

## 2. Tests

- [x] 2.1 Rewrite `RangeDisplayStyleTest`: slider renders whatever style is stored (incl. the
      prod-shaped `list_pips` case), storage stays numeric, prepopulation works, rating still
      inherits the survey default, live-preview endpoint ignores a posted style for range.
- [x] 2.2 `./run_tests.sh survey` green.

## 3. Records

- [x] 3.1 Spec delta: remove the creator-choice requirement from `range-question-display`, add
      the slider-always requirement.
- [x] 3.2 Backlog: note the retirement in `feature-additional-scale-question-types.md`.
- [x] 3.3 Commit, push, PR stacked on `feature/question-type-picker`.
