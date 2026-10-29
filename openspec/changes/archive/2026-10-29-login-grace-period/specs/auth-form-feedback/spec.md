## MODIFIED Requirements

### Requirement: Failed sign-in preserves the entered username

The sign-in form SHALL re-render with the submitted username after a failed attempt and SHALL clear the
password field. The failure message SHALL NOT reveal whether an account exists for the submitted
identifier. The one exception is a correct password for an account whose address is unconfirmed past
the sign-in grace period: the visitor has proven they hold the account, so the page SHALL name the real
reason (see `sign-in-grace-period`). The generic message SHALL no longer carry the resend-activation hint,
because the case it guessed at now has its own message.

#### Scenario: Username survives a wrong password

- **WHEN** a user submits the sign-in form with a correct username and an incorrect password
- **THEN** the re-rendered page SHALL contain the submitted username as the value of the username field
- **AND** the password field SHALL be empty

#### Scenario: Failure message does not enumerate accounts

- **WHEN** the sign-in form is submitted with an identifier that has no account, and separately with an existing identifier and a wrong password
- **THEN** both responses SHALL present the same failure message

#### Scenario: Correct password on an unconfirmed account past the grace period

- **WHEN** the sign-in form is submitted with the correct password of an account unconfirmed for more than 24 hours
- **THEN** the page SHALL show the not-confirmed message with the masked address instead of the generic one
- **AND** the username field SHALL keep the submitted value
