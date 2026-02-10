## ADDED Requirements

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
The landing page SHALL display a hero section as the first visible content, with the primary call-to-action being to contact us about ordering a survey.

#### Scenario: Hero content
- **WHEN** the landing page is rendered
- **THEN** the hero section SHALL display a headline, a short value-proposition description targeting architecture and urban planning professionals, and a primary CTA button "Order a Survey"

#### Scenario: Hero primary CTA
- **WHEN** a visitor clicks the "Order a Survey" button in the hero
- **THEN** the page SHALL scroll to the contact section

#### Scenario: Hero secondary CTA
- **WHEN** the landing page is rendered
- **THEN** the hero SHALL include a secondary "Browse Surveys" button that scrolls to the survey cards section

### Requirement: How it works section
The landing page SHALL display a "How it works" section explaining the service flow in 3 steps.

#### Scenario: Steps content
- **WHEN** the landing page is rendered
- **THEN** the how-it-works section SHALL display three steps: (1) describe your task, (2) we create a geo-survey, (3) you get data and maps

### Requirement: Contact section
The landing page SHALL display a contact section with email and Telegram links for ordering surveys.

#### Scenario: Contact channels
- **WHEN** the landing page is rendered
- **THEN** the contact section SHALL display an email link (mailto:) and a Telegram link (t.me/)

#### Scenario: Contact settings from configuration
- **WHEN** the landing page is rendered
- **THEN** the contact email and Telegram handle SHALL be read from Django settings (`CONTACT_EMAIL`, `CONTACT_TELEGRAM`)

### Requirement: Page sections layout
The landing page SHALL be organized in full-width sections in the following order: hero, how-it-works, survey cards, stories, contact, footer.

#### Scenario: Section ordering
- **WHEN** the landing page is rendered
- **THEN** sections SHALL appear in order: hero, how-it-works, surveys, stories, contact, footer

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
The landing page SHALL display a footer with contact info, navigation links, and copyright.

#### Scenario: Footer content
- **WHEN** the landing page is rendered
- **THEN** the footer SHALL display email and Telegram contact links, navigation links (Surveys, Stories), and a copyright line
- **AND** the footer SHALL NOT display any login or registration links
