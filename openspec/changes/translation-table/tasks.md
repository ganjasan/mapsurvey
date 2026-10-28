## 1. Source hashes and the gap engine

- [x] 1.1 Model `TranslationSource` (survey FK to the canonical header, `key`, `language`, `source_hash`, `updated_at`; unique on survey+key+language) and migration `0105_translationsource`
- [x] 1.2 `survey/translation_table.py`: occurrence keys (`section:<code>[#n]:…`, `question:<code>:…`, `question:<code>:choice:<code>`, `group:<code>:…`, `survey:thanks`), source normalisation and hashing, `record_hashes()` / `stale_keys()`
- [x] 1.3 `services/common.save_translations()`, `services/surveys.set_thanks()` and `services/questions._apply_choices()` record hashes for the languages and fields they write (base-text saves untouched)
- [x] 1.4 `translation_gaps.py`: count a set Next label, a set primary thank-you page, and stale occurrences marked "(outdated)"; keep badges, publish warning, API and MCP on the one function
- [x] 1.5 Tests: hash recorded by modal/API/thanks saves; stale after a base edit; translated when no hash; gap engine entries for Next label, thank-you page and stale; publish 409 lists "(outdated)"

## 2. Collector and writer

- [x] 2.1 `translation_table.collect(survey, language)`: occurrences in respondent order (sections → groups/questions → sub-questions → choices, then thank-you page), location labels, statuses, grouping by normalised source + kind, group keys `t:<hash12>`, auto-expansion when translations differ
- [x] 2.2 `questions.set_choice_names(question, language, {code: text})` — writes only `name[lang]`, `update_fields=['choices']`
- [x] 2.3 `translation_table.apply(actor, survey, language, values, overwrite=False)`: content-lock check, key resolution (group or occurrence), skip-unless-overwrite, routing to `save_translations` / `set_choice_names` / `set_thanks`, caps and `coerce_creator_html`, hashes, one `LIVE_EDIT_SAVED` + `rescreen_if_live`, `Report`
- [x] 2.4 Tests: dedup and counts, order, group save fills every occurrence, occurrence save, auto-expanded groups, skip/overwrite, content lock refusal, script stripped, caps, live survey stays without a draft

## 3. Page and row editing

- [x] 3.1 `survey/translation_views.py` + URLs: `editor_survey_translations` (viewer), `editor_survey_translation_save` (editor, HTMX), export (viewer), import (editor); `?lang=` with default first non-primary; redirect to the draft while one exists; empty state under two languages
- [x] 3.1a Language choice: `?from=`/`?to=` with defaults (primary; first non-primary or the creator's UI language), fallback to primary text with a "(primary)" mark, `localStorage['msTranslations:<uuid>']` restore; `editor_survey_translation_add_language` (owner, POST) through `update_settings(partial=True)`; inline `language_picker.html` in the picker and the empty state
- [x] 3.2 Template `editor/survey_translations.html` + row partial: source and target pickers with *Add language…* (owner) or the owner hint (editor), status counts and filter (all / missing / stale), group rows with usage count and locations, *Translate separately*, read-only mode for viewers, "Learn more" via `HELP_URL.translate`
- [x] 3.3 Row autosave JS (`js/translation_table.js`): textarea change → HTMX POST → row re-render with status; lazy Quill on rich rows posting HTML; the editor's saved/saving/error indicator
- [x] 3.4a Deep links: `?question=<id>` on `editor_survey_detail` opens that question's modal after the section renders and scrolls to `#translations-<lang>`; table rows get `id="row-<key>"`; page/section/question/option/thank-you links in the row partial
- [x] 3.4 Fourth tab in `_survey_nav_tabs.html` (`fa-language`, `active_tab == 'translations'`); check the strip on mobile widths with `editor-mobile.css`
- [x] 3.5 Tests: tab present on every survey page, 403s per role, empty state, redirect to draft, row save renders the status, viewer read-only

## 3b. Modal blocks become a read-only mirror

- [x] 3.6 Section, question and group modals: translation inputs `disabled`, wrapped in links to `editor_survey_translations?to=<lang>#row-<key>`, one hint line under the block heading; Quill translation editors rendered read-only
- [x] 3.7 Choices table: per-language name columns read-only with the same links; `_apply_choices` leaves untouched languages alone; thanks panel non-primary tabs read-only with a link to `#row-survey:thanks`
- [x] 3.8 Table: `#row-<occurrence key>` resolves to the containing group row (expanded when split) and scrolls to it
- [x] 3.9 Tests: a modal POST with `translation_*` values changes nothing; the block shows the stored text and the link; choices save keeps existing per-language names; thanks panel link

## 4. CSV round trip

- [x] 4.1 CSV reader (`utf-8-sig`, sniffed `,;\t`, lower-cased headers) and a formula-safe writer with BOM in `translation_table.py` (`parse_csv`, `export_csv`); the layer CSV import keeps its own `_read_csv` — lifting both into one module is a follow-up, not this change
- [x] 4.2 Export view: columns `key, page, element, source, translation, status`; rich text as plain blocks; file name `<slug>-translations-<lang>.csv`
- [x] 4.3 Import view: upload + overwrite checkbox; match by key, then by normalised source; plain paragraphs → `<p>` for rich fields; apostrophe prefix stripped; report rendered above the table
- [x] 4.4 Tests: export shape and order, formula prefix, round trip equality, key-less hand-built file matched by source, unmatched reported, overwrite vs skip, language taken from the page

## 5. Strings, docs, changelog

- [x] 5.1 Add every new creator string to the ten offered catalogues by hand (`TranslationCatalogHygieneTest`)
- [x] 5.2 Help page `how-to/translate-a-survey.md`: the tab, statuses, CSV round trip and its markup caveat; registry key `translate` in `help_links.py`
- [x] 5.3 Changelog entry `survey/changelog/<date>-translations-tab.html` (`kind: new`)
- [x] 5.4 CLAUDE.md paragraph on the translation table (keys, hash table, one writer, gap engine) and `./run_tests.sh survey` baseline vs after
