## ADDED Requirements

### Requirement: Product showcase and capabilities
The landing page SHALL show the product in four steps — build, collect, analyze, share — each with a screenshot of the demo survey that opens full size, followed by a capabilities grid of six cards.

#### Scenario: Four showcase steps
- **WHEN** the landing page is rendered
- **THEN** the showcase SHALL contain four rows labelled BUILD, COLLECT, ANALYZE and SHARE, each with an inline screenshot and a full-size screenshot for the lightbox

#### Scenario: Six capability cards
- **WHEN** the landing page is rendered
- **THEN** the capabilities section SHALL contain six cards: Questions made for maps, Your data on the map, A map people build together, Built to be answered, Clean and analyse, Export and publish

#### Scenario: Claims match the product
- **WHEN** the showcase or capability copy names a count, a format or a feature
- **THEN** it SHALL be one the product has at the time of release (no "13 question types", no export formats the dialog does not offer)
