## 1. Colour data and rendering

- [x] 1.1 `normalise_choice_extras` keeps a valid `#RRGGBB` `color` (lower-cased) and drops anything else
- [x] 1.2 `_choice_extras` carries `color`; grid widget takes the question colour and resolves option → question (unless `#000000`) → none per option
- [x] 1.3 `choice_icon_grid.html` passes the resolved colour to `{% marker_icon %}`
- [x] 1.4 Tests: normaliser, question colour, option override, default `#000000` emits no inline colour

## 2. Editor

- [x] 2.1 Show the Color field for choice/multichoice while Icon grid is checked (`toggleTypeScopedFields`, also on style change)
- [x] 2.2 Color column (swatch + clear) in the choices table, hidden with the other grid columns; `serializeChoices` writes `color` only when set; rows rebuilt from existing choices restore it
- [x] 2.3 Test: modal renders the Color column; choices_json with `color` persists normalised

## 3. Picker sizing

- [x] 3.1 CSS: dropdown min-width `min(440px, 100vw - 16px)`, no right anchor, `--right` modifier, 44 px cells, 22 px glyphs; mobile rule unchanged
- [x] 3.2 `open()` aligns right when the left-aligned dropdown would overflow the viewport

## 4. Verify

- [x] 4.1 Targeted tests green; one full `./run_tests.sh survey` run (Ran 2677, OK)
- [x] 4.2 Browser: picker from a choices-table cell is wide and on screen; coloured icons in the respondent grid and the preview
- [x] 4.3 `openspec validate icon-grid-color-picker --strict`
