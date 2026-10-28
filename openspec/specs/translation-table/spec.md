# Translation Table

## Purpose

One page per survey and language that lists every creator-written text once, in respondent order,
with its translation beside it; one write path for every translation that does not come from an
entity's own modal; a CSV an outside translator can fill in and the creator can import back.

## Requirements

### Requirement: Translations tab in the survey navigation
The survey navigation strip SHALL carry a fourth tab, **Translations**, between *Survey* and
*Responses*, rendered for every survey and every role. The page SHALL be open to the `viewer` role
and up; editing and import SHALL require the `editor` role. When the survey has fewer than two
`available_languages`, the page SHALL show an empty state that links to the language setting in
Survey settings and SHALL render no table. While an unpublished-changes copy exists, opening the tab
on the live survey SHALL redirect to the draft's tab.

#### Scenario: Single-language survey
- **WHEN** a creator opens the Translations tab of a survey with `available_languages` `["en"]`
- **THEN** the page explains that a second language is added in Survey settings and links there, and no table is shown

#### Scenario: Viewer opens the tab
- **WHEN** a workspace member with the `viewer` role opens the Translations tab of a bilingual survey
- **THEN** the table renders read-only with the export available, and a POST to the row-save or import endpoint is refused with 403

#### Scenario: Live survey with unpublished changes
- **WHEN** a creator opens the Translations tab of a published survey that has an unpublished-changes copy
- **THEN** they are redirected to the Translations tab of that copy

### Requirement: Source and target languages are chosen on the page and remembered
The page SHALL let the creator choose the source column from every language of the survey (default
the primary language) and the target column from every non-primary language (default the first
non-primary language, or the creator's interface language when the survey offers it as a non-primary
language). A row whose chosen source language has no translation SHALL show the primary-language
text marked as such. Statuses SHALL be computed against the primary-language text whatever the
source column shows. Both choices SHALL be carried in the URL and remembered per survey in the
creator's browser, so reopening the tab restores them.

#### Scenario: Translating from a second language
- **WHEN** a survey has languages `["pt", "es", "fr"]`, every row has a Spanish translation, and the creator picks Spanish as the source and French as the target
- **THEN** the source column shows the Spanish texts, the target column edits French, and a row whose Spanish is missing shows the Portuguese text marked "(primary)"

#### Scenario: Choice is restored
- **WHEN** the creator chose `es → fr` yesterday and opens the Translations tab of the same survey today
- **THEN** the page opens on `es → fr`

### Requirement: A language can be added from the page
The target language picker SHALL offer **Add language…** to the survey owner, opening the same
language picker Survey settings uses; choosing a language SHALL append it to `available_languages`
through the settings service and show the table for it. The empty state of a single-language survey
SHALL offer the same picker inline. Editors who are not owners SHALL see no add entry and a hint
that the workspace owner adds languages. Removing a language SHALL remain a Survey settings action.

#### Scenario: Owner adds Spanish from the empty state
- **WHEN** the owner of an English-only survey opens the Translations tab and picks Spanish in the inline picker
- **THEN** `available_languages` becomes `["en", "es"]`, the table renders `en → es` with every row missing, and the survey's status and structure are unchanged

#### Scenario: Editor cannot add
- **WHEN** a workspace member with the `editor` role opens the target picker
- **THEN** there is no Add language entry and the page says the workspace owner adds languages

### Requirement: One row per unique source text, in respondent order
For the chosen non-primary language the table SHALL list every translatable occurrence of the
survey — section title, subheading and Next label; question name and help text (including the
Formatted Text body and sub-questions); every choice option name; group title and description; the
thank-you page — grouped by identical normalised source text and kind (plain or rich), one row per
group, ordered by the first occurrence in respondent order, with the number of occurrences and a
location label for each ("Page 2 · Question 1 · option"). A group's row SHALL show one translation
field; saving it SHALL write that translation to every occurrence of the group. A group whose
occurrences carry different translations SHALL render expanded with one sub-row per occurrence, and
any group SHALL be expandable with *Translate separately*, after which its occurrences are saved
individually. Source text SHALL be shown read-only. Rich fields SHALL be edited as rich text and keep
the source's markup.

