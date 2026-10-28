## ADDED Requirements

### Requirement: Configurable site-verification meta tag
The system SHALL render `<meta name="google-site-verification">` with the configured token on all
pages when `GOOGLE_SITE_VERIFICATION` is set, and SHALL render nothing when it is empty.

#### Scenario: Tag rendered when configured
- **WHEN** `GOOGLE_SITE_VERIFICATION` is set and a page is rendered
- **THEN** the head contains the meta tag with that token

#### Scenario: No tag by default
- **WHEN** the setting is empty
- **THEN** no google-site-verification meta tag is emitted
