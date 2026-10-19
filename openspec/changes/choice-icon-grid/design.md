## Context

`choice` already has two renderings picked by `Question.display_style`: the radio list
(`OtherChoiceRadioSelect`) and the searchable dropdown (`ChoiceDropdownWidget`, template
`choice_dropdown.html` with a once-bound inline script, CSS in `main.css`). `multichoice` has no
display style at all. The respondent form is built by `SurveySectionAnswerForm` and rendered
through `partials/question_fields.html` on every surface: the section, the geo-feature and
layer-object pop-ups (server-rendered, inserted into the DOM later) and the editor's
"Respondent sees" frame (`editor/partials/question_preview_frame.html`, which loads `main.css`).

The set of styles a type accepts is written out four times today: `STYLES_BY_TYPE` in
`forms.py`, `QuestionForm.clean()`, `editor_question_preview_live` and
`serialization._import_question`. Each one hard-codes `choice → {default, dropdown}`.

Choice entries already carry one optional key beyond `code`/`name`: `other: true`. The editor's
`serializeChoices()` writes it, `_guard_choice_codes` keeps it, ZIP copies `choices` verbatim.

## Goals / Non-Goals

**Goals:**
- One more style, `icon_grid`, for `choice` and `multichoice`, with the same value, validation and
  write-in behaviour as the list.
- Optional per-option `icon` and `group`, authored in the existing choices table.
- Collapse-after-pick for single choice. It must work in pop-ups inserted after page load.
- One list of allowed styles per type, so the next style is one edit.

**Non-Goals:**
- Marker colour/icon by chosen option (follow-up).
- Icons in the Dropdown or List renderings, on Responses, in exports or on public results. The keys
  are carried but only the grid draws them.
- Drag-reorder of groups. A group is just the value on consecutive rows.

## Decisions

**D1. Native inputs inside labels, server-rendered.** The grid is a widget template over Django's
`RadioSelect`/`CheckboxSelectMultiple` (`ChoiceIconGridRadio`, `ChoiceIconGridCheckbox`, both
with `OtherChoiceWidgetMixin`). Each tile is `<label class="cig-tile"><input …><icon><span>label`.
The input is visually hidden but focusable. The checked tile is styled by
`.cig-tile:has(input:checked)` plus a `cig-tile--on` class set server-side for old browsers.
- *Why:* the submitted value, the required check in the respondent JS, the write-in toggle
  (`other_option.js` listens on input change) and keyboard/arrow navigation all come for free and
  match the list exactly.
- *Alternative:* a JS-built grid feeding a hidden select, like the dropdown. Rejected: it adds a
  second source of truth and breaks without JS.

**D2. Icons through `{% marker_icon %}` on the server.** The widget's `create_option` puts the
choice's `icon` on the option dict, and the option template calls `{% marker_icon option.icon %}`.
An empty value renders no icon element at all, so the tile shows the label alone. That is what
`marker_icons.render` already does for empty input. An unknown `set:name` shows the default pin
there, which is the wrong signal on a tile. The grid therefore asks `marker_icons` whether the
value is known (new helper `marker_icons.is_drawable(value)`; the existing `is_known` means "catalogued", which would drop pasted Font Awesome classes) and drops it when it is not.
- *Alternative:* `MarkerIcon.element` in the browser. Rejected: the grid is static markup, and
  the server helper is the documented twin.

**D3. Groups as consecutive runs.** The widget walks the options in stored order and starts a new
`<div class="cig-group">` with an `<h6 class="cig-group__title">` whenever `group` (stripped)
differs from the previous option's. An empty group after a named one gets an untitled run. If no
option has a group, the result is one untitled run, i.e. a flat grid. Group text is plain text,
escaped, and not translated per language in v1. The translation savers do not touch it, and the
same label shows in every language.
- *Alternative:* `optgroup` via Django choices. Rejected: Django's optgroups sort nothing but
  change the option `index`/ids and the write-in lookup. Simple runs are enough.

**D4. Collapse is CSS-driven with a tiny delegated script.** For `choice` the widget root carries
`data-cig-collapse`. The script binds once per document (`window._choiceIconGridBound`, like the
dropdown) and uses delegated `change` and `click` listeners on `document`. On change it measures
the tiles' `offsetTop` and marks the tiles not on the chosen tile's row with `cig-off-row`. It
then sets `cig-collapsed` on the root, which hides those tiles and the group headings of other
runs, and shows the "Show all options" button. The button removes `cig-collapsed`. A grid that
already holds an answer (revisit, reopened pop-up) collapses when it first becomes visible. The
script runs `collapseChecked(root)` on `DOMContentLoaded` for the section, and for pop-ups on the
respondent map's existing popup-open path. Which hook that is gets settled during implementation:
a call from the pop-up code or a delegated `pointerenter`/`focusin` fallback. Row membership is computed from layout, not from a
fixed column count, so it adapts to pop-up width and phone width. On `resize` collapsed grids are
recomputed. `multichoice` grids never get `data-cig-collapse`.
- *Why "the row":* the issue asks for the row holding the chosen tile, so neighbours stay one
  tap away for a quick switch.

