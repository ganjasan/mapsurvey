## ADDED Requirements

### Requirement: Problem-solution comparison section
The landing page SHALL display a "Problem → Solution" section that contrasts the status quo with Mapsurvey's value propositions.

#### Scenario: Section content
- **WHEN** the landing page is rendered
- **THEN** the problem-solution section SHALL display a before/after comparison with at least five rows covering: cost ($1,400+/project → free), data control (vendor servers → self-hosted), geometry (pin-only → points/lines/polygons), data export (locked → GeoJSON/CSV), and source code (closed → open-source)

#### Scenario: Desktop layout
- **WHEN** the landing page is rendered on a viewport >= 1024px
- **THEN** the problem-solution section SHALL display as a two-column layout (without Mapsurvey / with Mapsurvey)

#### Scenario: Mobile layout
- **WHEN** the landing page is rendered on a viewport < 768px
- **THEN** the comparison rows SHALL stack vertically as before/after cards

### Requirement: Problem-solution section positioning
The problem-solution section SHALL appear immediately after the hero section.

#### Scenario: Section order
- **WHEN** the landing page is rendered
- **THEN** the problem-solution section SHALL be the second content section after the hero

### Requirement: Problem-solution i18n support
All problem-solution section text SHALL support English and Russian via Django's i18n framework.

#### Scenario: English rendering
- **WHEN** the landing page is rendered with language set to "en"
- **THEN** the problem-solution content SHALL render in English

#### Scenario: Russian rendering
- **WHEN** the landing page is rendered with language set to "ru"
- **THEN** the problem-solution content SHALL render in Russian
