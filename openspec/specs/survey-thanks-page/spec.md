# Survey Thanks Page Specification

## Purpose
What a respondent sees after finishing a survey — the built-in thanks page, custom multilingual content, session cleanup, the precedence of a custom redirect URL, and the URL-pattern ordering the page depends on.
## Requirements
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
The system SHALL send a respondent who submits the last section to the survey's `redirect_url` only when that value, after the same tidying the settings form applies (a leading `#` before `http(s)://` dropped, a bare `www.` given `https://`, the scheme lowercased), is a valid absolute `http://` or `https://` URL. Any other stored value — `"#"`, an empty string, an anchor such as `"#tag"`, a relative path such as `"/thanks"`, or free text — SHALL send the respondent to the built-in thanks page. The same rule SHALL apply to every place that redirects to `redirect_url`: the HTMX final-section response (`HX-Redirect`), the plain final-section redirect, and the entry redirect of a survey with no start section. One exception: when the submit comes from a framed document (request header `MS-Embedded: 1`, see `survey-embedding`), a valid `redirect_url` SHALL NOT be navigated to; the respondent SHALL be sent to the built-in thanks page with `?next=<redirect_url>`, which renders a "Continue" link opening that URL in the top window.

#### Scenario: Survey with custom redirect URL
- **WHEN** user submits the last section of a survey with `redirect_url` set to `"https://example.com"`
- **THEN** user is redirected to `"https://example.com"` (not to the built-in thanks page)

#### Scenario: Framed submit stays on the thanks page
- **WHEN** user submits the last section through HTMX with `MS-Embedded: 1` on a survey whose `redirect_url` is `"https://example.com"`
- **THEN** the response carries `HX-Redirect` with `/surveys/<survey_name>/thanks/?next=https://example.com`

#### Scenario: Anchor value sends the respondent to the thanks page
- **WHEN** user submits the last section of a survey whose `redirect_url` is `"#projectname"`
- **THEN** user is redirected to `/surveys/<survey_name>/thanks/`

#### Scenario: Anchor value over HTMX sends the respondent to the thanks page
- **WHEN** user submits the last section through HTMX on a survey whose `redirect_url` is `"#projectname"`
- **THEN** the response carries `HX-Redirect` with the thanks page URL, not `"#projectname"`

#### Scenario: A link typed after the default anchor is followed
- **WHEN** user submits the last section through HTMX on a survey whose `redirect_url` is `"#https://example.com"`
- **THEN** the response carries `HX-Redirect: https://example.com`

#### Scenario: Relative path or free text sends the respondent to the thanks page
- **WHEN** user submits the last section of a survey whose `redirect_url` is `"/obrigada"`, `"-"` or `"Thank you!"`
- **THEN** user is redirected to `/surveys/<survey_name>/thanks/`

### Requirement: Thanks URL pattern is registered before section pattern
The URL pattern for `thanks/` SHALL be registered before `<section_name>/` in `urls.py` to ensure it takes priority.

#### Scenario: URL resolution priority
- **WHEN** Django resolves `/surveys/<survey_name>/thanks/`
- **THEN** it matches the `survey_thanks` view (not the `survey_section` view)

### Requirement: Stored redirect values are normalised
The system SHALL store `redirect_url` only as `"#"` or a valid absolute `http://`/`https://` URL. A one-time data migration SHALL rewrite existing rows: a value of the form `"#http://…"` or `"#https://…"` SHALL become the URL without the leading `#` when the result is valid; a scheme written in other case (`"Https://…"`) SHALL be lowercased; every other value that is not `"#"` or a valid http(s) URL SHALL become `"#"`. ZIP import (`import_survey_from_zip`, also used by AI generation) SHALL apply the same normalisation to the archive's `redirect_url`.

#### Scenario: Migration salvages a URL typed after the default anchor
- **WHEN** the migration runs over a survey whose `redirect_url` is `"#https://www.example.org/about"`
- **THEN** the stored value becomes `"https://www.example.org/about"`

#### Scenario: Migration resets an unusable value
- **WHEN** the migration runs over surveys whose `redirect_url` is `"#tag"`, `"/obrigada"`, `"-"` or `"Wat is je naam"`
- **THEN** each stored value becomes `"#"`

#### Scenario: Migration leaves valid values alone
- **WHEN** the migration runs over surveys whose `redirect_url` is `"#"` or `"https://example.com/x"`
- **THEN** the stored values are unchanged

#### Scenario: ZIP import normalises the value
- **WHEN** a survey archive with `"redirect_url": "#thanks"` is imported
- **THEN** the imported survey's `redirect_url` is `"#"`

