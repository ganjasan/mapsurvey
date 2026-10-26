# Landing Page Specification

## Purpose
The public marketing page at the root URL — its own base template, section layout, hero and contact CTAs, navbar and footer — kept separate from the authenticated editor chrome.
## Requirements
### Requirement: Public landing page at root URL
The system SHALL serve a public landing page at `/` for all visitors (anonymous and authenticated).

#### Scenario: Anonymous visitor sees landing page
- **WHEN** an unauthenticated user navigates to `/`
- **THEN** the system renders the landing page with hero, how-it-works, survey cards, stories, and contact section

#### Scenario: Authenticated visitor sees landing page
- **WHEN** an authenticated user navigates to `/`
- **THEN** the system renders the same landing page with "Editor" and "Logout" links in the navbar

#### Scenario: No redirect to login
- **WHEN** an unauthenticated user navigates to `/`
- **THEN** the system SHALL NOT redirect to `/accounts/login/`

### Requirement: Separate base template
The landing page SHALL use `base_landing.html` as its base template, independent from the existing `base.html`.

#### Scenario: Landing page does not load Bootstrap
- **WHEN** the landing page is rendered
- **THEN** the HTML SHALL NOT include Bootstrap CSS or JS from CDN

#### Scenario: Landing page loads custom assets
- **WHEN** the landing page is rendered
- **THEN** the HTML SHALL include a viewport meta tag, Google Fonts, and `landing.css`

#### Scenario: Existing pages unaffected
- **WHEN** user navigates to `/editor/`, `/surveys/`, or any non-landing page
- **THEN** those pages SHALL continue using `base.html` with Bootstrap 4

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

### Requirement: Page sections layout
The landing page SHALL be organized in full-width sections in the following order: hero, product showcase, use cases, demo, capabilities, how to start, footer.

#### Scenario: Section ordering
- **WHEN** the landing page is rendered
- **THEN** sections SHALL appear in order: hero, showcase, use cases, demo, capabilities, how to start, footer
- **AND** there SHALL be no separate mid-page or final call-to-action section besides "How to start"

#### Scenario: Full-width layout
- **WHEN** the landing page is rendered
- **THEN** sections SHALL span the full viewport width without a Bootstrap `.container` wrapper

### Requirement: Landing page navbar
The landing page SHALL have its own navbar with the Mapsurvey brand, navigation links, and auth-aware actions.

#### Scenario: Navbar links for anonymous user
- **WHEN** an unauthenticated user views the landing page
- **THEN** the navbar SHALL display "Mapsurvey" brand, "Surveys" anchor link, "Stories" anchor link, and "Contact" anchor link
- **AND** the navbar SHALL NOT display any login, register, or sign-up links

#### Scenario: Navbar links for authenticated user
- **WHEN** an authenticated user views the landing page
- **THEN** the navbar SHALL display "Mapsurvey" brand, "Surveys" anchor link, "Stories" anchor link, "Contact" anchor link, username, "Editor" link, and "Logout" link

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

### Requirement: How to start section
The landing page SHALL display a "How to start" section that offers two paths side by side: building the survey yourself for free, and building it with us under a fixed quote. Each path SHALL carry exactly one button.

#### Scenario: Two paths
- **WHEN** the landing page is rendered
- **THEN** the "How to start" section SHALL show a "Build it yourself" card with three steps and a "Get Mapsurvey free" button (or "Go to Dashboard" for a signed-in user)
- **AND** a "Build it with us" card with three steps, a "Request a demo" button linking to `/demo/?src=how_to_start`, and a text link to `/services/`

#### Scenario: Stacked on a phone
- **WHEN** the viewport is narrower than 760px
- **THEN** the two cards SHALL stack vertically with the "Build it yourself" card first

### Requirement: Product showcase and capabilities
The landing page SHALL show the product in four steps — build, collect, analyze, share — each with a screenshot of the demo survey that opens full size, followed by a capabilities grid of six cards.

#### Scenario: Four showcase steps
- **WHEN** the landing page is rendered
- **THEN** the showcase SHALL contain four rows labelled BUILD, COLLECT, ANALYZE and SHARE, each with an inline screenshot and a full-size screenshot for the lightbox

#### Scenario: Six capability cards
- **WHEN** the landing page is rendered
- **THEN** the capabilities section SHALL contain six cards: Questions made for maps, Your data on the map, A map people build together, Built to be answered, Clean and analyse, Export and publish

#### Scenario: Claims match the product
- **WHEN** the showcase or capability copy names a count, a format or a feature
- **THEN** it SHALL be one the product has at the time of release (no "13 question types", no export formats the dialog does not offer)

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

