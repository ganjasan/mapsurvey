## ADDED Requirements

### Requirement: Quick Start self-host section
The landing page SHALL display a quick start section showing developers how to self-host Mapsurvey in three commands.

#### Scenario: Three-command code block
- **WHEN** the landing page is rendered
- **THEN** the quick start section SHALL display a styled code block with three steps: (1) git clone the repository, (2) copy .env.example and run docker compose up --build, (3) open localhost:8000

#### Scenario: Section headline
- **WHEN** the quick start section is rendered
- **THEN** it SHALL display a headline: "Prefer to self-host? Three commands."

#### Scenario: Deployment guide link
- **WHEN** the quick start section is rendered
- **THEN** it SHALL display a link to the deployment documentation below the code block

### Requirement: Quick start code block styling
The code block SHALL be presented in a terminal-like visual style.

#### Scenario: Monospace rendering
- **WHEN** the quick start code block is rendered
- **THEN** commands SHALL be displayed in a monospace font with a dark background simulating a terminal window

#### Scenario: Copy functionality
- **WHEN** the code block is rendered
- **THEN** it SHALL include a copy-to-clipboard button or visual affordance

### Requirement: Quick start i18n support
The quick start section headline and surrounding text SHALL support English and Russian. The commands themselves SHALL remain in English.

#### Scenario: Bilingual rendering
- **WHEN** the landing page is rendered in either "en" or "ru"
- **THEN** the section headline and deployment guide link text SHALL render in the active language
- **AND** the terminal commands SHALL remain unchanged in both languages
