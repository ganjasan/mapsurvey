## Context

Translations today ride along with each entity's own autosave POST as `translation_<lang>_<field>`
keys, saved by `services/common.save_translations()` into `SurveySectionTranslation` (title,
subheading, next_label), `QuestionTranslation` (name, subtext) and `QuestionGroupTranslation` (title,
description); choice names are per-language dicts inside `Question.choices[i].name`; the thank-you
page is `SurveyHeader.thanks_html[lang]` through `services/surveys.set_thanks()`. The primary language
(`available_languages[0]`) lives in base fields only (migration 0052). `survey/translation_gaps.py`
is the one gap engine (badges, publish warning, API/MCP 409) and knows nothing about `next_label`,
the thank-you page or outdated translations. There is no translation-specific view, URL or form, no
"stale" concept, and no CSV path for translations. Live-survey rules: translations are a SAFE edit,
but a write that goes only through `save_translations` skips `assert_content_editable`,
`LIVE_EDIT_SAVED` and `rescreen_if_live` — a new write path must call them itself.

The reference for the table's shape is the customer's own spreadsheet (Page / Element / English /
Spanish): a translator wants every text once, in reading order, with just enough context to place it.

## Goals / Non-Goals

**Goals:**
- One page where a creator (or a bilingual colleague) translates a whole survey into one language
  without opening a single modal, and sees at a glance what is missing or outdated.
- A CSV an outside translator can fill in a spreadsheet and the creator can import back — including a
  spreadsheet built by hand from the exported layout, matched by source text when keys are absent.
- One writer for every translation write that is not the existing modals, so the AI job of #393
  plugs into the same function.
- Outdated translations become visible (stale) instead of silently serving old wording.

**Non-Goals:**
- AI translation, glossary, the machine-translated mark, per-entity re-translate (later items of #393).
- Replacing the inline translation blocks in the modals; they stay as they are.
- Translating respondents' answers or reference-layer objects.
- Changing how respondents pick or see a language.

## Decisions

### D1. Rows are occurrences; the table groups them by identical source text
A **occurrence** is one translatable field of one entity: `section:<code>[#n]:title|subheading|next_label`,
`question:<code>:name|subtext`, `question:<code>:choice:<choice code>`, `group:<code>:title|description`,
`survey:thanks`. (`#n` is the ordinal among sections sharing a code — section codes are not unique
within a survey.) A **group** is the set of occurrences whose normalised source text (whitespace
collapsed; for rich fields the sanitised HTML) and kind (plain / rich) are equal; its key is
`t:<first 12 hex of sha1(kind + "\n" + normalised source)>`.

The table shows one row per group, in respondent order of its first occurrence, with a usage count
and the location labels of its occurrences ("Page 2 · Question 1 · option"). Typing into a group row
writes the same translation to every occurrence. A group whose occurrences already carry *different*
translations renders expanded — one sub-row per occurrence — and any group can be expanded with
"Translate separately" (the customer's reviewer translated "Walk" as "Caminar" under activities and
"Caminando" under modes of travel, and that must stay possible).

*Alternative considered*: one row per occurrence with a "same as above" hint — rejected: on a
30-question survey "Other" and "(Select all that apply)" appear a dozen times each; the epic's point is
that they are typed once.

### D2. Stale = stored source hash ≠ current source hash, kept in a side table keyed by codes
A new model `TranslationSource(survey FK → canonical SurveyHeader, key, language, source_hash,
updated_at)`, unique on `(survey, key, language)`, where `key` is the occurrence key of D1 and
`source_hash` is sha1 of the normalised source at the moment the translation was written. Status of
an occurrence: **missing** when the translation is empty and the source is non-empty; **stale** when a
hash row exists and differs from the current source; **translated** otherwise (a translation with no
hash row — everything written before this change, ZIP imports, duplicates — reads as translated until
its source changes *and* it is saved again, which is the honest answer: we do not know).

Why a side table keyed by `canonical_of(survey)` + code rather than a column on each translation model
plus keys inside `choices[i]` and `thanks_html`: (a) the five sources get one uniform mechanism;
(b) the choice dict is rebuilt by the question modal's JavaScript on every save (`.choice-name-<lang>`
inputs → fresh objects), so a hash inside the dict would be dropped by every modal save; (c) codes are
stable across the draft copy, publishing and restored versions, so nothing has to be copied on any of
those paths — the lesson of #329 (a hand-written copy list silently dropping fields). The cost is that
a hash can describe the draft while the live copy still has the old source; that is fine because
content edits, translations included, are refused on the live copy while a draft exists, and the tab
redirects to the draft like Build does.

