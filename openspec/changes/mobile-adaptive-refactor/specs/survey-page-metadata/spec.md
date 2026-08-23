# survey-page-metadata

## ADDED Requirements

### Requirement: Survey pages carry a meaningful title
Respondent survey pages (section pages and the thanks page) SHALL render a non-empty
`<title>` containing the survey's display name.

#### Scenario: Section page title
- **WHEN** a respondent opens any survey section
- **THEN** the document title contains the survey name

### Requirement: Survey pages declare their language
Respondent survey pages SHALL set the `lang` attribute on the root `<html>` element to the
language the survey content is being served in.

#### Scenario: Language attribute matches content
- **WHEN** a respondent views a survey in a selected content language
- **THEN** `html[lang]` equals that language's code
