## Why

The block library offers Quotes as "What people wrote, picked by you", but the block only takes
text typed or pasted on the page: to quote a respondent the author leaves for Responses, finds the
answer, copies it and comes back (#749). The empty block shows a placeholder row that looks like a
filled quote next to a yellow warning, the closing quote mark floats after the placeholder, the
red × is loud on every row, the quotes cannot be reordered, every block is the same grey column,
and "Before you publish" only lists the quotes without saying which one deserves a second look.

## What Changes

- **Pick from answers.** The Quotes block's panel lists the free-text answers of a survey — the
  report's home survey or another survey the member sees — filtered by question, searched by
  words, readable lengths first, clean sessions only. One click adds the answer as a quote with the
  question's name as its source. A picked quote keeps `ref = {survey, question}`; on save the
  server marks it `shortened` when its text is no longer one of that question's answers.
- **Empty state.** A Quotes block with no quote shows two actions, "Pick from answers" and "Write
  a quote", instead of an empty placeholder row and the warning; the add link under the quotes
  offers the same two.
- **Row controls.** No quote marks around an empty field; the row's × is grey and shows on hover
  or focus; rows are reordered by dragging their handle.
- **Layout.** `config.style`: `list` (default, as today), `pull` (one large quote per row),
  `cards` (two columns). Set in the block's settings; the page, embeds and the canvas follow it.
- **Privacy flag.** `reports.quotes.contact_flags(text)` finds an email address, a phone number or
  a web address; "Before you publish" lists those quotes in their own item and the canvas marks
  the row.

## Capabilities

### New Capabilities
- `reports-quotes`: picking quotes from answers, their origin, layout and the contact flag.

### Modified Capabilities
- `reports-editor`: the empty Quotes block shows its two actions instead of the note.

## Impact

- `reports/quotes.py` (new), `reports/story.py` (`clean_config` keeps `ref`, `shortened`, `style`),
  `reports/services.py` (`update_block(quote_style=)`, origin check), `reports/editor_views.py`
  (`quotes` route, rows post `ref`), `reports/checks.py`, `reports/canvas.py`.
- Templates `reports/editor/_canvas_block.html`, `_block_panel.html`, `_quote_answers.html` (new),
  `reports/_block.html`; `css/report_builder.css`, `css/report_public.css`;
  `js/report_builder.js`; `js/site_builder.js` (rows may stay empty, rows post the `data-*`
  attributes their list names).
- Report file, REST and MCP carry the new keys through `clean_config`; the PDF keeps one layout.
- Tests: `survey/tests/test_reports_quotes.py`.