Hashes are written by **every** translation write: `save_translations()` (modals, API, MCP) and
`set_thanks()` gain a hash write for each language they save, `_apply_choices` writes hashes for choice
names whose per-language value changed, and the table writer of D3 writes them for what it saves. Base
text saves never touch hashes — that is exactly what makes stale detectable.

### D3. One writer: `translation_table.apply()`
`survey/translation_table.py` holds the collector and the writer:

- `collect(survey, language) -> TableRows`: walks sections → groups/questions (sub-questions after their
  parent) → choices, then the thank-you page, building occurrences with source, translation, location
  label, status; then groups them (D1).
- `apply(actor, survey, language, values: {key: text}, *, overwrite=False) -> Report`: `key` may be a
  group key (fills every occurrence of the group) or an occurrence key. It calls
  `locks.assert_content_editable(survey)` once, resolves keys against `collect()`, skips occurrences
  that already have a translation unless `overwrite`, routes each write to the entity's existing
  service path (`save_translations` for sections, questions and groups; a narrow
  `questions.set_choice_names(question, language, {code: text})` that mutates only `name[lang]` and
  saves `choices` with `update_fields`; `surveys.set_thanks` for the thank-you page), passes rich
  values through `coerce_creator_html`, writes the hashes, emits one `LIVE_EDIT_SAVED` and
  `rescreen_if_live` when the survey is live, and returns `Report(filled, overwritten, skipped,
  unmatched)`.
- `stale_keys(survey, language)` for the gap engine.

The HTMX row save, the CSV import and (later) the AI job are the three callers; none of them touches a
model directly. Plain fields keep their existing caps (`next_label` 30, titles 512) through the same
`caps` argument the modals use.

### D4. The gap engine learns stale, the Next label and the thank-you page
`survey_translation_gaps()` stays the one source for the badges, the publish warning and the API 409,
and is extended in place: a section's `next_label` counts when the base label is set, the thank-you
page counts when `thanks_html[primary]` is non-empty (one entry labelled "Thank-you page"), and stale
occurrences are reported with the language suffixed "(outdated)". The table's statuses are computed by
the same functions, so the table, the badges and the warning cannot disagree.

### D5. Page, URL and permissions follow the Responses tab
- Fourth tab in `_survey_nav_tabs.html` between Survey and Responses: `fa-language` "Translations",
  `active_tab == 'translations'`. Always rendered; the desktop strip is what the mobile top strip shows,
  and the page has a single pane, so it includes no `_mobile_nav.html` bottom bar.
- `survey/translation_views.py`: `editor_survey_translations` (`viewer` and up; viewers get the table
  read-only and the export), `editor_survey_translation_save` (HTMX POST, `editor`), `_export`
  (GET, `viewer`), `_import` (POST, `editor`). URLs `editor/surveys/<uuid>/translations/[…]`. Language
  from `?lang=`; default = the first non-primary language.
- Fewer than two languages → the page renders the empty state with a link to `?panel=settings`
  (languages live in Survey settings), never a table.
- While an unpublished-changes copy exists, the tab on the live survey redirects to the draft's tab
  (same rule as Build), because content edits are refused on the live copy.
- Every row links back into the Survey tab: the page row and section rows to
  `editor_survey_detail?section=<id>` (exists), question and option rows to
  `?section=<id>&question=<id>` (**new**: `survey_detail.html` opens the question modal for that id
  once the section is rendered and scrolls it to the Translations block of the table's language, by
  `#translations-<lang>`), the thank-you row to `?panel=thanks` (exists). Each table row carries
  `id="row-<key>"`, so the Back button lands on the same row.
