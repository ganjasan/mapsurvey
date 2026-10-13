## ADDED Requirements

### Requirement: Child-abuse reports are always escalated

A report with reason `child_abuse` SHALL produce an owner notice whose subject starts with `[URGENT]`. When such a report arrives for a survey that already has an open (`pending` or `reported`) review whose `note` does not start with `child_abuse:`, the system SHALL set the review note's reason prefix to `child_abuse` (preserving the earlier text after it), increment `report_count`, and send exactly one urgent notice even though a notice was sent before. Further `child_abuse` reports on a review already marked `child_abuse` SHALL only increment `report_count`.

#### Scenario: First report is child abuse

- **WHEN** a visitor submits a `child_abuse` report for a survey with no open review
- **THEN** one notice SHALL be sent whose subject starts with `[URGENT]`

#### Scenario: Child-abuse report on a survey already reported for scam

- **WHEN** a survey has a `reported` review with note starting `scam:` and a visitor submits a `child_abuse` report
- **THEN** the review note SHALL start with `child_abuse:`
- **AND** `report_count` SHALL increase by one
- **AND** exactly one additional notice SHALL be sent, with subject starting `[URGENT]`

#### Scenario: Repeated child-abuse reports do not repeat the mail

- **WHEN** a review note already starts with `child_abuse:` and another `child_abuse` report arrives
- **THEN** `report_count` SHALL increase by one
- **AND** no additional notice SHALL be sent

## MODIFIED Requirements

### Requirement: Reporting a survey opens a review without holding it

`/surveys/<uuid>/report/` SHALL render a form with a reason, one of `phishing`, `scam`, `illegal`, `child_abuse`, `harassment`, `personal_data`, `other` in that order, each with a translatable label, and an optional message of at most 500 characters. A valid POST SHALL create a `ContentReview` with `source='report'` and `status='reported'` for the canonical survey (or increment `report_count` on an existing open review for that survey), write an `AbuseEvent` with `defense='content_screen'` and `detail` starting with `report survey=<id>`, and send the owner notice. A report SHALL NOT change what respondents see. The endpoint SHALL be limited to 3 POSTs per client IP per hour, failing open if the cache is unreachable, and SHALL respond with a neutral thank-you page in every accepted case.

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

#### Scenario: All seven reasons are offered

- **WHEN** a visitor opens the report page of a published survey
- **THEN** the form SHALL offer exactly the reasons `phishing`, `scam`, `illegal`, `child_abuse`, `harassment`, `personal_data`, `other` in that order
