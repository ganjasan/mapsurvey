# Translation Completeness

Editor-side visibility of missing translations, so the base-language fallback stops silently
masking gaps from the survey author.

## ADDED Requirements

### Requirement: Editor surfaces missing translations per entity
For surveys with two or more `available_languages`, the editor SHALL compute, server-side,
the set of non-primary languages for which each section or question is missing translated
content, and SHALL display a compact indicator listing the missing language codes on the
affected entity. A language counts as missing for an entity when it has no translation row or
an empty translated primary text field (section title, question name), or — for choice-based
questions — when any choice name dict lacks that language's key. Optional texts (subtext,
subheading) SHALL count as missing only when the corresponding base field is non-empty.
Single-language surveys SHALL show no indicators.

#### Scenario: Manually added question with no translations
- **WHEN** a survey has available_languages ["pt", "es", "en"] and a question has no
  translation rows
- **THEN** the question shows an indicator listing "es, en"

#### Scenario: Choice dict missing one language
- **WHEN** a choice question on the same survey has all name dicts containing "pt" and "es"
  but one dict lacking "en"
- **THEN** the question shows an indicator listing "en"

#### Scenario: Fully translated entity shows nothing
- **WHEN** a section has non-empty title translations for every non-primary language and its
  base subheading is empty
- **THEN** no indicator is shown for that section

### Requirement: Publish flow warns about translation gaps
The publish flow SHALL display a warning enumerating the affected entities and their missing
languages before the creator confirms publication, whenever the survey has two or more
`available_languages` and any section or question has missing translations. The warning
SHALL NOT block publication.

#### Scenario: Publishing with gaps
- **WHEN** the creator publishes a trilingual survey where one question lacks es and en
  translations
- **THEN** the publish confirmation shows a warning naming that question and the languages
  "es, en", and the creator can still confirm and publish

#### Scenario: Publishing a complete survey
- **WHEN** every section and question carries non-empty translations for all non-primary
  languages
- **THEN** the publish flow shows no translation warning
