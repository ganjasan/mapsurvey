## ADDED Requirements

### Requirement: Hero headline communicates open-source PPGIS positioning
The hero section SHALL display an H1 headline that communicates Mapsurvey's positioning as an open-source participatory mapping platform.

#### Scenario: H1 content
- **WHEN** the landing page is rendered
- **THEN** the hero section SHALL display an H1 element with text "Open-source platform for participatory mapping"

#### Scenario: Subheadline content
- **WHEN** the landing page is rendered
- **THEN** the hero section SHALL display a subheadline below the H1 with text describing that users can create map-based surveys where people mark places, draw routes, and outline areas, and that it is free, open source, and self-hostable

### Requirement: Dual CTA buttons
The hero section SHALL display two call-to-action buttons: a primary "Try Free" button and a secondary "Self-Host" button.

#### Scenario: Primary CTA leads to sign-up
- **WHEN** an unauthenticated visitor clicks "Try Free"
- **THEN** the system SHALL navigate to the registration page

#### Scenario: Primary CTA for authenticated user leads to dashboard
- **WHEN** an authenticated user clicks "Try Free"
- **THEN** the system SHALL navigate to the editor dashboard

#### Scenario: Secondary CTA leads to GitHub
- **WHEN** a visitor clicks "Self-Host"
- **THEN** the system SHALL navigate to the GitHub repository URL

### Requirement: Trust badges
The hero section SHALL display trust badges below the CTA buttons to reinforce key value propositions.

#### Scenario: Badge content
- **WHEN** the landing page is rendered
- **THEN** the hero section SHALL display exactly four trust badges: "Open Source", "Free to Start", "Self-Hostable", "GDPR-Friendly"

#### Scenario: Badge ordering
- **WHEN** the landing page is rendered
- **THEN** the trust badges SHALL appear in a single horizontal row on desktop and wrap gracefully on mobile

### Requirement: Product visual
The hero section SHALL display a product screenshot or interactive visual alongside the headline on desktop, and below the headline on mobile.

#### Scenario: Desktop layout
- **WHEN** the landing page is rendered on a viewport >= 1024px
- **THEN** the hero SHALL display the headline/CTA on the left and the product visual on the right in a two-column layout

#### Scenario: Mobile layout
- **WHEN** the landing page is rendered on a viewport < 768px
- **THEN** the hero SHALL display the headline/CTA first, followed by the product visual below

#### Scenario: Visual content
- **WHEN** the hero product visual is rendered
- **THEN** it SHALL display a screenshot of the survey respondent interface showing a map with drawn geometry (not abstract graphics)

### Requirement: Hero section i18n support
All hero section text content SHALL support English and Russian via Django's i18n framework.

#### Scenario: English rendering
- **WHEN** the landing page is rendered with language set to "en"
- **THEN** the hero headline, subheadline, CTA labels, and trust badge labels SHALL render in English

#### Scenario: Russian rendering
- **WHEN** the landing page is rendered with language set to "ru"
- **THEN** the hero headline, subheadline, CTA labels, and trust badge labels SHALL render in Russian
