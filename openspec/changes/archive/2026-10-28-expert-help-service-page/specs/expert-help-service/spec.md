## ADDED Requirements

### Requirement: Public expert-help service page

The system SHALL serve a public page at `/services/` that describes optional paid
help with survey design and getting responses. The page SHALL render for
anonymous visitors, extend the landing layout, state clearly that the platform
itself stays free and open source, present the help as two tiers (launch help and
a done-with-you engagement), and provide a call-to-action that opens an email to
`konuchovartem@mapsurvey.org` to request a call. The path SHALL be allowed in
`robots.txt`.

#### Scenario: Anonymous visitor loads the services page

- **WHEN** an unauthenticated visitor requests `/services/`
- **THEN** the response is HTTP 200 and includes the service headline, the "still
  free / open source" reassurance, both help tiers, and the mailto call-to-action.

#### Scenario: Page is crawlable

- **WHEN** a crawler fetches `/robots.txt`
- **THEN** `/services/` is present as an `Allow` entry.
