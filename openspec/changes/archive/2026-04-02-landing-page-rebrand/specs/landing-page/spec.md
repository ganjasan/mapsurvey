## MODIFIED Requirements

### Requirement: Public landing page at root URL
The system SHALL serve a public landing page at `/` for all visitors (anonymous and authenticated).

#### Scenario: Anonymous visitor sees landing page
- **WHEN** an unauthenticated user navigates to `/`
- **THEN** the system renders the landing page with hero, problem-solution, features, demo, comparison, use cases, tech stack, quick start, social proof, pricing, and footer sections

#### Scenario: Authenticated visitor sees landing page
- **WHEN** an authenticated user navigates to `/`
- **THEN** the system renders the same landing page with "Dashboard" and "Logout" links in the navbar

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
- **THEN** the HTML SHALL include a viewport meta tag, web fonts (loaded via font-display: swap with preload), and `landing.css`

#### Scenario: Existing pages unaffected
- **WHEN** user navigates to `/editor/`, `/surveys/`, or any non-landing page
- **THEN** those pages SHALL continue using `base.html` with Bootstrap 4

### Requirement: Hero section with open-source PPGIS positioning
The landing page SHALL display a hero section as the first visible content, positioned around the open-source participatory mapping platform value proposition.

#### Scenario: Hero content
- **WHEN** the landing page is rendered
- **THEN** the hero section SHALL display an H1 headline about open-source participatory mapping, a subheadline describing map-based surveys, a primary "Try Free" CTA button, a secondary "Self-Host" CTA button, and trust badges

#### Scenario: Hero primary CTA
- **WHEN** an unauthenticated visitor clicks "Try Free"
- **THEN** the system SHALL navigate to the registration page

#### Scenario: Hero secondary CTA
- **WHEN** a visitor clicks "Self-Host"
- **THEN** the system SHALL navigate to the GitHub repository URL

### Requirement: Page sections layout
The landing page SHALL be organized in full-width sections in the following order: hero, problem-solution, features, demo, comparison, use cases, tech-stack/quick-start, social proof, pricing, footer.

#### Scenario: Section ordering
- **WHEN** the landing page is rendered
- **THEN** sections SHALL appear in the order specified above

#### Scenario: Full-width layout
- **WHEN** the landing page is rendered
- **THEN** sections SHALL span the full viewport width without a Bootstrap `.container` wrapper

### Requirement: Landing page navbar
The landing page SHALL have its own navbar with product navigation and auth-aware actions.

#### Scenario: Navbar links for anonymous user
- **WHEN** an unauthenticated user views the landing page
- **THEN** the navbar SHALL display "Mapsurvey" brand, anchor links for Features, Demo, Pricing, a Docs link, a GitHub link, and a "Sign In" button

#### Scenario: Navbar links for authenticated user
- **WHEN** an authenticated user views the landing page
- **THEN** the navbar SHALL display "Mapsurvey" brand, anchor links for Features, Demo, Pricing, a Docs link, a GitHub link, username, "Dashboard" link, and "Logout" link

#### Scenario: Mobile hamburger menu
- **WHEN** the landing page is rendered on a viewport < 768px
- **THEN** the navbar SHALL collapse into a hamburger menu

### Requirement: Footer
The landing page SHALL display a footer with product navigation, documentation links, social links, language switcher, and license notice.

#### Scenario: Footer content
- **WHEN** the landing page is rendered
- **THEN** the footer SHALL display navigation links (Features, Demo, Docs, Pricing, GitHub), social links (GitHub, Mastodon, Twitter/X), a language switcher (EN/RU), and an open-source license notice

#### Scenario: Footer does not display contact section
- **WHEN** the landing page is rendered
- **THEN** the footer SHALL NOT display email or Telegram contact links as primary elements

## REMOVED Requirements

### Requirement: How it works section
**Reason**: Replaced by problem-solution, features, and demo sections that better communicate the open-source product positioning.
**Migration**: Content about survey workflow is now covered by the features section and interactive demo.

### Requirement: Contact section
**Reason**: The "Order a Survey" service model is replaced by self-serve sign-up and self-hosting. Contact is now limited to enterprise inquiries via the pricing section.
**Migration**: Enterprise contact prompt appears in the pricing section. General contact moved to footer or dedicated page.

### Requirement: Hero section with contact CTA
**Reason**: The "Order a Survey" CTA is replaced by dual CTAs: "Try Free" (sign-up) and "Self-Host" (GitHub).
**Migration**: Hero section is replaced by `landing-hero-v2` capability.
