## ADDED Requirements

### Requirement: Tech architecture section for developers
The landing page SHALL display a tech architecture section targeting developers and technical evaluators.

#### Scenario: Stack diagram
- **WHEN** the landing page is rendered
- **THEN** the tech architecture section SHALL display a visual representation of the technology stack: Django 4.2 + GeoDjango + PostGIS, with subsystems (survey engine, visual editor, data export, import/export, Leaflet widgets)

#### Scenario: Developer-focused key points
- **WHEN** the tech architecture section is rendered
- **THEN** it SHALL list key technical selling points: Python/Django stack, PostGIS spatial queries, HTMX (no SPA), Docker Compose deployment, and AGPLv3 license

### Requirement: GitHub CTA in tech section
The tech architecture section SHALL include a prominent "View on GitHub" call-to-action.

#### Scenario: GitHub link
- **WHEN** a visitor clicks "View on GitHub" in the tech architecture section
- **THEN** the system SHALL navigate to the GitHub repository URL

### Requirement: Tech section code-style presentation
The stack diagram SHALL be presented in a styled code block or terminal-like visual.

#### Scenario: Terminal aesthetic
- **WHEN** the tech architecture section is rendered
- **THEN** the stack diagram SHALL be displayed in a monospace font with syntax-highlighted or terminal-styled formatting

### Requirement: Tech section i18n support
All tech architecture section text SHALL support English and Russian.

#### Scenario: Bilingual rendering
- **WHEN** the landing page is rendered in either "en" or "ru"
- **THEN** all tech section headings, key points, and CTA labels SHALL render in the active language
