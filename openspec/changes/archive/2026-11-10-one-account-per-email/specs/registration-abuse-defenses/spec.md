## ADDED Requirements

### Requirement: One account per email address
The registration form SHALL refuse an email address that already belongs to any account, compared
case-insensitively and including banned accounts, with an error on the email field: "An account
with this email already exists." The page SHALL then offer a link to sign in and a link to reset
the password. A refused submission SHALL create no user, send no mail and count as a form-invalid
attempt for the rate limiter. The honeypot check SHALL still run before this validation.

#### Scenario: Address already registered
- **WHEN** the registration form is submitted with `Person@Example.org` and an account with
  `person@example.org` exists
- **THEN** the response is 200 with the email field error, links to `/accounts/login/` and the
  password reset page, and no new user exists

#### Scenario: Registration through an invitation with a registered address
- **WHEN** a visitor follows an acceptable invitation's *Create account* and submits an address
  that already has an account
- **THEN** no user is created, the invitation stays unaccepted and the page offers sign-in

#### Scenario: New address
- **WHEN** the form is submitted with an address no account holds
- **THEN** registration proceeds as before
