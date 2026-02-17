## MODIFIED Requirements

### Requirement: Public landing page at root URL
The system SHALL serve a public landing page at `/` for all visitors (anonymous and authenticated). The survey cards section SHALL exclude surveys with `status=draft`.

#### Scenario: Anonymous visitor sees landing page
- **WHEN** an unauthenticated user navigates to `/`
- **THEN** the system renders the landing page with hero, how-it-works, survey cards, stories, and contact section

#### Scenario: Authenticated visitor sees landing page
- **WHEN** an authenticated user navigates to `/`
- **THEN** the system renders the same landing page with "Editor" and "Logout" links in the navbar

#### Scenario: No redirect to login
- **WHEN** an unauthenticated user navigates to `/`
- **THEN** the system SHALL NOT redirect to `/accounts/login/`

#### Scenario: Draft surveys excluded from landing page
- **WHEN** the landing page is rendered and some surveys have `status=draft`
- **THEN** the survey cards section SHALL NOT include surveys with `status=draft`

#### Scenario: Closed surveys shown with indicator
- **WHEN** the landing page is rendered and a survey has `status=closed` and `visibility=public`
- **THEN** the survey card SHALL appear on the landing page (existing `visibility` filter still applies)
