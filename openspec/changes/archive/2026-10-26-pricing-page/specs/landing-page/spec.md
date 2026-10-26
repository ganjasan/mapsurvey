## MODIFIED Requirements

### Requirement: Footer
Every page built on `base_landing.html` SHALL display a light footer laid out after Notion's: a brand block on the left with the Mapsurvey wordmark and a short attributed quote, and five link columns titled "Product", "Mapsurvey for", "Use cases", "Resources" and "Company", followed by a bottom row with the language links, the AGPLv3 licence line and a copyright line naming the owner. This supersedes the footer requirement as modified by `dpga-readiness`: its legal links and owner line are kept, moved into the new layout. The footer SHALL keep a link to every internal marketing page it linked before this change, except `/pro/`, whose place is taken by `/pricing/` (change `pricing-page`).

#### Scenario: Columns and their links
- **WHEN** a page built on `base_landing.html` is rendered
- **THEN** the footer SHALL contain the five column titles in that order
- **AND** "Product" SHALL link to features, the demo survey section, `/pricing/`, `/services/` and "Request a demo" at `/demo/?src=footer`
- **AND** "Mapsurvey for" SHALL link to the five audience pages, "Use cases" to the four category pages, "Resources" to `/stories/`, the mapping-tools guide and the three alternative pages, and "Company" to the terms of use, the privacy & trust page, email, Telegram and GitHub

#### Scenario: Brand block with a quote
- **WHEN** the footer is rendered
- **THEN** the brand block SHALL show the wordmark and the Jane Jacobs quote with its attribution, translated on `/ru/`

#### Scenario: Nothing external or auth-related
- **WHEN** the footer is rendered
- **THEN** it SHALL NOT link to Discord or to any external booking page
- **AND** it SHALL NOT display any login or registration links

#### Scenario: Legal links and owner
- **WHEN** the footer is rendered
- **THEN** the "Company" column SHALL link "Terms of use" to `/terms/` and "Privacy & Trust" to `/trust/`
- **AND** the bottom row SHALL carry the AGPLv3 licence line and the copyright "© 2021–<current year> Artem Koniukhov"

#### Scenario: Readable on a phone
- **WHEN** the viewport is 360px wide
- **THEN** the footer columns SHALL wrap without horizontal scrolling
