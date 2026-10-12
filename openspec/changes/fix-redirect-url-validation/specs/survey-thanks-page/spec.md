## MODIFIED Requirements

### Requirement: Custom redirect URL takes precedence
The system SHALL send a respondent who submits the last section to the survey's `redirect_url` only when that value, after the same tidying the settings form applies (a leading `#` before `http(s)://` dropped, a bare `www.` given `https://`, the scheme lowercased), is a valid absolute `http://` or `https://` URL. Any other stored value — `"#"`, an empty string, an anchor such as `"#tag"`, a relative path such as `"/thanks"`, or free text — SHALL send the respondent to the built-in thanks page. The same rule SHALL apply to every place that redirects to `redirect_url`: the HTMX final-section response (`HX-Redirect`), the plain final-section redirect, and the entry redirect of a survey with no start section.

#### Scenario: Survey with custom redirect URL
- **WHEN** user submits the last section of a survey with `redirect_url` set to `"https://example.com"`
- **THEN** user is redirected to `"https://example.com"` (not to the built-in thanks page)

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

## ADDED Requirements

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
