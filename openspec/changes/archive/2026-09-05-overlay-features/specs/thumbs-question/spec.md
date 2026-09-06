## ADDED Requirements

### Requirement: The `thumbs` input type
A question of type `thumbs` SHALL present two controls (👍 / 👎), store the choice as
`up` or `down`, allow changing the choice, and honour `required` like other single-value
types. It SHALL be available as a top-level question and as a sub-question.

#### Scenario: Answer and change
- **WHEN** a respondent taps 👍 then 👎
- **THEN** the stored value is `down` and only 👎 is highlighted

#### Scenario: Required
- **WHEN** a required thumbs question is left empty and the respondent moves forward
- **THEN** the existing required message appears and the section stays

### Requirement: Thumbs are aggregated as for/against
Exports SHALL emit `up`/`down`; Responses, public results and the object results GeoJSON
SHALL aggregate thumbs as `up`, `down` and share of up.

#### Scenario: Aggregate
- **WHEN** 24 respondents chose 👍 and 7 chose 👎
- **THEN** the aggregate reads `up = 24`, `down = 7`, share 77 %
