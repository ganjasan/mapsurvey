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
The landing page SHALL display a hero section as the first visible content with exactly two buttons: a primary one to start on your own and a secondary one to book a call with us. The demo survey, when configured, SHALL be offered as a text link under the buttons, not as a third button. The hero SHALL NOT make hosting or compliance claims.

#### Scenario: Hero buttons for an anonymous visitor
- **WHEN** an unauthenticated visitor views the landing page and `BOOK_A_CALL_URL` is set
- **THEN** the hero SHALL show a primary "Create your Mapsurvey" button linking to registration
- **AND** a secondary "Book a 30-min call" button linking to `BOOK_A_CALL_URL` in a new tab

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
The landing page SHALL display a footer with contact info, navigation links, and copyright.

#### Scenario: Footer content
- **WHEN** a page built on `base_landing.html` is rendered and `BOOK_A_CALL_URL` is set
- **THEN** the footer "Connect" column SHALL offer a "Book a call" link to `BOOK_A_CALL_URL`, alongside email, Telegram and GitHub
- **AND** the footer SHALL NOT link to Discord
- **AND** the footer SHALL NOT display any login or registration links

### Requirement: How to start section
The landing page SHALL display a "How to start" section that offers two paths side by side: building the survey yourself for free, and building it with us under a fixed quote. Each path SHALL carry exactly one button.

#### Scenario: Two paths
- **WHEN** the landing page is rendered
- **THEN** the "How to start" section SHALL show a "Build it yourself" card with three steps and a "Create your Mapsurvey" button (or "Go to Dashboard" for a signed-in user)
- **AND** a "Build it with us" card with three steps, a "Book a 30-min call" button linking to `BOOK_A_CALL_URL`, and a text link to `/services/`

#### Scenario: Booking not configured
- **WHEN** `BOOK_A_CALL_URL` is empty
- **THEN** the "Build it with us" card SHALL still render, and its button SHALL link to `/services/` instead

#### Scenario: Stacked on a phone
- **WHEN** the viewport is narrower than 760px
- **THEN** the two cards SHALL stack vertically with the "Build it yourself" card first

### Requirement: Book-a-call target from configuration
Every "Book a call" control on the public marketing pages SHALL take its URL from the `BOOK_A_CALL_URL` setting (environment variable, default the Mapsurvey Cal.com booking page), exposed to templates by the `contact` context processor. Discord SHALL NOT be offered on any public page.

#### Scenario: Services page call buttons
- **WHEN** `/services/` is rendered and `BOOK_A_CALL_URL` is set
- **THEN** both "Book a short call" buttons SHALL link to `BOOK_A_CALL_URL`
- **AND** when `BOOK_A_CALL_URL` is empty they SHALL fall back to a `mailto:` link to `CONTACT_EMAIL`

#### Scenario: Educators page
- **WHEN** `/for-educators/` is rendered and `BOOK_A_CALL_URL` is set
- **THEN** its hero SHALL offer "Book a call" instead of a Discord link

#### Scenario: Click is measured
- **WHEN** a visitor clicks any Book-a-call control and PostHog is loaded
- **THEN** a `book_call_clicked` event SHALL be captured with the surface it was clicked on and no other visitor data

