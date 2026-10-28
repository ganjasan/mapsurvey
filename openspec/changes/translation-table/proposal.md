## Why

A creator who adds a second language gets an empty translation form under every section, question,
option, group and the thank-you page, and fills each one by hand — on a real survey that is dozens of
fields, and the same string ("Other", "(Select all that apply)") is typed again and again. The Spanish
translation of a US city transport consultation (#391 → #393) was done twice in one week by dumping
every creator-written text from the production database, translating it in a spreadsheet (the second
time by the customer's native-speaker reviewer) and writing it back with SQL. That round trip is a
product surface, not a database script, and it is the mechanism the AI translation of epic #393 will
sit on. Issue #454.

## What Changes

- A fourth tab, **Translations**, in the survey nav strip between *Survey* and *Responses*, on the
  desktop strip and the mobile nav. Always visible: with fewer than two languages it shows an empty
  state that links to the language settings; otherwise the table with a language picker.
- **The translation table**: one row per *unique* creator-written source string, in respondent order,
  with a usage count, the source on the left and the translation for the chosen language on the right.
  One translation fills every occurrence of that string. Sources are exactly what the translation
  models hold: section title / subheading / Next label, question name / help text / Formatted Text body,
  choice option names, group title / description, the thank-you page. Rich text is edited as rich text
  with the source markup kept.
- **Row status**: *missing* / *translated* / *stale*. Stale is computed from a hash of the source text
  stored beside the translation at write time, so editing the primary-language text never silently
  leaves an outdated translation behind. What counts as missing is what `translation_gaps` already
  reports; the publish warning and the editor badges count stale rows as gaps too.
- **One writer**: the table, the CSV import (and, later, the AI job) save through one function that
  applies `coerce_creator_html` to rich fields, records the source hash, treats translations as a SAFE
  edit on a live survey, and never overwrites an existing translation without an explicit flag.
- **CSV round trip**: export the table for a language (one row per unique string, a stable key, source
  and translation columns) and import the same file back; the import report says what was filled, what
  was skipped as already translated, and what did not match.
- **The inline translation blocks stay, read-only.** The Translations block of the section, question
  and group modals, the per-language columns of the choices table and the non-primary tabs of the
  thank-you panel keep showing the translations but no longer edit them: every field is disabled and
  a click on it opens the Translations tab at that row (the right language, the row scrolled into
  view). One place writes translations from the UI; the modal keeps telling the creator that a
  translation exists and where it is edited.
- Out of scope (later items of #393): AI translation, glossary, the "machine-translated" mark,
  per-question re-translate.

## Capabilities

### New Capabilities
- `translation-table`: the Translations tab; the unique-string table with usage counts and
  missing / translated / stale statuses; the single translation write path with source hashes; CSV
  export and import of the table.

### Modified Capabilities
- `survey-editor`: *Translation management* and *Choices editor for choice-based questions* — the
  inline translation inputs become read-only and link to the Translations tab; they no longer save.
  The delta is written against the version in the merged-but-unarchived change
  `fix-primary-language-duplicate-fields`, which MUST be archived before this one (its
  `translation-completeness` spec is not touched here; the stale state is specified in the new
  capability).

## Impact

- **Models / migration**: a `source_hash` column on `SurveySectionTranslation` (title, subheading,
  next_label), `QuestionTranslation` (name, subtext) and `QuestionGroupTranslation` (title,
  description) — one JSON map field → hash per translated field; for choice names and the thank-you
  page the hashes live beside the per-language values (`choices[i].name_hash[lang]`,
  `SurveyHeader.thanks_html_hash[lang]`). Existing translations get no hash and read as *translated*
  until their source changes after this ships (the hash is written on the next save).
- **New module** `survey/translation_table.py`: collect rows (reuses the walk in
  `survey/translation_gaps.py`), status, one `apply_translations()` writer, CSV writer/reader.
- **Views / URLs**: `editor_survey_translations` (page), row save (HTMX), export, import — in a new
  `survey/translation_views.py`; `_survey_nav_tabs.html`, `_mobile_nav.html`, `editor_mobile_nav.js`
  get the fourth tab; `editor_views.py` saves of translation fields write the hash too.
- **Live-survey rules**: translation writes go through `_check_content_edit_allowed` (safe edit) and
  `_rescreen_if_live`.
- **Existing editor saves** of base text do not touch hashes — that is what makes stale detectable.
- **ZIP export/import** carries the hashes if present and ignores their absence.
- **Tests**: `survey/tests/test_translation_table.py` (collector, dedup, status, writer, CSV round trip,
  live-survey gating, nav tab); catalog entries for the new creator strings.
- **Docs**: changelog entry, help page `how-to/translate-a-survey`, `help_links.py` key.
