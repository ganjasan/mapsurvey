## ADDED Requirements

### Requirement: Use cases section with four cards
The landing page SHALL display a use cases section with exactly four audience-specific cards.

#### Scenario: Card content
- **WHEN** the landing page is rendered
- **THEN** the use cases section SHALL display cards for: (1) Urban Planning, (2) Academic Research, (3) Civic Tech / NGOs, (4) Municipalities

#### Scenario: Each card has icon and scenario description
- **WHEN** the use cases section is rendered
- **THEN** each card SHALL display an icon, a title, and a short paragraph describing how that audience uses Mapsurvey

### Requirement: Use cases desktop layout
The use cases cards SHALL display in a responsive layout.

#### Scenario: Desktop layout
- **WHEN** the landing page is rendered on a viewport >= 1024px
- **THEN** the four use case cards SHALL display in a single row

#### Scenario: Tablet layout
- **WHEN** the landing page is rendered on a viewport between 768px and 1023px
- **THEN** the use case cards SHALL display in a 2x2 grid

#### Scenario: Mobile layout
- **WHEN** the landing page is rendered on a viewport < 768px
- **THEN** the use case cards SHALL stack vertically or display as a tab/accordion interface

### Requirement: Use cases i18n support
All use cases section text SHALL support English and Russian.

#### Scenario: Bilingual rendering
- **WHEN** the landing page is rendered in either "en" or "ru"
- **THEN** all use case titles and descriptions SHALL render in the active language
