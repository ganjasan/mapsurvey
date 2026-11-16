## MODIFIED Requirements

### Requirement: Public results page existence and addressing
The system SHALL serve a report at `/r/<slug>/` where `slug` is unique and independent of any survey
slug. A report is an object of a workspace and MAY have a home survey; it is not bound 1:1 to a
`SurveyHeader`. The page SHALL be reachable only when it is published.

#### Scenario: Published page is reachable
- **WHEN** an anonymous visitor opens `/r/<slug>/` for a published results page
- **THEN** the system returns 200 and renders the page

#### Scenario: Unpublished page is not reachable
- **WHEN** an anonymous visitor opens `/r/<slug>/` for a results page that is not published
- **THEN** the system returns 404

#### Scenario: Unknown slug
- **WHEN** an anonymous visitor opens `/r/<slug>/` for a slug that does not exist
- **THEN** the system returns 404

#### Scenario: Slug is independent of survey slug
- **WHEN** a creator sets the results-page slug to a value different from the survey slug
- **THEN** the page is served at `/r/<that-slug>/` and the survey's own public URL is unaffected
