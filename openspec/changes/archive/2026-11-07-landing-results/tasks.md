## 1. Shared renderer

- [x] 1.1 Move the inline script of `public_results.html` into `js/public_results_render.js` (`renderResultBlocks(blocks, basemaps)`); the template includes and calls it; the page tests that read the script read the static file

## 2. Results block

- [x] 2.1 `PublicResultsService.for_survey(survey, k, lang)`
- [x] 2.2 `landings.py`: `results` kind, `_clean_results`, `results_questions(org)` for the picker, `results_payload(block, lang)` with the 60 s cache
- [x] 2.3 `landing_views._save_block`: survey + question from `results_question` (`<survey uuid>:<code>`), link the survey, type check
- [x] 2.4 Templates: form branch, `landings/blocks/results.html`, `public.html` (libraries + call), builder summary

## 3. Tests, docs, strings

- [x] 3.1 Tests for every new scenario
- [x] 3.2 Help page, translations
- [x] 3.3 Full suite, validate, dev check of `/r/` and a landing with charts and a map
- [ ] 3.4 PR into `epic/landing-pages`, merge
