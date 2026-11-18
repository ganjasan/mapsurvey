## 1. Data and server

- [x] 1.1 `story.clean_config('quotes')` keeps `ref {survey, question}`, `shortened`, `style`
- [x] 1.2 `reports/quotes.py`: `text_questions(survey)`, `answers_for(survey, code, q)`, `mark_origins(items)`, `contact_flags(text)`
- [x] 1.3 `services.update_block(quote_style=)`; quote items pass `mark_origins`
- [x] 1.4 `_block_edit` reads `ref` rows and `quote_style`; `quotes` route (both ways in) renders the answer list
- [x] 1.5 `checks.run` adds the `quote_contact` item; canvas records carry per-row flags

## 2. Editor

- [x] 2.1 Shared builder: `data-rows-empty` lists stay empty; `data-row-attrs` posted per row
- [x] 2.2 Canvas: empty state with two actions, quote marks only around text, origin chips, contact mark, drag handle
- [x] 2.3 Panel: answer picker (survey, question, search, list, Add) and the layout choice
- [x] 2.4 `report_builder.js`: picker fetch, add a picked quote, Sortable rows
- [x] 2.5 CSS: quiet ×, layouts on canvas and page

## 3. Page and tests

- [x] 3.1 `reports/_block.html` + `report_public.css` draw `list | pull | cards`
- [x] 3.2 `survey/tests/test_reports_quotes.py`; existing editor/story/review tests green
- [x] 3.3 Translations of the new strings in every offered catalog
