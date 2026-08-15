# Rework the question type picker — groups, icons, hints, example previews, bigger modal

**Type**: improvement
**Priority**: high
**Area**: frontend
**Created**: 2026-08-09

## Description

`INPUT_TYPE_CHOICES` is a flat list of thirteen entries offered in one undifferentiated dropdown,
and it mixes three genuinely different things:

- **Display blocks** that collect nothing: `image`, `html`. These are not input types at all — a
  respondent cannot answer them — yet they sit in the middle of the list between `polygon` and
  `text_line` as though they were.
- **Ordinary questions**: `text`, `text_line`, `number`, `choice`, `multichoice`, `range`, `rating`,
  `datetime`.
- **Geo questions**: `point`, `line`, `polygon` — the ones that put something on the map, and the
  only ones for which colour and icon mean anything.

The ordering has also drifted: `text_line` ("Single Line Text") sits after `image`, far from `text`,
which it belongs beside.

Grouping them — `<optgroup>` in the dropdown, or a sectioned picker — makes the distinction the
model already relies on visible to the author.

**2026-08-14 — scope widened from "group the dropdown" to a picker rework.** The flat dropdown is
now implicated in a real support case (see Notes), so the ask is bigger than `<optgroup>`:

- **Groups** — display blocks / ordinary questions / geo questions, as above.
- **Icons** — one per type, so the list is scannable; geo types already have canonical FA icons
  (`fa-map-marker-alt`, `fa-route`, `fa-draw-polygon`) in `survey/forms.py`.
- **Short hints** — one line per type stating what the respondent does and what gets stored
  ("Rating — respondent picks one point on a labelled scale").
- **Example preview on hover** — hovering a type shows a rendered mini-example of the respondent
  view. This is the piece that actually fixes the support case: a name plus icon still doesn't tell
  a creator that "rating per item" covers a ranking need, a picture of the widget does.
- **Bigger modal** — the New Question dialog (`survey/templates/editor/partials/question_form_modal.html`,
  rendered into the editor's modal container) is far too small for a sectioned picker with
  previews; move to `modal-lg`/`modal-xl` or a two-pane layout (types left, preview right).

**Interactive mockup**: [question-type-picker.mockup.html](../changes/question-type-picker/question-type-picker.mockup.html)
— all three picker variants (grouped select / card grid / two-pane with preview), three modal
sizes, hover-preview and hide-irrelevant-fields toggles; picking a type rebuilds the form fields.
Lives in the change folder since promotion.

**2026-08-14 — direction chosen** (mockup review): **variant B** — grouped card grid with icons,
in an **1100px** modal, hover flyout showing a canned example per type, irrelevant fields hidden,
plus a persistent **"Respondent sees" pane** on the right that renders the question *as currently
configured* — live from the form values (question text, choices, display style, colour/icon for
geo). The pane, not the flyout, is what tells a creator "rating per item covers my ranking need".
Also decided: rename the `html` type's label to **"Formatted Text"** with a paragraph icon —
survey creators don't know what "HTML" means; the stored `input_type` value stays `html`, so no
migration.

## Notes

- Reported 2026-08-09 alongside
  [Color/Icon/Image shown on every type](bug-question-fields-shown-for-every-type.md): "в списке
  вопросов нет разделения на блоки… на вопросы, которые не вопросы, а просто тексты, картинки,
  видео, звуковые дорожки… на простые вопросы, на гео вопросы."
- **2026-08-14 — discoverability failure in the wild.** Jannis Hamp (jhmp) emailed asking for a
  "ranking" question type ("order the fruits from 1 to 5"), a need that per-item `rating`
  questions already cover — he could not tell from the flat type list. Raised to **high**: the
  picker is now costing us feature-requests for capabilities we already have. See
  `docs/marketing/user-outreach/jhmp/` and the ranking note in
  [additional scale question types](feature-additional-scale-question-types.md).
- Small on its own, but it props up
  [Media upload question type](feature-audio-upload.md) (#41): once video and audio arrive the flat
  list becomes unreadable, and the display-block group is exactly where they belong — as does the
  naming collision noted there, where the existing `image` type *shows* an image rather than
  accepting one.
- The grouping is the natural place to state which types support which settings, which is the same
  information the field-hiding fix carries. Doing them together would be coherent; doing this one
  first would make that fix easier to explain.
- Purely presentational: `INPUT_TYPE_CHOICES` values stay as they are, so no migration and no
  stored data changes.

- **2026-08-15 — promoted and implemented** in change [question-type-picker](../changes/question-type-picker/proposal.md), together with the field-hiding fix from [Color/Icon/Image shown on every type](bug-question-fields-shown-for-every-type.md). Direction B from the mockup: grouped card grid, 1100px modal, hover examples, live "Respondent sees" pane rendering the unsaved draft server-side.
