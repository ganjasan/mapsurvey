# Tasks — star display style for rating questions

## 1. Model and resolution

- [x] 1.1 `DISPLAY_STYLE_CHOICES` gains `('stars', 'Stars')`; `get_default_rating_display_style`
      accepts it.
- [x] 1.2 `Question.star_icon()` / `Question.star_color()` resolving defaults (`fas fa-star`,
      `#f5b301`, treating `#000000` as unset).

## 2. Render

- [x] 2.1 `CHOICE_BASED_STYLES` gains `stars` in `forms.py` and `question_utils.py`.
- [x] 2.2 Rating field builder passes resolved icon/colour onto the widget for the star style.
- [x] 2.3 `partials/rating_stars.html`: radios + icons, rtl flex, aria-labels.
- [x] 2.4 Wire into `survey_section_partial.html` and `question_preview_frame.html`.
- [x] 2.5 CSS block in `survey/assets/css/main.css` (fill-up-to-checked, hover preview,
      per-question colour via inline custom property); collectstatic.

      Two specificity traps found in the browser, not by the tests: the shared
      `.question-card label:has(input[type="radio"])` rule out-specifies a bare
      `.rating-stars__star`, so every unselected star rendered as body text; and the same rule
      dresses labels as 44px pills with 40px of left padding, which stretched each star to 86px
      and pushed the fifth outside the card. Both fixed by scoping under `.question-card--scale`
      (the convention the scale-strip block already uses) and resetting the box.

## 3. Editor

- [x] 3.1 Third "Display as" thumbnail (stars).
- [x] 3.2 "Number of stars" spinner, visible only for the stars style, rewriting choice rows to
      `1..N` and preserving typed names.
- [x] 3.3 Colour + icon fields visible for rating when the style is stars (extends
      `toggleTypeScopedFields`); hint when the count is long.
- [x] 3.4 Survey-wide default option in `SurveyHeaderForm`.

## 4. Tests

- [x] 4.1 Renders one icon per choice with the resolved icon/colour; defaults are gold stars.
- [x] 4.2 Creator-set icon and colour reach the render.
- [x] 4.3 Storage unchanged: an answer through stars is stored exactly as through the strip;
      switching an existing question to stars leaves answers and export untouched.
- [x] 4.4 Survey-wide default `stars` applies to a question with no style of its own.
- [x] 4.5 Live preview endpoint renders stars for an unsaved draft with posted colour/icon.
- [x] 4.6 `./run_tests.sh survey` green.

## 5. Records

- [x] 5.1 Spec delta for `rating-question-display` (including the two styles that already
      shipped but were never written down).
- [x] 5.2 Backlog note on #102 (presentation-variants slice closed).
- [x] 5.3 Commit, push, PR.
