## MODIFIED Requirements

### Requirement: Footer
The landing page SHALL display a footer with contact info, navigation links, a "Compare" column linking to the competitor comparisons hub, and copyright.

#### Scenario: Footer content
- **WHEN** the landing page is rendered
- **THEN** the footer SHALL display email and Telegram contact links, navigation links (Surveys, Stories), a "Compare" column with a link to `/alternatives/`, and a copyright line
- **AND** the footer SHALL NOT display any login or registration links

#### Scenario: Compare column present on all pages using base_landing.html
- **WHEN** any page extending `base_landing.html` is rendered (landing, trust, stories, comparison pages)
- **THEN** the footer SHALL contain a "Compare" column with at least one link to the `/alternatives/` hub
