## ADDED Requirements

### Requirement: Every respondent page renders in the survey language
The system SHALL activate the survey's language on every respondent page of that survey, not only
on its sections. The language is the respondent's selection for this survey when one exists;
otherwise the browser's language when the survey offers it; otherwise the survey's first language.

#### Scenario: Thanks page after a Polish survey
- **WHEN** a respondent whose browser is set to English completes a survey taken in Polish
- **THEN** the thanks page interface MUST render in Polish

#### Scenario: Password gate of a single-language survey
- **WHEN** a respondent opens a password-protected survey whose only language is German and enters a wrong password
- **THEN** the page and the error message MUST render in German

#### Scenario: Password gate of a multilingual survey before a language is chosen
- **WHEN** a respondent with a French browser opens a password-protected survey offering English and French
- **THEN** the password page MUST render in French

#### Scenario: Closed survey page
- **WHEN** a respondent opens a closed survey whose language is Spanish
- **THEN** the closed-survey page MUST render in Spanish

#### Scenario: Abuse report page
- **WHEN** a respondent follows "Report this survey" from a Dutch survey
- **THEN** the report form, its reasons and the confirmation MUST render in Dutch

#### Scenario: Survey language does not leak into the editor
- **WHEN** a creator who also took a survey in Polish opens the editor
- **THEN** the editor MUST render in the creator's own interface language
