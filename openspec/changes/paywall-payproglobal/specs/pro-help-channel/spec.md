# pro-help-channel Specification

## Purpose
The Pro request form through which a Pro organisation asks for consulting, analysis or a report,
and how those requests reach the team and are recorded.

## ADDED Requirements

### Requirement: The form is a Pro feature; Free organisations see the offer
`/org/<slug>/help/` SHALL render the request form for members of organisations whose
entitlements include `pro_help`. For members of other organisations it SHALL render the service
description with an Upgrade link (owners) or a "ask your organisation owner" note (others), and
SHALL reject POSTs with HTTP 403.

#### Scenario: Pro member opens the page
- **WHEN** an editor of a Pro organisation opens `/org/<slug>/help/`
- **THEN** the request form is rendered

#### Scenario: Free owner opens the page
- **WHEN** the owner of a Free organisation opens the page
- **THEN** the service description and an "Upgrade to Pro" button are rendered and no form

#### Scenario: Free POST
- **WHEN** a member of a Free organisation POSTs to the page
- **THEN** the response is HTTP 403 and nothing is stored

### Requirement: A request records what is needed to act on it
The form SHALL collect `kind` (consulting / analysis / report / other), an optional survey of the
organisation, a message (required, max 5000 characters) and a preferred contact (email prefilled
from the user, editable), and SHALL store a `ProHelpRequest` with organisation, requesting user,
these fields and `created_at`.

#### Scenario: Valid submission
- **WHEN** a Pro member submits kind `report`, survey X and a message
- **THEN** a `ProHelpRequest` row exists with those values and the page confirms receipt

#### Scenario: Survey from another organisation
- **WHEN** the submitted survey id belongs to a different organisation
- **THEN** validation fails and nothing is stored

### Requirement: Requests reach the team and the requester is acknowledged
On submission the system SHALL send, outside the request cycle, one email to `CONTACT_EMAIL`
containing the organisation, requester, kind, survey, message and an admin link, and one
confirmation email to the preferred contact. A failed send SHALL be retried and SHALL not lose
the stored request.

#### Scenario: Mail sent
- **WHEN** a request is stored
- **THEN** a task is enqueued that sends the two emails

#### Scenario: Transport failure
- **WHEN** the mail backend raises
- **THEN** the task retries and the `ProHelpRequest` row remains

### Requirement: Requests are measured
Storing a request SHALL emit the PostHog event `pro_help_requested` with `org_id`, `kind` and
whether a survey was attached, keyed on the requester.

#### Scenario: Event emitted
- **WHEN** a request is stored
- **THEN** `pro_help_requested` is emitted once
