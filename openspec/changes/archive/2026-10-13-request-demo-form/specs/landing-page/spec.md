## MODIFIED Requirements

### Requirement: Hero section with contact CTA
The landing page SHALL display a hero section as the first visible content with exactly two buttons: a primary one to start on your own and a secondary one to request a demo. The demo survey, when configured, SHALL be offered as a text link under the buttons, not as a third button. The hero SHALL NOT make hosting or compliance claims.

#### Scenario: Hero buttons for an anonymous visitor
- **WHEN** an unauthenticated visitor views the landing page
- **THEN** the hero SHALL show a primary "Get Mapsurvey free" button linking to registration
- **AND** a secondary "Request a demo" button linking to `/demo/?src=hero` in the same tab

#### Scenario: Hero for a signed-in user
- **WHEN** an authenticated user views the landing page
- **THEN** the primary hero button SHALL be "Go to Dashboard" linking to the editor

#### Scenario: Demo survey as a text link
- **WHEN** `DEMO_SURVEY_URL` is set
- **THEN** the hero SHALL show a text link to the demo survey beneath the buttons

#### Scenario: No unbacked claims in the hero
- **WHEN** the landing page is rendered
- **THEN** the hero badges SHALL NOT include "GDPR-Friendly" or any claim about where data is hosted

### Requirement: Footer
Every page built on `base_landing.html` SHALL display a light footer laid out after Notion's: a brand block on the left with the Mapsurvey wordmark and a short attributed quote, and five link columns titled "Product", "Mapsurvey for", "Use cases", "Resources" and "Company", followed by a bottom row with the language links, the AGPLv3 licence line and a copyright line naming the owner. This supersedes the footer requirement as modified by `dpga-readiness`: its legal links and owner line are kept, moved into the new layout. The footer SHALL keep a link to every internal marketing page it linked before this change.

#### Scenario: Columns and their links
- **WHEN** a page built on `base_landing.html` is rendered
- **THEN** the footer SHALL contain the five column titles in that order
- **AND** "Product" SHALL link to features, the demo survey section, `/pro/`, `/services/` and "Request a demo" at `/demo/?src=footer`
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

### Requirement: How to start section
The landing page SHALL display a "How to start" section that offers two paths side by side: building the survey yourself for free, and building it with us under a fixed quote. Each path SHALL carry exactly one button.

#### Scenario: Two paths
- **WHEN** the landing page is rendered
- **THEN** the "How to start" section SHALL show a "Build it yourself" card with three steps and a "Get Mapsurvey free" button (or "Go to Dashboard" for a signed-in user)
- **AND** a "Build it with us" card with three steps, a "Request a demo" button linking to `/demo/?src=how_to_start`, and a text link to `/services/`

#### Scenario: Stacked on a phone
- **WHEN** the viewport is narrower than 760px
- **THEN** the two cards SHALL stack vertically with the "Build it yourself" card first

## ADDED Requirements

### Requirement: Demo request reachable from every marketing surface
Every control on the public marketing pages that invites the visitor to talk to us SHALL link to `/demo/` with a `src` parameter naming the surface. No public page SHALL link to an external booking calendar or to Discord.

#### Scenario: Services page buttons
- **WHEN** `/services/` is rendered
- **THEN** both call-to-action buttons SHALL read "Request a demo" and link to `/demo/?src=services`

#### Scenario: Educators page
- **WHEN** `/for-educators/` is rendered
- **THEN** its hero SHALL offer a secondary "Request a demo" button linking to `/demo/?src=educators`

#### Scenario: No booking calendar anywhere
- **WHEN** `/`, `/ru/`, `/services/`, `/for-educators/` and `/pro/` are rendered
- **THEN** none of them SHALL contain a link to `cal.com` and no `book_call_clicked` listener

## REMOVED Requirements

### Requirement: Book-a-call target from configuration
**Reason**: The external booking page converted 3 clicks and 0 bookings in 60 days; every surface now leads to the on-site demo request (`demo-request` capability).
**Migration**: The `BOOK_A_CALL_URL` setting, context-processor key, template branches, the `book_call_clicked` listener and their tests are deleted. The Render env var can be removed at leisure; it is ignored.