#### Scenario: Repeated option text
- **WHEN** "Other" is an option of six questions and "(Select all that apply)" is the help text of four
- **THEN** the table shows one row for each, with usage counts 6 and 4 and the six/four locations listed

#### Scenario: One translation fills every occurrence
- **WHEN** the creator types "Otro" into the "Other" row and it saves
- **THEN** every one of the six questions has `name["es"] == "Otro"` for that option, and the respondent page in Spanish shows "Otro" on each

#### Scenario: Different wording in context
- **WHEN** "Walk" is an option of an activities question and of a mode-of-travel question, and the creator clicks *Translate separately* on its row
- **THEN** the row splits into two sub-rows that save independently, and the next render keeps them split because their translations differ

#### Scenario: Rich text keeps markup
- **WHEN** a section subheading is `<p><em>These questions are optional.</em></p>` and the creator enters its translation in the row's rich editor
- **THEN** the stored `SurveySectionTranslation.subheading` is the entered HTML passed through the creator-HTML coercion, and the respondent sees it with the emphasis

### Requirement: Every row links to its place in the editor
Each table row and each location in a usage list SHALL link into the Survey tab: a page or section
row to that section, a question or option row to that question with its modal opened at the
Translations block of the table's language, the thank-you row to the thank-you panel. Rows SHALL
carry a stable anchor so the browser's Back returns to the same row.

#### Scenario: Open a question from the table
- **WHEN** a creator clicks the location of an option row that belongs to question `Q_123` in section 42
- **THEN** the Survey tab opens with section 42 selected and the modal of `Q_123` open, scrolled to its translation inputs for the table's language

#### Scenario: Back returns to the row
- **WHEN** the creator presses Back in the browser after that
- **THEN** the Translations tab is shown scrolled to the row they left from

### Requirement: Row status is missing, stale or translated
Each occurrence SHALL have a status: **missing** when the source is non-empty and the translation is
empty; **stale** when a source hash was recorded with the translation and the current source text
hashes differently; **translated** otherwise. A group row's status SHALL be missing if any occurrence
is missing, else stale if any is stale, else translated. The source hash SHALL be recorded by every
translation write — the entity modals, the API and MCP services, the thank-you panel, the table and
the CSV import — and SHALL NOT be touched by a save of the base (primary-language) text. A
translation with no recorded hash SHALL read as translated. The table SHALL show per-status counts
and let the creator filter to missing and stale rows.

#### Scenario: Editing the English after translating
- **WHEN** a question named "How often do you visit the park?" has a Spanish translation saved through the question modal, and the creator later changes the English name in the modal
- **THEN** the question's name row reads *stale* in the table, and the English edit changed nothing in the Spanish translation

#### Scenario: Re-translating clears stale
- **WHEN** the creator saves a new Spanish name for that question from the table row
- **THEN** the row reads *translated* and the recorded hash equals the current source hash

#### Scenario: Translation from before hashes existed
- **WHEN** a translation row exists with no recorded source hash
- **THEN** its status is *translated*

### Requirement: The gap engine counts stale rows, the Next label and the thank-you page
`survey_translation_gaps()` SHALL report, in addition to today's missing titles, names, help texts,
descriptions and choice names: a section's missing Next-label translation when the base label is set;
a missing thank-you page translation when the primary-language thank-you page is non-empty; and every
stale occurrence, with the language marked "(outdated)". The editor badges, the publish warning and
the API/MCP `translation_gaps` response SHALL use that one result, and the table's statuses SHALL be
derived from the same functions.

