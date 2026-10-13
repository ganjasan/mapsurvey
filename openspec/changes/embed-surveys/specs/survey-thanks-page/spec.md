## MODIFIED Requirements

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
