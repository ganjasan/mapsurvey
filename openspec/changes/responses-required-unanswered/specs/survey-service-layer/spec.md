## MODIFIED Requirements

### Requirement: Validation settings parsed once
`questions.parse_validation_settings(input_type, data)` SHALL be the one parser of
`validation_settings` (number bounds, spray max dots, file limits clamped to the platform maxima,
multi-feature min ≤ max), used by question create, edit and sub-question create. It SHALL NOT
parse outlier sigma, text minimum length or polygon area factor; such keys already stored are
left untouched and ignored by every reader.

#### Scenario: Create keeps bounds
- **WHEN** a number question is created with `min=1`, `max=10`
- **THEN** its `validation_settings` holds both

#### Scenario: Inverted multi-feature bounds refused
- **WHEN** a polygon question is saved with `min_features=5`, `max_features=2`
- **THEN** `ValidationFailed` names `max_features`

#### Scenario: Removed keys are not written
- **WHEN** a text question is saved with `vs_min_length=5`
- **THEN** its `validation_settings` holds no `min_length` written by that save
