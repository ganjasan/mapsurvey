## ADDED Requirements

### Requirement: Validation errors and help text are visually distinct on auth pages

Auth pages SHALL present validation errors so that they are distinguishable from body copy at a
glance, not by colour alone. An error SHALL carry a visual surface of its own — a background or
border marking its extent — and an adjacent non-colour indicator, so that it does not read as
ordinary text within a multi-field form.

#### Scenario: Registration validation error is distinguishable from body copy

- **WHEN** a registration submission is rejected because the password fails a validator
- **THEN** the rendered error SHALL carry a background or border distinguishing it from surrounding text
- **AND** the error SHALL carry a non-colour indicator, so it is not conveyed by colour alone

#### Scenario: Non-field errors are shown

- **WHEN** a registration submission fails with an error not attached to any single field
- **THEN** the rendered page SHALL display that error above the form

### Requirement: Help text states constraints a user can violate

Help text on registration fields SHALL describe the constraints a submission can realistically fail —
minimum length and permitted characters — and SHALL NOT lead with maximum-length ceilings that no
human input approaches. Django's stock username help text ("Required. 150 characters or fewer. Letters,
digits and @/./+/-/_ only.") SHALL be replaced.

#### Scenario: Username help text does not advertise the 150-character ceiling

- **WHEN** the registration page renders the username field
- **THEN** the help text SHALL state the permitted characters and any minimum length
- **AND** the help text SHALL NOT state "150 characters or fewer"

### Requirement: Password guidance distinguishes enforced rules from advice

The registration page SHALL present password rules as a checklist that updates as the user types, and
SHALL distinguish rules the server enforces from advice it does not. Enforced rules SHALL be derived
from the configured `AUTH_PASSWORD_VALIDATORS`. Advisory rules SHALL NOT be rendered as errors, since
a password violating one is still accepted.

Password composition beyond a minimum length SHALL NOT block registration. The system SHALL warn about
commonly used passwords, passwords reusing the account's own email or username, and all-numeric
passwords, and SHALL accept them when submitted.

The checklist SHALL NOT block submission; server-side validation remains the sole authority. Where a
rule cannot be evaluated exactly in the browser, the checklist MAY report it as satisfied when it is
not, but SHALL NOT report it as violated when the server would accept — including for advisory rules,
which the server always accepts.

#### Scenario: A common password is accepted

- **WHEN** registration is submitted with a widely-known common password meeting the minimum length
- **THEN** the account SHALL be created

#### Scenario: A password resembling the email is accepted

- **WHEN** registration is submitted with a password closely resembling the submitted email address
- **THEN** the account SHALL be created

#### Scenario: A password below the minimum length is rejected

- **WHEN** registration is submitted with a password shorter than the configured minimum
- **THEN** the form SHALL be re-rendered with an error and no account SHALL be created

#### Scenario: Advisory rules are marked as advice

- **WHEN** the registration page renders a rule the server does not enforce
- **THEN** that rule SHALL be marked so it is presented as advice rather than as an error

#### Scenario: Checklist updates while typing

- **WHEN** a user types a password shorter than the configured minimum
- **THEN** the minimum-length rule SHALL be shown as unsatisfied
- **AND** typing further characters until the minimum is met SHALL show it as satisfied without a page reload

#### Scenario: Checklist does not block submission

- **WHEN** a user submits the registration form while one or more checklist rules show as unsatisfied
- **THEN** the submission SHALL be sent to the server
- **AND** the server's validation result SHALL determine the outcome

#### Scenario: Page remains usable without JavaScript

- **WHEN** the registration page is rendered with JavaScript disabled
- **THEN** the rules SHALL still be listed
- **AND** the form SHALL still submit and validate server-side

#### Scenario: Checklist stays in sync with enforced validators

- **WHEN** `AUTH_PASSWORD_VALIDATORS` contains a validator not represented in the rendered checklist
- **THEN** the test suite SHALL fail

### Requirement: Failed sign-in preserves the entered username

The sign-in form SHALL re-render with the submitted username after a failed attempt and SHALL clear the
password field. The failure message SHALL NOT reveal whether an account exists for the submitted
identifier, and SHALL be accompanied by a link to resend the activation email, since an unactivated
account is a common cause that the generic message cannot name.

#### Scenario: Username survives a wrong password

- **WHEN** a user submits the sign-in form with a correct username and an incorrect password
- **THEN** the re-rendered page SHALL contain the submitted username as the value of the username field
- **AND** the password field SHALL be empty

#### Scenario: Failure message does not enumerate accounts

- **WHEN** the sign-in form is submitted with an identifier that has no account, and separately with an existing identifier and a wrong password
- **THEN** both responses SHALL present the same failure message

### Requirement: Rate-limited registration returns a rendered page

When registration is refused by the rate limit, the response SHALL be an HTML page in the site layout
that states that too many attempts were made, indicates when the user may retry, and links to sign-in
and password reset. The response SHALL keep HTTP status 429 and the `Retry-After` header. The page
SHALL NOT disclose which limit was reached, the configured thresholds, or the number of attempts
remaining.

#### Scenario: Rate-limited response is a rendered page

- **WHEN** a registration POST is refused by the rate limit
- **THEN** the response SHALL have status 429 and a `Retry-After` header
- **AND** the response `Content-Type` SHALL be HTML
- **AND** the body SHALL contain a link to the sign-in page and a link to password reset

#### Scenario: Thresholds are not disclosed

- **WHEN** the rate-limit page is rendered
- **THEN** the body SHALL NOT contain the configured limit values
