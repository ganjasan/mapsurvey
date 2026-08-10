# Color, Icon and Image are offered on every question type, and do nothing on most

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-08-09

## Description

The question editor shows **Color**, **Icon class** and **Image** for every `input_type`. All three
are consumed by only a subset, so on a text, number, choice or rating question they are dead
controls presented as live ones.

Traced through the code:

- **Color** — read once (`forms.py:299`) and passed only into `LeafletDrawButtonField` for
  `point` / `line` / `polygon` (`forms.py:253, 257, 261`). No respondent-facing template, analytics
  view or map layer reads `question.color` for anything else.
- **Icon class** — same, geo only. The field's own placeholder gives it away: it suggests
  `fas fa-map-marker-alt`, a map pin, on a text question.
- **Image** — `image_source` is computed for every question (`forms.py:301`) but only reaches a
  widget in the `image` branch (`forms.py:264`).

**Image is the damaging one.** On any other type the form accepts the upload and stores the file,
and nothing ever renders it. The author sees a successful save, the file exists in storage, the
survey never shows it, and there is no signal at any point that the upload was pointless.

The editor already has the machinery for this — `toggleChoicesEditor`, `toggleValidationFields`,
`toggleDisplayStyleFields` and `toggleStripWidthHint` all hide fields that do not apply to the
selected type. These three were simply never wired into it.

## Notes

- Reported 2026-08-09 from the New Question dialog: "Что значит Color, Icon, Image для Text
  вопроса? Это поведение проявляется во всех вопросах."
- Fix is small: add a toggle keyed on `input_type`, following the existing functions. Colour and
  icon show for geo types; image shows for the `image` type.
- Decide separately what to do about images already uploaded against types that never render them.
  Check production for `Question.image` set on a non-`image` question before choosing — silently
  dropping them on the next save would be its own surprise.
- Worth checking the same question for `validation_settings`, which is a JSON blob shared across
  types, and for `required` on `html`/`image` blocks, which collect nothing and cannot be required
  in any meaningful sense.
- Related: [Group the question type list](improvement-group-question-type-list.md), reported in the
  same message — both are about the dialog implying capabilities a type does not have.
