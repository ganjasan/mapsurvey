## ADDED Requirements

### Requirement: Comparison table section
The landing page SHALL display a feature comparison table showing Mapsurvey against three competitors: Maptionnaire, KoBoToolbox, and ArcGIS Survey123.

#### Scenario: Table dimensions
- **WHEN** the landing page is rendered
- **THEN** the comparison table SHALL have 4 product columns (Mapsurvey, Maptionnaire, KoBoToolbox, ArcGIS Survey123) and at least 10 feature rows

#### Scenario: Feature rows
- **WHEN** the comparison table is rendered
- **THEN** it SHALL include rows for: open source, self-hostable, cost, mark a place (point), draw a route (line), outline an area (polygon), data export with geodata, public-facing surveys, visual survey editor, and data control

#### Scenario: Mapsurvey column emphasis
- **WHEN** the comparison table is rendered
- **THEN** the Mapsurvey column SHALL be visually emphasized (highlighted or distinct styling) relative to competitor columns

### Requirement: Comparison table responsive behavior
The comparison table SHALL remain usable on mobile screens.

#### Scenario: Desktop layout
- **WHEN** the comparison table is rendered on a viewport >= 1024px
- **THEN** the full table SHALL be visible without horizontal scrolling

#### Scenario: Mobile layout
- **WHEN** the comparison table is rendered on a viewport < 768px
- **THEN** the table SHALL be horizontally scrollable or transform into an accordion format

### Requirement: Comparison section tagline
The comparison section SHALL display a tagline reinforcing the cost advantage.

#### Scenario: Tagline content
- **WHEN** the comparison section is rendered
- **THEN** a tagline SHALL be displayed below the table: "Other platforms charge $1,400+ per project. Mapsurvey is free."

### Requirement: Comparison table i18n support
All comparison section text SHALL support English and Russian.

#### Scenario: Bilingual rendering
- **WHEN** the landing page is rendered in either "en" or "ru"
- **THEN** all table headers, row labels, the tagline, and footnotes SHALL render in the active language
