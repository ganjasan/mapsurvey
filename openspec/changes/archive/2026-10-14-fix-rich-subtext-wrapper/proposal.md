## Why

A geo question whose help text was written in the rich-text editor shows the hint twice on its
draw button: once grey, once black and larger than the question title (#315). Since creator prose
became rich text, `Question.subtext` is HTML (`<p>…</p>`), and five respondent/preview templates
still wrap it in a `<p>`. A paragraph cannot contain a paragraph, so the browser closes the styled
wrapper empty and the creator's paragraph lands beside it unstyled. On the draw button the
multi-feature script then re-fills the empty wrapper from `data-orig-subtitle`, which is the
second copy. On card questions and image captions there is no duplicate, but the hint loses its
grey, small style on every question that has a rich-text hint.

## What Changes

- The wrappers around creator rich text become block containers (`<div>`) in
  `leaflet_draw_button.html`, `partials/survey_section_partial.html` (both card branches),
  `editor/partials/question_preview_frame.html` (both branches) and `show_image.html`.
- The creator's own paragraphs inside those wrappers lose their default margins, so a one-line
  hint looks the same as the old plain-text one.
- A test renders a section with one question of every type that shows a hint, using a rich-text
  hint, and checks that the hint sits inside its styled wrapper exactly once.

## Capabilities

### New Capabilities

### Modified Capabilities
- `question-subtext`: adds the requirement that a rich-text hint renders once, inside its styled
  wrapper, on every surface that shows it.

## Impact

Templates only (five files) plus `survey/assets/css/main.css`. No model, migration or JS change.
