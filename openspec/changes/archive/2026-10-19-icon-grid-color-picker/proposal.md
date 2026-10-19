## Why

Follow-up to `choice-icon-grid` (#341), from the owner's first use on production. Icon-grid tiles have no way to set an icon colour: every glyph is the same dark grey, so a grid of 17 kinds of place reads as one undifferentiated block. The icon picker, opened from a choices-table cell, is as narrow as that cell (~230 px). It shows four columns of small icons and two rows of category chips that wrap three times.

## What Changes

- **Icon colour on the icon grid.** The question's existing **Color** field is shown for `choice`/`multichoice` while Icon grid is selected and colours every tile icon. A new optional **Color** column in the choices table overrides it for one option. The stored value is an optional `color` key (`#RRGGBB`) on the choice entry, next to `icon`/`group`. A question colour of `#000000` (the model default) means "not set", and the tile keeps today's grey. The colour reaches the glyph only through `{% marker_icon … color=… %}`.
- **A picker that fits.** The dropdown is at least 440 px wide (or the viewport less a margin) whatever the width of its input. It opens to whichever side keeps it on screen. Its cells grow from 40 to 44 px and glyphs from 18 to 22 px. Every picker gets this: the question's marker icon, star ratings and the choices table.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `choice-icon-grid`: tile icons take the option colour, else the question colour, else the default grey.
- `inline-choices`: the choice object gains an optional `color` (`#RRGGBB`), normalised with `icon`/`group`.
- `survey-editor`: Color is offered for the icon grid; the choices table has a Color column under Icon grid.
- `marker-icon-picker`: the dropdown has a minimum width and opens on the side with room.

## Impact

- `survey/question_types.py` (`normalise_choice_extras` gains `color`).
- `survey/forms.py` (the grid widget receives the question colour and option colours).
- `survey/templates/choice_icon_grid.html`.
- `survey/templates/editor/partials/question_form_modal.html` (Color field gating, Color column).
- `survey/assets/js/icon_picker.js` and the picker CSS in `editor_base.html`.
- Tests. No migration (`color` is a JSON key).
