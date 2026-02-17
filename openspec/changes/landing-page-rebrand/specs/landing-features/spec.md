## ADDED Requirements

### Requirement: Features section with six cards
The landing page SHALL display a features section containing exactly six feature cards.

#### Scenario: Feature card content
- **WHEN** the landing page is rendered
- **THEN** the features section SHALL display cards for: (1) Interactive map surveys, (2) 13 question types, (3) Multilingual surveys, (4) Data export, (5) Deploy in minutes, (6) Open source

#### Scenario: Each card has icon and description
- **WHEN** the features section is rendered
- **THEN** each card SHALL display an icon, a title, and a short description text

### Requirement: Features section desktop grid layout
The features section SHALL display cards in a responsive grid.

#### Scenario: Desktop layout
- **WHEN** the landing page is rendered on a viewport >= 1024px
- **THEN** the feature cards SHALL display in a 3-column by 2-row grid

#### Scenario: Tablet layout
- **WHEN** the landing page is rendered on a viewport between 768px and 1023px
- **THEN** the feature cards SHALL display in a 2-column grid

#### Scenario: Mobile layout
- **WHEN** the landing page is rendered on a viewport < 768px
- **THEN** the feature cards SHALL stack in a single column

### Requirement: Features section expandable details
Each feature card SHALL support expandable details revealing additional information.

#### Scenario: Card expansion on interaction
- **WHEN** a user clicks or hovers on a feature card
- **THEN** the card SHALL reveal additional detail text describing the feature capabilities

#### Scenario: Collapsed default state
- **WHEN** the features section is first rendered
- **THEN** all feature cards SHALL be in their collapsed state showing only icon, title, and short description

### Requirement: Features section i18n support
All features section text SHALL support English and Russian via Django's i18n framework.

#### Scenario: Bilingual rendering
- **WHEN** the landing page is rendered in either "en" or "ru"
- **THEN** all feature card titles, descriptions, and expanded details SHALL render in the active language
