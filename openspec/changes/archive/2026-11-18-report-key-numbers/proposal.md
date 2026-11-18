## Why

The Key numbers block of a report is unfriendly to a first-time author (owner, 2026-11-18; issue
#744). A new block arrives empty with a warning that it is left out of the report, and showing a
number of the survey means typing a token (`{responses}`, `{marks:CODE}`) the settings panel lists
as code; clicking a live number turns it back into its token.

## What Changes

- A new Key numbers block of a report with a survey arrives filled with the numbers reports most
  often open with — opened, answered, finished, marks on the map — the same set a drafted report
  gets (`reports/numbers.py::defaults`, one list for both).
- Numbers of the survey are picked from a menu: "Add a number" offers the survey's numbers with
  their current values and "A number you type". Clicking a live number opens the same menu to
  change it or to turn it into a typed number. The author never types or sees a token there.
- The token list leaves the Key numbers settings panel. Tokens stay the stored format and keep
  working in text and in the opening.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reports-editor`: how key numbers are added and edited on the canvas.

## Impact

New `reports/numbers.py`; `reports/drafting.py`, `reports/services.py`, `reports/canvas.py`,
`reports/editor_views.py`, the builder templates (`builder.html`, `_canvas_block.html`,
`_block_panel.html`, new `_number_menu.html`), `js/report_builder.js`, `css/report_builder.css`,
the ten catalogs, the help page. No migration; stored blocks are unchanged.
