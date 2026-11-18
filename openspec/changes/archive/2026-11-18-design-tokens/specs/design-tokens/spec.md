## ADDED Requirements

### Requirement: One file of design tokens for the creator app
The system SHALL define the creator app's colours, text sizes, spacing, radii and shadows in one
stylesheet of tokens, in two layers: a palette of raw values and tokens named by purpose that refer
to it. Both creator base templates SHALL load it after Bootstrap; the respondent pages and the
marketing pages SHALL NOT load it. The action colour SHALL be the palette's indigo.

#### Scenario: Both creator bases load the tokens
- **WHEN** a page of the creator app is rendered from either base template
- **THEN** it links the tokens stylesheet after Bootstrap

#### Scenario: Respondent and marketing pages keep their own look
- **WHEN** a respondent page or a marketing page is rendered
- **THEN** it does not link the tokens stylesheet

### Requirement: Existing components follow the tokens
The system SHALL set Bootstrap's buttons, links, badges, alerts, form focus and modals from the
tokens, and the variables the survey editor, the builders and the Pro badge defined for themselves
SHALL refer to the tokens, so that a token's value is the look of every component that uses it.

#### Scenario: The primary button is the action colour
- **WHEN** a creator page shows a primary button
- **THEN** its background is the action token, whichever page it is on

#### Scenario: Older variable names
- **WHEN** the editor's or the builder's accent variable is read
- **THEN** it is a reference to the action token

### Requirement: New colours are tokens
The system's test suite SHALL record how many colour literals each creator stylesheet and template
holds and SHALL fail when a file holds more than recorded or a new file holds any.

#### Scenario: A literal is added
- **WHEN** a colour literal is added to a creator template
- **THEN** the test suite fails and names the file
