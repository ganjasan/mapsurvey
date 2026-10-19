## Context

`choice-icon-grid` (#341) shipped tiles whose icons are always `#374151`, and a choices-table Icon column whose picker dropdown is `left:0; right:0` of its wrapper, so it is exactly as wide as the cell. `Question.color` exists (default `#000000`) and already colours map markers and star ratings; it is hidden for choice types.

## Decisions

**D1. Question colour + per-option override.** It reuses the field creators already know from markers and stars: one colour for the common case, and an override for the option that should stand out. `#000000` means "not set" because it is the model default every existing question carries. Painting all those icons pure black would change existing grids on deploy.
- *Alternatives:* question-only (cannot single out an option) or option-only (17 clicks for a uniform colour). Both rejected.

**D2. Colour resolved on the server, drawn by `marker_icon`.** `_choice_extras` carries `color`. The widget receives the question colour, and `get_context` puts the resolved colour (option → question unless `#000000` → none) on each option. The template calls `{% marker_icon option.icon color=option.icon_color %}`, which sets `color:` on `<i>` and `fill:` on `<svg>`. With no colour nothing inline is emitted and the CSS grey applies.

**D3. Validation in one place.** `normalise_choice_extras` gains `color`: kept only if it matches `^#[0-9a-fA-F]{6}$` after strip, then lower-cased. It runs on every save path already (editor, autosave, live preview, ZIP import).

**D4. Editor colour cell.** An `<input type="color">` cannot be empty, so the cell is a swatch plus a "×" clear button. A cleared cell carries `data-unset="1"` and shows a struck-through swatch; picking a colour removes the flag. `serializeChoices()` writes `color` only when not unset. Values are set through `.value` after the row is inserted, as for icon/group.

**D5. Picker sizing in CSS + one alignment check in JS.** `.icon-picker-dropdown` gets `min-width: min(440px, calc(100vw - 16px))` and loses the implicit `right:0`. `open()` measures the wrapper and dropdown. If `wrapperLeft + dropdownWidth > viewportWidth - 8`, it adds `icon-picker-dropdown--right` (`left:auto; right:0`). The mobile rule (`position: fixed` bottom sheet) is untouched. Cells 44 px, glyphs 22 px.
- *Alternative:* `position: fixed` computed from the button rect on desktop too. Rejected: the dropdown would then drift away from its input when the modal body scrolls, and the absolute placement already escapes the table because nothing between it and the modal clips overflow.

## Risks / Trade-offs

- [A creator who deliberately picked black for the question gets grey icons] → Rare and recoverable: a per-option colour or `#111111` gives black. This is documented in the Color help text for the grid.
- [Wider dropdown overflows a very short modal vertically] → `max-height` and an inner scroll on the grid are unchanged.
