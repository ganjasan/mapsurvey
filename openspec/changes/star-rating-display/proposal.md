# Star display style for rating questions

## Why

A rating question today renders as a compact numbered strip or as a labelled list. Both read as
research instruments. The star rating is the one scale every respondent already understands
without instruction, and it is the shape creators ask for when the question is "how good was
this" rather than "place yourself on this scale".

It also gives the type picker's live preview something to sell: `rating` is the type creators
should reach for when they want a labelled discrete scale (the range/rating split settled in
`range-slider-only`), and stars make that type recognisable at a glance.

## What Changes

- New display style **`stars`** for rating questions: one icon per choice, filled up to the
  respondent's selection, with hover preview. Available per question and as a survey-wide
  default, alongside the existing two styles.
- **Configurable, with sane defaults**: five gold stars out of the box. The creator can change
  the icon (any Font Awesome icon, via the icon picker the dialog already has), the colour (the
  colour picker it already has), and the number of stars.
- **The count is the choice list.** Stars render one icon per choice, exactly as the compact
  strip does, so the underlying data is unchanged. The editor adds a "Number of stars" control
  that writes the choice rows for the creator instead of making them type 1..5 by hand.
- **Colour and icon become visible for rating questions when stars are selected.** This extends
  the per-type field visibility from `question-type-picker` rather than fighting it: the two
  fields appear exactly where they are consumed, which is now geo types *and* star ratings.
- Stored answers are untouched: stars are radio inputs over the same choices, so a rating answer
  keeps landing in `Answer.selected_choices`. Switching an existing rating question to stars
  changes only its appearance. **No migration** — `color` and `icon_class` already exist on
  `Question`, and `display_style` already exists with room for another value.

Not in scope: half stars or fractional ratings; per-choice icons (all stars in one question share
one icon); emoji faces as a distinct style (an icon choice covers it).

## Capabilities

### New Capabilities

- `rating-question-display`: how a `rating` question is presented to the respondent — the
  available display styles, how one is chosen per question and survey-wide, and what a star
  rating is configured from. (Rating's existing two styles were never specified; this change
  writes the capability down, including the behaviour that already shipped.)

## Impact

- `survey/models.py` — `DISPLAY_STYLE_CHOICES` gains `stars`;
  `get_default_rating_display_style` accepts it; a helper resolving the star icon and colour
  (defaults applied where the creator never set them).
- `survey/forms.py` — `CHOICE_BASED_STYLES` gains `stars`; the rating field builder passes icon
  and colour to the widget.
- `survey/templatetags/question_utils.py` — `CHOICE_BASED_STYLES` mirror.
- `survey/templates/partials/rating_stars.html` — new render; wired into
  `survey_section_partial.html` and `question_preview_frame.html`.
- `survey/assets/css/main.css` — star block; collectstatic.
- `survey/editor_forms.py` — survey-wide default gains the option.
- `survey/templates/editor/partials/question_form_modal.html` — third "Display as" thumbnail,
  "Number of stars" control, colour/icon visibility for rating + stars.
- `survey/tests.py` — rendering, defaults, storage-unchanged, count control.
- Backlog: closes the "presentation variants" slice of #102.
