## Context

`views.section` builds one HTML string per geo / layer-objects question from
`SurveySectionAnswerForm(question=…)` and ships it in `subquestions_forms` (json_script); the
popup builders in `base_survey_template.html` and `layer_objects_block.html` wrap it in a
`<form>` and read and restore answers by field `name`. The section form renders the same form
class through a card loop in `survey_section_partial.html`; the editor preview had a third copy
of that loop.

## Goals / Non-Goals

**Goals:** a sub-question in a popup looks and reads like the same question in the section —
hint, display style, card — for every type a sub-question may be.

**Non-Goals:** the geo save path does not store `ranking` sub-answers (an empty row is written);
that is a separate, pre-existing gap with no production rows, not this change.

## Decisions

- One partial for the field loop, three includers. The alternative (a popup-only template) is the
  drift that produced this bug.
- `render_to_string` without a request: the partial needs no context processors, and running
  them once per geo question per page view would be waste.
- Popup-time init through one function (`initPopupFields`), called after the restore in both
  popups, so the rating chip reflects restored answers. Stars, pips, thumbs and choice styling
  are CSS (`:has(:checked)`) and need nothing.
- Popup styling scoped to `.leaflet-popup-content`; `font-size: 1rem` on every form block but
  `.layer-controls`, whose buttons size off the map font on purpose. Cards keep 4px side padding:
  choice rows bleed 4px out for their hover fill, and with none the popup scrolled sideways on a
  phone.

## Risks / Trade-offs

- Field ids repeat between popups of the same question, as they did with `as_p()`; Leaflet keeps
  one popup in the DOM at a time.
- Verified in a browser on a survey with every input type at top level and every sub-question
  type in both popups: hints grey 13.6 px under 14.7 px titles, no duplicate, answers restored on
  reopen and saved on submit, no JS errors.
