## ADDED Requirements

### Requirement: Respondent pages carry a safety notice and a report link

Every respondent-facing survey page (section pages and the thanks page) SHALL render a footer line stating that passwords and card numbers must never be entered in a Mapsurvey survey, followed by a "Report this survey" link to `/surveys/<uuid>/report/`. The notice SHALL be translatable and SHALL NOT be removable by the creator.

#### Scenario: Notice is present on a section page

- **WHEN** a respondent opens any section of a published survey
- **THEN** the page SHALL contain the safety notice and a link to the report page for that survey

#### Scenario: Notice is present on the thanks page

- **WHEN** a respondent reaches the thanks page
- **THEN** the page SHALL contain the safety notice and the report link

### Requirement: Reporting a survey opens a review without holding it

`/surveys/<uuid>/report/` SHALL render a form with a reason (`phishing`, `scam`, `other`) and an optional message of at most 500 characters. A valid POST SHALL create a `ContentReview` with `source='report'` and `status='reported'` for the canonical survey (or increment `report_count` on an existing open review for that survey), write an `AbuseEvent` with `defense='content_screen'` and `detail` starting with `report survey=<id>`, and send the owner notice. A report SHALL NOT change what respondents see. The endpoint SHALL be limited to 3 POSTs per client IP per hour, failing open if the cache is unreachable, and SHALL respond with a neutral thank-you page in every accepted case.

#### Scenario: First report creates a reported review and mails the owner

- **WHEN** a visitor submits a report with reason `phishing` for a survey with no open review
- **THEN** a `ContentReview` with `source='report'`, `status='reported'` and `report_count=1` SHALL exist for the canonical survey
- **AND** one owner notice SHALL be sent
- **AND** the survey SHALL still serve to respondents

#### Scenario: Repeated reports do not repeat the mail

- **WHEN** a second report arrives for a survey that already has a `pending` or `reported` review
- **THEN** that review's `report_count` SHALL increase by one
- **AND** no additional email SHALL be sent

#### Scenario: Rate limit

- **WHEN** a client IP submits a fourth report within an hour
- **THEN** the response SHALL be HTTP 429
- **AND** no review row SHALL be created or updated

#### Scenario: Reports on unknown or draft surveys reveal nothing

- **WHEN** the report URL names a UUID that does not exist or belongs to a draft
- **THEN** the response SHALL be 404, identical to the survey entry page's response
