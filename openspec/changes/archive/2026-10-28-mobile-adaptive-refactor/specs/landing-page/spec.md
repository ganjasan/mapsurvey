# landing-page (delta)

## ADDED Requirements

### Requirement: Content visible without JavaScript
All landing page sections SHALL be visible with JavaScript disabled or failed.
Scroll-reveal animation SHALL be applied as a progressive enhancement only, and SHALL be
skipped when the user agent reports `prefers-reduced-motion: reduce`.

#### Scenario: No-JS visitor sees full page
- **WHEN** the landing page is rendered without executing JavaScript
- **THEN** every content section below the hero is visible (no opacity-hidden sections)

#### Scenario: Reduced motion respected
- **WHEN** a visitor with `prefers-reduced-motion: reduce` scrolls the landing page
- **THEN** sections appear without reveal animation
