## ADDED Requirements

### Requirement: Public Pro early-access page

The system SHALL serve a public page at `/pro/` that asks visitors which paid
capabilities would matter on a real project. The page SHALL render for anonymous
visitors, extend the landing layout, and SHALL NOT state any price, plan cost or
billing period. The page SHALL state that capabilities available on the free plan
remain free. The page SHALL link to `/services/` for visitors who need help
before the capabilities exist.

#### Scenario: Anonymous visitor loads the page

- **WHEN** an unauthenticated visitor requests `/pro/`
- **THEN** the response is HTTP 200 and includes the segment question, every
  capability group, the free-text question, the budget-shape question, the
  free-stays-free statement, and a link to `/services/`

#### Scenario: The page carries no pricing

- **WHEN** `/pro/` is rendered
- **THEN** the response body contains no currency amount and no billing-period
  wording such as "per month", "per year" or "per project" offered as a price

#### Scenario: Signed-in creator sees their email pre-filled

- **WHEN** an authenticated user requests `/pro/`
- **THEN** the email field is pre-filled with their account email

### Requirement: Capability options are defined once

The system SHALL define the capability options, their groups, and their stable
machine keys in a single Python constant that drives the rendered template, form
validation, and the stored value. A submitted key that is not in the constant
SHALL be rejected rather than stored or silently dropped.

#### Scenario: Every rendered checkbox is a known key

- **WHEN** `/pro/` is rendered
- **THEN** every capability checkbox in the response has a `value` present in the
  capability constant

#### Scenario: An unknown capability key is rejected

- **WHEN** a POST to `/pro/` includes a capability key absent from the constant
- **THEN** the submission is rejected with a validation error and no
  `ProInterest` row is created

### Requirement: Submissions are persisted

The system SHALL persist a submission as a `ProInterest` record holding the
segment, the selected capability keys, the free-text answer, the budget shape,
the email, the optional organisation, the submission timestamp, and the
submitting user when authenticated. A submission SHALL be accepted when the
visitor selects no capabilities, because an empty selection is a meaningful
answer.

#### Scenario: Valid submission is stored

- **WHEN** a visitor submits `/pro/` with an email, consent, and two capabilities
  selected
- **THEN** a `ProInterest` row is created holding both capability keys and the
  visitor is shown a confirmation

#### Scenario: Submission with nothing selected is stored

- **WHEN** a visitor submits `/pro/` with an email and consent but no capability
  selected
- **THEN** a `ProInterest` row is created with an empty capability list

#### Scenario: Authenticated submission is attributed

- **WHEN** an authenticated user submits `/pro/`
- **THEN** the stored row references their user account

### Requirement: Consent is required before storing personal data

The system SHALL require an explicit, non-prefilled consent checkbox and SHALL
link the privacy policy on the page. A submission without consent SHALL be
rejected and SHALL NOT be stored.

#### Scenario: Consent checkbox is not pre-ticked

- **WHEN** `/pro/` is rendered
- **THEN** the consent checkbox is present and unchecked, and a privacy policy
  link is present

#### Scenario: Submission without consent is rejected

- **WHEN** a visitor submits `/pro/` with a valid email but without consent
- **THEN** the response redisplays the form with an error and no `ProInterest`
  row is created

### Requirement: Submissions emit a product-analytics event

The system SHALL emit a single PostHog `pro_interest_submitted` event per stored
submission, carrying the segment, the selected capability keys and the budget
shape. The system SHALL resolve a distinct id for every submission, including an
anonymous one with no PostHog cookie and no session key, so that no stored answer
goes uncounted. The system SHALL NOT record the submission through `SurveyEvent`,
which measures customers' respondents. A failure to emit the event SHALL NOT
prevent the submission from being stored.

#### Scenario: Event accompanies a stored submission

- **WHEN** a submission is stored
- **THEN** one `pro_interest_submitted` event is emitted with the segment,
  capability keys and budget shape

#### Scenario: An anonymous visitor with no cookie is still counted

- **WHEN** an anonymous visitor with no PostHog cookie and no established
  session submits the form
- **THEN** the event is still emitted, under a distinct id derived from the
  stored row

#### Scenario: Analytics failure does not lose the answer

- **WHEN** emitting the event raises
- **THEN** the `ProInterest` row is still stored and the visitor still sees the
  confirmation

#### Scenario: No respondent-analytics record is written

- **WHEN** a submission is stored
- **THEN** no `SurveyEvent` row is created

### Requirement: Both marketing offers are reachable and crawlable

The system SHALL link `/pro/` and `/services/` from the landing navigation and
the landing footer, SHALL list both in `sitemap.xml`, and SHALL allow `/pro/` in
`robots.txt`.

#### Scenario: Navigation and footer expose both pages

- **WHEN** a landing page is rendered
- **THEN** the navigation and the footer each contain a link to `/pro/` and a
  link to `/services/`

#### Scenario: Both pages are crawlable

- **WHEN** a crawler fetches `/robots.txt` and `/sitemap.xml`
- **THEN** `/pro/` is present as an `Allow` entry, and both `/pro/` and
  `/services/` appear in the sitemap