**D5. One allowed-styles table.** `question_types.DISPLAY_STYLES_BY_TYPE = {'rating':
('default','scale_strip','list_pips','stars'), 'choice': ('default','dropdown','icon_grid'),
'multichoice': ('default','icon_grid')}` and `allowed_display_styles(input_type)`. `forms.py`,
`editor_forms.QuestionForm.clean()`, `editor_question_preview_live`, the saved-question preview's
`display_style` override and `serialization` all read it. `DISPLAY_STYLE_TYPES` in `forms.py`
becomes its keys. `DISPLAY_STYLE_CHOICES` gains `('icon_grid', 'Icon grid')`, which needs an
AlterField migration with no data change.

**D6. Editor: one card, two columns gated by style.** `#display-style-fields` gets an Icon grid
card (`data-types="choice multichoice"`, a 2×3 mini tile thumb). The List card's `data-types`
also gains `multichoice`. JS `DISPLAY_STYLE_TYPES` gains `multichoice`. The card filter changes
from equality to token membership on `data-types`. The choices table gets `Icon` and `Group`
header cells and row cells with classes `choice-icon-cell`/`choice-group-cell`. A
`choices-editor--grid` class on the editor, toggled when the checked style is `icon_grid`,
shows them, the same pattern as `choices-editor--no-other`. Each row's icon input gets an
`IconPicker.attach` (the picker wraps a plain input, so a per-row call works). Rows added later
attach on creation. `serializeChoices()` writes `icon`/`group` only when non-empty, so a survey
that never uses the grid stores byte-identical choices. Switching away from Icon grid hides
the columns but keeps the values, so switching back loses nothing.
- *Alternative:* always-visible columns. Rejected: two empty columns on every choice question
  for a style most creators never pick.

**D7. Saving keeps the keys, server-side cleanup is minimal.** `_guard_choice_codes` already
passes unknown keys through. A small `normalise_choice_extras(choices)` strips non-string or
blank `icon`/`group`, trims them, and caps `group` at 60 and `icon` at 64 characters. It runs
where `choices_json` is parsed (create, edit, autosave, live preview) and in ZIP import, so a
hand-edited archive cannot store a 10 KB "group". Icon values are not validated against the
catalog on save, because an unknown icon renders nothing (D2). That matches how `icon_class`
pasted Pro classes pass through.

**D8. AI generation.** If the generator's schema enumerates `display_style`, add `icon_grid` and
document `icon`/`group` on choices with an example. Otherwise nothing changes, since ZIP import
is the write path and accepts the keys.

## Risks / Trade-offs

- [The preview frame loads Font Awesome 5.8.1 while the catalog is built from 5.15.4, so a few
  newer FA icons show blank in "Respondent sees" only] → Bump the frame's FA link to 5.15.4, the
  version the three base templates use (CLAUDE.md: keep FA on the catalog version).
- [Row detection by `offsetTop` runs while a pop-up is still hidden, where everything has
  offsetTop 0] → Compute on the `change` event (the grid is visible then) and recompute on the
  first visible interaction for prefilled grids. A grid that cannot be measured stays expanded,
  which is the fail-open state.
- [`:has()` is missing on old Android WebViews] → The server-set `cig-tile--on` class and a
  change handler that toggles it give the same look.
- [17 tiles with long labels overflow on 320 px] → Tiles have a fixed min width (≈84 px). Labels
  clamp to 2 lines with `title` carrying the full text, and the grid wraps.
- [Write-in option inside a grid] → The write-in input renders once under the grid (as the
  dropdown does), not inside a tile, and `other_option.js` keeps working on input change.

## Migration Plan

One AlterField migration for `display_style` choices, reversible, with no data touched. Existing
questions keep `default`/`dropdown`. Rollback = revert the PR; any `icon_grid` value left behind
resolves to the plain list through `resolve_display_style`'s unknown-value fallback, and the
extra choice keys are ignored by every other consumer.

## Open Questions

- None blocking. Translating group labels per language is deferred until a multilingual survey
  asks for it.
