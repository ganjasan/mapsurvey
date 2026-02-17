## ADDED Requirements

### Requirement: Social proof trust signals section
The landing page SHALL display a social proof section with trust signals to compensate for early-stage user base.

#### Scenario: GitHub stars badge
- **WHEN** the landing page is rendered
- **THEN** the social proof section SHALL display a GitHub stars counter badge that reflects the current star count from the repository

#### Scenario: Technology provenance
- **WHEN** the social proof section is rendered
- **THEN** it SHALL display a statement associating Mapsurvey with well-known Django/PostGIS users (e.g., "Built with the same technologies as Instagram, Pinterest, and NASA")

#### Scenario: Institutional origin
- **WHEN** the social proof section is rendered
- **THEN** it SHALL display a statement about Mapsurvey's origin: "Born from urban research at ITMO University, St. Petersburg"

#### Scenario: Open-source license credibility
- **WHEN** the social proof section is rendered
- **THEN** it SHALL display a statement about the open-source license credibility

### Requirement: GitHub stars badge dynamic update
The GitHub stars badge SHALL reflect the actual star count from the repository.

#### Scenario: Badge source
- **WHEN** the social proof section is rendered
- **THEN** the GitHub stars badge SHALL use the shields.io badge or GitHub API to display the current star count

### Requirement: Social proof i18n support
All social proof section text SHALL support English and Russian.

#### Scenario: Bilingual rendering
- **WHEN** the landing page is rendered in either "en" or "ru"
- **THEN** all trust signal statements SHALL render in the active language
