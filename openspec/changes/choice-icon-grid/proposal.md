## Why

A `choice` with 10–20 short options (kinds of place, activities) renders as a radio list; inside a
geo pop-up on a phone that is two screens of scrolling, and nothing tells the options apart at a
glance although the marker catalog already has an icon for most of them (#341, epic #343 "one geo
question for many kinds of place").

## What Changes

- New display style **Icon grid** (`display_style = "icon_grid"`) for `choice` and `multichoice`:
  one tile per option, icon above a short label, selected tile(s) highlighted. Tiles are the native
  radios/checkboxes wrapped in their labels, so keyboard, validation and the submitted value are
  exactly those of the list rendering.
- `multichoice` gains a **Display as** block for the first time: *List* (default) and *Icon grid*.
  `choice` gets Icon grid as a third card beside List and Dropdown.
- The choices table gets two optional columns, **Icon** (picked with the existing icon picker,
  any `MarkerIcon` form: `fas fa-…`, `maki:…`, `temaki:…`) and **Group** (free text). They are
  shown when Icon grid is the selected style. Stored as optional `icon` and `group` keys on each
  `choices` entry, next to `other`.
- Groups: consecutive options with the same non-empty `group` get one small heading above their
  tiles; no group anywhere = one flat grid.
- `choice` only: after a pick the grid collapses to the row that holds the chosen tile (its
  neighbours stay for a quick switch) plus a "Show all options" link; a later change collapses
  again. A stored answer renders collapsed. `multichoice` never collapses.
- Rendered on every respondent surface that renders the form — section, geo-feature and
  layer-object pop-ups — and in the editor's "Respondent sees" preview
  (`editor_question_preview_live`).
- Icons are drawn only through `{% marker_icon %}` / `MarkerIcon.element`; an unknown or empty
  icon renders the label alone.
- ZIP export/import, AI generation and draft copies carry `display_style = "icon_grid"` and the
  `icon`/`group` keys unchanged; a survey exported before this change imports as before.

Not in scope: colouring the map marker by the chosen option (follow-up, a `by` rule on the
sub-question value like `SurveyMapLayer.style`).

## Capabilities

### New Capabilities
- `choice-icon-grid`: how a `choice`/`multichoice` question with `display_style = "icon_grid"`
  renders and behaves for respondents — tiles, icons, group headings, collapse after a pick
  (single choice only), fallback for missing icons, preview parity.

### Modified Capabilities
- `choice-dropdown-display`: "Dropdown style is scoped to choice questions" becomes the general
  rule of which display styles each type accepts (`choice`: default/dropdown/icon_grid;
  `multichoice`: default/icon_grid; anything else falls back).
- `inline-choices`: the choice object gains optional `icon` and `group` keys, ignored by every
  consumer except the icon-grid rendering, preserved by save, export and import.
- `survey-editor`: the question form's Display as block covers `multichoice`, offers the Icon grid
  card, and the choices table shows Icon (with picker) and Group columns for that style.
- `survey-serialization`: `icon_grid` is an accepted `display_style` on import for
  `choice`/`multichoice`; `icon`/`group` round-trip.

## Impact

- `survey/models.py` — `DISPLAY_STYLE_CHOICES` + migration (AlterField, no data change).
- `survey/forms.py` — `STYLES_BY_TYPE`, a new `ChoiceIconGridWidget` (radio and checkbox variants,
  keeping the `OtherChoiceWidgetMixin` write-in), its template under `survey/templates/`.
- `survey/editor_forms.py`, `survey/editor_views.py` (allowed styles, `choices_json` keeps the two
  keys), `survey/serialization.py` (allowed styles on import).
- `survey/templates/editor/partials/question_form_modal.html` — Display as for multichoice, new
  card + thumb, two table columns, icon picker per row.
- New respondent CSS/JS for the grid and the collapse (event-delegated, so pop-ups inserted later
  work); loaded by the respondent base template and the live-preview template.
- AI generation schema/prompt if it enumerates display styles.
- Tests in `survey/tests.py` (render, collapse markup, validation, round-trip, preview) and a
  changelog entry under `survey/changelog/`.
