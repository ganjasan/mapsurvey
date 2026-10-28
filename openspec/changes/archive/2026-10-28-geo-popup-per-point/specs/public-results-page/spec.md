## MODIFIED Requirements

### Requirement: Anonymous geo display
The public page SHALL render geo answers (points/lines/polygons) as anonymous geometry. Each geometry's popup SHALL expose only per-point attributes that the creator explicitly selected — namely the **sub-questions of that geo question** — resolved from that geometry's own sub-answers (`parent_answer`). Popups SHALL NOT be filled from session-level answers, SHALL NOT include free-text answers, and SHALL NEVER expose record identifiers (session id, IP, UTM, timestamps). A geo question with no eligible (non-text) sub-questions SHALL render anonymous geometry only.

#### Scenario: Default popup is empty of attributes
- **WHEN** a map block has no popup fields selected
- **THEN** each feature's properties are empty and no identifiers appear anywhere in the payload

#### Scenario: Popup shows only selected sub-question attributes, per point
- **WHEN** a map block selects one sub-question of its geo question as a popup field
- **THEN** each point's popup shows that point's own answer to the sub-question, and points from the same respondent can show different values

#### Scenario: Free-text sub-answers are never shown
- **WHEN** a geo question has a free-text sub-question
- **THEN** it is not offered as a popup field and never appears in any point's popup

#### Scenario: Editor offers the geo question's sub-questions as popup fields
- **WHEN** the creator configures a map block whose geo question has sub-questions
- **THEN** the "Geo popup fields" picker lists those sub-questions (not unrelated top-level questions)
