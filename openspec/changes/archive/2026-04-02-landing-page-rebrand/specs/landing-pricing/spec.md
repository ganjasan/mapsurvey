## ADDED Requirements

### Requirement: Pricing section with three tiers
The landing page SHALL display a pricing section with three columns: Free, Pro (coming soon), and Self-Hosted.

#### Scenario: Free tier content
- **WHEN** the pricing section is rendered
- **THEN** the Free tier SHALL display: price $0, limited surveys and responses, hosted on mapsurvey.org, automatic updates, community support, no custom domain, and a "Try Free" CTA button

#### Scenario: Pro tier content
- **WHEN** the pricing section is rendered
- **THEN** the Pro tier SHALL display: price TBD, unlimited surveys and responses, hosted on mapsurvey.org, automatic updates, priority support, custom domain, and a "Notify me" CTA button or link

#### Scenario: Self-Hosted tier content
- **WHEN** the pricing section is rendered
- **THEN** the Self-Hosted tier SHALL display: price $0/forever, unlimited surveys and responses, hosted on user's server, user-managed updates, community support (GitHub), custom domain, and a "Self-Host" CTA button linking to the GitHub repository

### Requirement: Pricing tier CTA actions
Each pricing tier CTA SHALL navigate to the appropriate destination.

#### Scenario: Free tier CTA
- **WHEN** a visitor clicks "Try Free" on the Free tier
- **THEN** the system SHALL navigate to the registration page

#### Scenario: Self-Hosted tier CTA
- **WHEN** a visitor clicks "Self-Host" on the Self-Hosted tier
- **THEN** the system SHALL navigate to the GitHub repository URL

### Requirement: Pricing enterprise contact
The pricing section SHALL include an enterprise contact prompt below the tiers.

#### Scenario: Enterprise contact line
- **WHEN** the pricing section is rendered
- **THEN** a line SHALL be displayed below the pricing tiers: "Need a custom deployment or enterprise support? Contact us"

### Requirement: Pricing responsive layout
The pricing tiers SHALL display responsively.

#### Scenario: Desktop layout
- **WHEN** the pricing section is rendered on a viewport >= 1024px
- **THEN** the three pricing tiers SHALL display side by side in a single row

#### Scenario: Mobile layout
- **WHEN** the pricing section is rendered on a viewport < 768px
- **THEN** the pricing tiers SHALL stack vertically

### Requirement: Pricing i18n support
All pricing section text SHALL support English and Russian.

#### Scenario: Bilingual rendering
- **WHEN** the landing page is rendered in either "en" or "ru"
- **THEN** all pricing tier labels, feature descriptions, CTA labels, and the enterprise contact line SHALL render in the active language
