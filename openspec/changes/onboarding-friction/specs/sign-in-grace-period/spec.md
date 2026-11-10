## MODIFIED Requirements

### Requirement: Registration signs the creator in
On successful registration the system SHALL sign the new account in and redirect to the editor's
start page, and SHALL send the activation mail as before. The editor SHALL NOT show an
unconfirmed creator a standing confirm-your-email banner: the request to confirm is made where the
confirmation is required — the "Confirm your email to publish" dialog a refused publish opens,
naming the address the mail went to, with a button that resends the mail (same limits as the
resend form) — and by the sign-in form once the grace period has ended.

#### Scenario: Straight into the editor
- **WHEN** a visitor submits a valid registration
- **THEN** the response redirects to the editor start page with the session authenticated as the
  new account, and one activation mail is sent

#### Scenario: No banner while building
- **WHEN** an unconfirmed creator within the grace period opens the dashboard or any editor page
- **THEN** the page shows no confirm-your-email banner and no grace-period countdown

#### Scenario: The publish dialog asks for the confirmation
- **WHEN** an unconfirmed creator within the grace period opens a survey in the editor
- **THEN** the page carries the "Confirm your email to publish" dialog with the address and a resend button, opened only when a publish is refused