#### Scenario: Publish warning names outdated translations
- **WHEN** a creator publishes a bilingual survey where one question's Spanish name is stale and the thank-you page has no Spanish
- **THEN** the publish confirmation lists that question with "es (outdated)" and "Thank-you page" with "es", and the creator can still acknowledge and publish

### Requirement: One writer for table and import
Every write from the Translations page and the CSV import SHALL go through one function that
takes `{key: text}` (group or occurrence keys), checks the live-survey content lock once, applies the
creator-HTML coercion to rich fields and the existing length caps to plain fields, skips occurrences
that already have a translation unless overwrite was requested, records the source hashes, re-screens
a live survey once, and returns a report of filled, overwritten, skipped and unmatched keys. No view
of this capability SHALL write a translation model, a choices dict or `thanks_html` directly.

#### Scenario: Table save on a published survey
- **WHEN** a creator saves a row on a published survey with live editing enabled
- **THEN** the translation is live for respondents immediately, no unpublished-changes copy is created, and the survey is re-screened

#### Scenario: Content locked
- **WHEN** live editing is switched off and a creator posts a row save on a published survey
- **THEN** the save is refused with the content-locked message and nothing is written

#### Scenario: Script in a rich translation
- **WHEN** a rich row is saved with `<p>Hola</p><script>x()</script>`
- **THEN** the stored translation contains no script element

### Requirement: CSV export of the table
The page SHALL offer a CSV download for the chosen language: UTF-8 with a byte-order mark, columns
`key`, `page`, `element`, `source`, `translation`, `status`, one row per table row in table order
(one per occurrence for expanded groups). Rich sources and translations SHALL be written as plain
text with a blank line between blocks. A cell beginning with `=`, `+`, `-` or `@` SHALL be prefixed
with an apostrophe. The file SHALL be named `<survey slug>-translations-<lang>.csv`.

#### Scenario: Export shape
- **WHEN** a creator downloads the Spanish CSV of a survey whose first page is "Help Shape the Future" with a Start button and an intro block
- **THEN** the first rows are the page title, the Next-button label and the intro text, each with a key, `page` "Page 1: Help Shape the Future", a human `element` label, the English source, the Spanish translation (empty when missing) and the status

### Requirement: CSV import fills the table
The page SHALL accept a CSV upload for the chosen language with an "Overwrite existing
translations" option. Rows SHALL be matched by `key`; a row whose key is missing or unknown SHALL be
matched by exact normalised `source` text; the language SHALL come from the page, not the file.
Matched rows SHALL be written through the single writer; an empty `translation` cell SHALL be skipped.
A rich field receiving plain text SHALL have its blank-line-separated paragraphs wrapped in
paragraphs before coercion. The page SHALL render the report — filled, overwritten, skipped as already
translated, unmatched (with the source text of each) — and SHALL never drop a row silently.

#### Scenario: Round trip
- **WHEN** a creator exports the Spanish CSV, a translator fills the empty `translation` cells, and the creator imports the file
- **THEN** every filled row is written, rows that already had a translation are reported as skipped, and a second export equals the imported file in `source` and `translation`

#### Scenario: Hand-built spreadsheet without keys
- **WHEN** an imported file has no `key` column but its `source` cells equal the survey's English texts
- **THEN** each row is matched by source and written, and rows whose source matches nothing are listed as unmatched

#### Scenario: Overwrite requested
- **WHEN** the import is submitted with "Overwrite existing translations" checked
- **THEN** rows with a non-empty translation replace existing translations and are reported as overwritten

### Requirement: Translations tab is documented
The change SHALL ship an in-app changelog entry, a "Learn more" link from the tab to the help
page `how-to/translate-a-survey` through the help-links registry, and the help page SHALL describe
the table, the statuses and the CSV round trip, including that CSV does not carry inline markup.

#### Scenario: Help link resolves
- **WHEN** the help-site links test runs
- **THEN** the `translate` registry key resolves to an existing page under the help docs