- Row editing: plain rows are a textarea that autosaves on change through the HTMX endpoint, which
  re-renders the row with its status (the editor's saved/saving/error indicator pattern); rich rows get
  a Quill instance on first focus and post HTML. Each row shows the source on the left, read-only.

### D8. Source and target languages are chosen on the page, remembered, and languages are added there
Nothing in the table assumes English: the **source** column is any language of the survey, default
the primary (`available_languages[0]`, whose text lives in the base fields); where the chosen source
language has no translation for a row the primary text is shown with a "(primary)" mark. Statuses
and hashes are always relative to the primary text — *stale* means the original changed. The
**target** column is any non-primary language, default the first one, or the creator's interface
language when the survey has it and it is not the primary. Both choices live in the URL
(`?from=pt&to=es`, so the link can be sent to a colleague) and are remembered per survey in
`localStorage['msTranslations:<uuid>']`, browser-only like the Responses layer panel.

The target picker ends with **+ Add language…**, which opens the same `language_picker.html` the
settings panel uses and saves through `services.surveys.update_settings(partial=True)` — the one
path that writes `available_languages` — then reloads the table on the new language. The empty state
offers the same picker inline instead of sending the creator to Survey settings. Adding a language
is an owner action, as in Survey settings; editors see the picker without that entry and a hint
naming who can add one. Removing a language stays in Survey settings (it drops translations and
deserves the settings panel's confirmation).

*Alternative considered*: default the source column to the creator's interface language — rejected:
a creator with a Russian interface and an `en, es` survey has no Russian text to show; the primary
language of the survey is the creator's language in practice.

### D9. The modal blocks stay as a read-only mirror that links to the row
The Translations block in `section_detail_form.html`, `question_form_modal.html` and
`group_form_modal.html`, the per-language name columns of the choices table and the non-primary
tabs of `thanks_panel.html` keep rendering the stored translations, but every input is `disabled`
(so nothing is posted — the `translation_<lang>_*` and per-language `choices_json` values stop
reaching `save_translations` from the UI; the API and MCP services keep writing through it). Each
field is wrapped in a link to `editor_survey_translations?to=<lang>#row-<occurrence key>`; a hover
title and one line under the block heading say "Translations are edited on the Translations tab".
The choices JS keeps building the per-language dict from the (disabled) inputs so an unchanged dict
round-trips; `_apply_choices` compares per-language values and writes nothing for languages whose
inputs were disabled (they arrive unchanged). The row anchor in the table is the occurrence key, so a
grouped row is found through any of its occurrences (`#row-<occurrence key>` resolves to the group
row that contains it, expanded if needed).

Why not remove the blocks: a creator opening a question wants to see that a Spanish text exists
without leaving the modal, and the block is the natural place to discover the new tab. Why not keep
them editable: two write paths for the same text is how stale hashes and "which is current" questions
start; the customer's reviewer edits in a table, not in modals.

### D6. CSV: the customer's layout, with a key column, matched by key then by source
Export (`?lang=es&format=csv`): UTF-8 with BOM, columns `key, page, element, source, translation,
status`, one row per group (per occurrence for expanded groups), in table order; rich sources are
exported as plain text with a blank line between blocks (a translator works in Excel, not in HTML);
cells starting with `= + - @` are prefixed with `'` (no formula injection; the import strips it back).
File name `<survey slug>-translations-<lang>.csv`.

Import (`<input type=file>` + "Overwrite existing translations" checkbox): decoded with `utf-8-sig`,
delimiter sniffed (the `_read_csv` helper of the layer CSV import, lifted into a shared module), rows
matched by `key`; a row with no or unknown key is matched by exact normalised `source` (so a
spreadsheet built from an earlier export, or by hand in the same shape, still lands). A rich field
receiving plain text has its blank-line paragraphs wrapped in `<p>` before `coerce_creator_html`
(inline markup is not carried by CSV — the page says so next to the import). The report (filled /
overwritten / skipped / unmatched with the offending source text) renders above the table; nothing is
dropped silently. The language is the page's `?lang=`, not read from the file.

### D7. Catalogue, changelog, help
New creator strings go into all ten offered catalogues by hand (`TranslationCatalogHygieneTest`); the
changelog entry `2026-10-xx-translations-tab.html` (`kind: new`, `link: editor_dashboard` — the entry
cannot link to a survey-specific page); help page `how-to/translate-a-survey.md` already exists and
gets the table and CSV steps plus a registry key `translate` in `help_links.py`, used by the tab's
"Learn more".

## Risks / Trade-offs

- [Grouping by text merges strings that should differ in context] → the group row lists every
  location; "Translate separately" expands it; differing existing translations expand automatically.
- [Hash side table drifts from reality after ZIP import / duplicate / restore] → absence of a row
  reads as translated, never as stale; the first save from any path writes the row. Documented in
  the help page as "outdated is tracked from the moment a translation is saved on this page or in a
  modal".
- [Section codes repeat] → the `#n` ordinal in the key; a mismatch only mis-states a status, never
  writes to the wrong entity, because `apply()` resolves keys through `collect()` of the same survey.
- [Extending the gap engine adds 409s for API/MCP publishers] → they already acknowledge gaps; the
  new entries are the Next label, the thank-you page and stale rows, all genuine gaps.
- [Quill per rich row on a long survey] → lazy init on focus; a survey has a handful of rich fields.
- [Synchronous CSV import on a large survey] → a survey's translation CSV is a few hundred rows; the
  layer CSV import is synchronous too.
- [Export of rich text as plain text loses inline bold on re-import] → stated on the page; the table
  itself keeps markup.

## Migration Plan

1. Migration `0105_translationsource` creates the side table (no data migration — absence = unknown).
2. Deploy; the tab appears for every survey. Rollback = revert the deploy; the table is harmless.

## Open Questions

- None blocking. Whether viewers should see the tab at all (vs. 403) is decided as "read-only + export"
  to match Responses; revisit if a customer objects.
