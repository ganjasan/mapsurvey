## Context

A key number is `{'value', 'label'}` in `ReportBlock.config`; a value that is a token
(`reports.tokens.TOKEN`) is filled from the report's home survey at render time. The canvas shows
the filled value and keeps the token in `data-raw`; focusing the field swaps the token back in for
editing. Rows are edited on the canvas by `js/site_builder.js` (shared with Sites) and posted as
parallel lists.

## Goals / Non-Goals

**Goals:** a filled block on the first click; survey numbers without tokens; typed numbers stay.

**Non-Goals:** a new storage format (tokens stay); numbers of a survey other than the home survey
(tokens are filled from the home survey only); changing tokens in Text blocks and the opening.

## Decisions

- **Defaults are the drafted report's set**, moved to `reports/numbers.py::defaults(survey)` and
  used by both `drafting._key_numbers` and the editor's "add block" — one answer to "which numbers
  do reports open with". The service takes `items`; the view passes the defaults when the report
  has a home survey.
- **A Key numbers block added from a chosen survey adopts it as the home survey** (same rule as a
  data block, change report-home-survey): its numbers can only be filled from the home survey.
- **The menu is rendered once per page** (`_number_menu.html`, from `numbers.choices(survey, k)`):
  the three funnel steps and the marks of each map question, each with its current value. Picking
  writes the token into the row's `data-raw` and the value into its text, then saves through the
  existing row autosave — no new endpoint.
- **A live value is not a text field.** A value that is exactly one token is marked `data-live`;
  `report_builder.js` stops it taking focus and opens the menu instead. A value that mixes text
  and a token ("{responses} people") keeps the old reveal-on-focus behaviour, as do the note and
  the opening.
- **No change to `site_builder.js`**: the report script intercepts "Add a number" in the capture
  phase and re-fires the click for the shared row code to add the row.

## Risks / Trade-offs

- The menu costs one engagement query and one count per map question on each builder load of a
  report with a survey; capped at eight map questions.
- `{respondents:CODE}` is not in the menu; it remains available as a typed token in text.
