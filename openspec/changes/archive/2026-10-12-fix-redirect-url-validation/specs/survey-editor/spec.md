## MODIFIED Requirements

### Requirement: Survey settings editing
The system SHALL provide a settings form (accessible from the editor) to edit SurveyHeader fields: name, organization, available_languages, visibility, redirect_url, and thanks_html.

`redirect_url` SHALL be presented as a choice labelled "After the last page" with two options: "Show the thank-you page" (stored as `"#"`, the default) and "Open a web address". The address input SHALL be shown only when "Open a web address" is chosen, SHALL never be pre-filled with `"#"`, and SHALL carry a help text with an example address. On save the address SHALL be trimmed; a leading `"#"` in front of `http://`/`https://` SHALL be dropped; a value starting with `www.` SHALL get `https://` prepended; the scheme SHALL be lowercased. The result SHALL be accepted only if it is a valid absolute `http://` or `https://` URL; otherwise the form SHALL be invalid with an error on the address field that shows an example. "Open a web address" with an empty address SHALL save as `"#"` without an error.

#### Scenario: Update survey visibility
- **WHEN** the user changes visibility from "private" to "public" and saves
- **THEN** the SurveyHeader.visibility is updated to "public"

#### Scenario: Update available languages
- **WHEN** the user selects ["en", "ru"] as available languages and saves
- **THEN** the SurveyHeader.available_languages is updated to ["en", "ru"]

#### Scenario: Default survey shows the thank-you option
- **WHEN** the owner opens Survey settings on a survey whose `redirect_url` is `"#"`
- **THEN** "Show the thank-you page" is selected and the address input is hidden and empty

#### Scenario: Survey with a link shows the address option
- **WHEN** the owner opens Survey settings on a survey whose `redirect_url` is `"https://example.com/x"`
- **THEN** "Open a web address" is selected and the address input contains `"https://example.com/x"`

#### Scenario: A valid address is saved
- **WHEN** the owner chooses "Open a web address", enters `"https://www.example.org/project"` and saves
- **THEN** SurveyHeader.redirect_url is `"https://www.example.org/project"`

#### Scenario: A pasted anchor in front of the address is dropped
- **WHEN** the owner enters `"#https://www.example.org/project"` and saves
- **THEN** SurveyHeader.redirect_url is `"https://www.example.org/project"`

#### Scenario: A bare www address gets a scheme
- **WHEN** the owner enters `"www.example.org/project"` and saves
- **THEN** SurveyHeader.redirect_url is `"https://www.example.org/project"`

#### Scenario: An invalid address is refused
- **WHEN** the owner enters `"#projectname"`, `"/thanks"` or `"Thank you!"` and saves through autosave
- **THEN** the response is 400 with an error on the `redirect_url` field and SurveyHeader.redirect_url is unchanged

#### Scenario: Choosing the thank-you page clears the address
- **WHEN** the owner switches from "Open a web address" to "Show the thank-you page" and saves
- **THEN** SurveyHeader.redirect_url is `"#"`

#### Scenario: An empty address saves as the thank-you page
- **WHEN** the owner chooses "Open a web address" but leaves the address empty and saves
- **THEN** SurveyHeader.redirect_url is `"#"` and no error is shown
