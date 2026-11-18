## Why

The creator app's colours and sizes are written in four places — Bootstrap 4's defaults, the survey
editor's variables, the builders' variables, the Pro badge's — plus literals in templates: 319
distinct colours, three different "primary" colours (indigo, Bootstrap blue, teal). The same button
looks different from page to page, and a change of look means editing dozens of templates.

## What Changes

- One file, `css/tokens.css`, loaded by both creator base templates right after Bootstrap: a palette
  of raw values and, over it, tokens named by purpose (surfaces, text, lines, action, danger,
  success, warning, Pro, type sizes, space, radius, shadow).
- The action colour is indigo (owner decision 2026-11-18); teal stays on the marketing pages.
- Bootstrap's buttons, links, badges, alerts, form focus and modals are set from the tokens once, so
  existing markup changes its look without template edits. The quiet button ("secondary", filled or
  outline) is white with a grey frame.
- The editor's, the builders' and the Pro badge's own variables become references to the tokens.
- A ratchet test: no creator stylesheet or template may hold more colour literals than recorded.

Not in this change: moving individual pages' literals onto tokens (done component by component
afterwards, lowering the baseline), a dark theme, respondent pages, marketing pages.

## Capabilities

### New Capabilities
- `design-tokens`: the token file, what loads it, how Bootstrap follows it and the ratchet.

## Impact

`survey/assets/css/tokens.css` (new), `base.html`, `editor/editor_base.html`, `site_builder.css`,
`pro_badge.css`,
`survey/tests/test_design_tokens.py` + `colour_baseline.json`, `scripts/colour_baseline.py`.
Every creator page's primary button turns from Bootstrap blue to indigo.
