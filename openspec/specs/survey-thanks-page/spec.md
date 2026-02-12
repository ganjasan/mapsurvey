### Requirement: Thanks page displays after survey completion
The system SHALL serve a thanks page at `/surveys/<survey_name>/thanks/` that confirms the survey has been completed.

#### Scenario: User completes last section and is redirected to thanks page
- **WHEN** user submits the last section of a survey with default `redirect_url` (`"#"`)
- **THEN** user is redirected to `/surveys/<survey_name>/thanks/`

#### Scenario: Thanks page renders default message
- **WHEN** user visits `/surveys/<survey_name>/thanks/` and `thanks_html` is empty
- **THEN** the page displays the default thank-you message
- **AND** the page extends `base.html` (no map/Leaflet dependencies)

#### Scenario: Thanks page renders custom HTML
- **WHEN** user visits `/surveys/<survey_name>/thanks/` and `thanks_html` is set
- **THEN** the page renders the custom HTML content instead of the default message

#### Scenario: Non-existent survey returns 404
- **WHEN** user visits `/surveys/nonexistent/thanks/`
- **THEN** the server returns HTTP 404

### Requirement: Custom thanks page content with language support
The system SHALL allow survey creators to provide custom HTML content for the thanks page via `SurveyHeader.thanks_html` JSONField, with per-language support following the `Question.choices[].name` pattern.

#### Scenario: Empty thanks_html shows default message
- **WHEN** `thanks_html` is empty (`{}`)
- **THEN** the thanks page displays the default "Thank you" message with a "Take survey again" link

#### Scenario: Multilingual thanks_html resolves by session language
- **WHEN** `thanks_html` is `{"en": "<h1>Thanks!</h1>", "ru": "<h1>Спасибо!</h1>"}`
- **AND** the user completed the survey in Russian (`survey_language` is `"ru"`)
- **THEN** the thanks page renders `<h1>Спасибо!</h1>`

#### Scenario: Language fallback chain
- **WHEN** `thanks_html` is `{"en": "<h1>Thanks!</h1>"}`
- **AND** the user completed the survey in French (`survey_language` is `"fr"`)
- **THEN** the thanks page falls back to `"en"` and renders `<h1>Thanks!</h1>`

#### Scenario: Plain string thanks_html for single-language surveys
- **WHEN** `thanks_html` is a plain string (e.g. `"<h1>Thanks!</h1>"`)
- **THEN** the thanks page renders that string regardless of language

#### Scenario: Session language is read before cleanup
- **WHEN** user arrives at the thanks page with `survey_language` in session
- **THEN** the view reads the language for content resolution before clearing the session

### Requirement: Thanks page clears survey session
The system SHALL clear survey session state when the thanks page is loaded, allowing the user to retake the survey.

#### Scenario: Session is cleared on thanks page load
- **WHEN** user visits the thanks page after completing a survey
- **THEN** `survey_session_id` is removed from the session
- **AND** `survey_language` is removed from the session

#### Scenario: User can retake survey after thanks page
- **WHEN** user navigates to the survey start after visiting the thanks page
- **THEN** a new survey session is created

### Requirement: Custom redirect URL takes precedence
The system SHALL use the survey's custom `redirect_url` when it is set to a value other than `"#"`.

#### Scenario: Survey with custom redirect URL
- **WHEN** user submits the last section of a survey with `redirect_url` set to `"https://example.com"`
- **THEN** user is redirected to `"https://example.com"` (not to the built-in thanks page)

### Requirement: Thanks URL pattern is registered before section pattern
The URL pattern for `thanks/` SHALL be registered before `<section_name>/` in `urls.py` to ensure it takes priority.

#### Scenario: URL resolution priority
- **WHEN** Django resolves `/surveys/<survey_name>/thanks/`
- **THEN** it matches the `survey_thanks` view (not the `survey_section` view)
