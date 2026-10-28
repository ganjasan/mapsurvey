## MODIFIED Requirements

### Requirement: Session detail modal lists sub-answers per geo object
Each geo object is its own Answer row in the session detail surface — the modal on the pre-V2 path, the drawer/overlay/full-screen surface under `RESPONSES_V2`. The surface SHALL show, under each geo answer row, that object's sub-answer name/value pairs. When a session contains several objects for the same geo question, the objects SHALL carry a numbered label ("point feature 1", "point feature 2") so their attributes can be told apart; a single object keeps the un-numbered label. That label SHALL also title the object in the session's full-size map, so an object on the map can be matched to its row. The row's displayed value is specified by `session-geo-map` (coordinates or vertex count); the label carries the disambiguation. Object ordering SHALL be deterministic (creation order). Sub-answer values SHALL be rendered through template autoescaping, and any JSON payload embedding feature properties SHALL NOT be marked safe.

#### Scenario: Session with two points for one geo question
- **WHEN** the detail surface opens for a session whose geo question has two point answers with different sub-answers
- **THEN** the two geo objects carry distinct numbered labels and each row shows its own object's attribute list

#### Scenario: Geo answer without sub-answers
- **WHEN** a geo answer in the session has no child answers
- **THEN** its row renders as today, with no empty attribute group

#### Scenario: Matching a mapped object to its row
- **WHEN** the creator opens the session's full-size map for a question holding several objects
- **THEN** each object on the map is titled with the same label its row carries
