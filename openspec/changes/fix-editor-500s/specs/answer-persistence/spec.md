# answer-persistence Specification (delta)

## ADDED Requirements

### Requirement: A mistyped posted value never costs a submission
When computing conditional visibility for a submitted section, the system SHALL ignore any posted
value for a controller question that is not a choice identifier, rather than raising. A question
whose stored `input_type` disagrees with the widget the respondent was served — the usual cause
being a creator changing the type while respondents hold the page open — SHALL degrade to "this
controller contributes nothing to visibility", never to a failed request.

#### Scenario: Geometry posted under a controller question
- **WHEN** a section is submitted with pipe-joined GeoJSON under the code of a question stored as `choice` or `multichoice`
- **THEN** the submission is processed, the remaining answers are stored, and no 500 is returned

#### Scenario: Ordinary choice submissions are unaffected
- **WHEN** a section is submitted with integer choice identifiers under a controller question
- **THEN** conditional visibility is computed from those identifiers exactly as before
