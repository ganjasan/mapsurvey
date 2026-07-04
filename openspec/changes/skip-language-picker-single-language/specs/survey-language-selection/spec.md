## MODIFIED Requirements

### Requirement: Language selection screen is the first screen for multilingual surveys
The system SHALL display a language selection screen as the first step only when
a respondent opens a survey configured with **more than one** language. Surveys
with zero or exactly one language SHALL skip the picker and go directly to the
first section; a one-language survey SHALL automatically use its single language
for content and record it on the session.

#### Scenario: Multilingual survey entry
- **WHEN** a respondent navigates to a survey that has two or more languages configured
- **THEN** the system MUST redirect to the language selection screen before showing any survey content

#### Scenario: Single-language survey entry
- **WHEN** a respondent navigates to a survey that has exactly one language configured
- **THEN** the system MUST skip the language selection screen, go directly to the first section, render content in that language, and store it as the `SurveySession.language`

#### Scenario: No-language survey entry
- **WHEN** a respondent navigates to a survey that has no languages configured
- **THEN** the system MUST skip the language selection screen and go directly to the first section

#### Scenario: Direct section access for a single-language survey
- **WHEN** a respondent opens a section URL of a one-language survey without a chosen language in session
- **THEN** the system MUST NOT redirect to the picker and MUST default the language to the survey's single language
