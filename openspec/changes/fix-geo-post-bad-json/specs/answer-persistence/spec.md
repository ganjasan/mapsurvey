## ADDED Requirements

### Requirement: A malformed geometry chunk does not fail the submission

The respondent POST handler SHALL skip a feature chunk that is not valid GeoJSON or carries no
usable `geometry`, instead of failing the submission. The remaining
chunks of that question and every other answer in the section SHALL be stored as if the malformed
chunk had not been sent. The handler SHALL log a warning naming the question code and a short prefix
of the skipped chunk.

#### Scenario: A comma-prefixed chunk is skipped and the rest persists

- **GIVEN** a section with a `point` question and a `text_line` question
- **WHEN** the respondent POSTs `",{valid feature}|"` under the point question's code together with
  a text answer
- **THEN** the response is the normal redirect (no 500), no geometry is stored for the first chunk,
  and the text answer is stored

#### Scenario: A valid chunk after a malformed one is kept

- **WHEN** the posted value is `"garbage|{valid feature}|"`
- **THEN** exactly one point answer is stored, from the valid chunk

#### Scenario: JSON that is not a Feature is skipped

- **WHEN** a chunk is `"[]"` or `"{}"`
- **THEN** it stores nothing and the submission succeeds
