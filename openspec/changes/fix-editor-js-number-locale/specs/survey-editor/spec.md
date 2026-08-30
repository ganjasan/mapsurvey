# survey-editor Specification (delta)

## ADDED Requirements

### Requirement: Numbers emitted into JavaScript are locale-independent
Any number the editor interpolates into inline JavaScript, a `data-*` attribute read by script, or
any other machine-parsed context SHALL be rendered without locale formatting. `USE_L10N` is on and
every non-English language in `LANGUAGES` writes decimals with a comma, so an unguarded float turns
`52.52` into `52,52` and makes the surrounding script fail to parse.

Numbers shown to a person as text SHALL remain localized.

#### Scenario: Map picker initialises under a comma-decimal UI
- **WHEN** the section map picker is rendered for a creator whose UI language writes decimals with a comma
- **THEN** the coordinates in its script are written with a decimal point and the script parses

#### Scenario: Survey settings map initialises under a comma-decimal UI
- **WHEN** the survey settings map block is rendered under such a locale
- **THEN** its coordinates are written with a decimal point

#### Scenario: Numeric question statistics parse under a comma-decimal UI
- **WHEN** the Responses page renders the histogram script for a numeric question under such a locale
- **THEN** the minimum and maximum are written with a decimal point

#### Scenario: Coordinate readouts stay localized for the reader
- **WHEN** the panel shows a coordinate as text for the creator to read
- **THEN** it is formatted for their locale
