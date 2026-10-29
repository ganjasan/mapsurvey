# account-activation Specification

## Purpose
TBD - created by archiving change activation-funnel-autologin. Update Purpose after archive.
## Requirements
### Requirement: Auto-login after successful activation
The system SHALL, upon successful confirmation via the confirmation form's POST with a valid activation key for an unconfirmed account, mark the address confirmed, log the user in and redirect them to the editor dashboard (`LOGIN_REDIRECT_URL`) without requiring credential entry. This applies inside and after the sign-in grace period alike.

#### Scenario: Confirmed activation signs in
- **WHEN** an anonymous user submits the confirmation form with a valid, unexpired activation key for an unconfirmed account
- **THEN** the address is confirmed, the user's session is authenticated as that account, and the response redirects to `/editor/`

#### Scenario: Confirmation while already signed in during the grace period
- **WHEN** an unconfirmed creator who is signed in submits the confirmation form for their own account
- **THEN** the address is confirmed, the session continues, and the response redirects to `/editor/`

#### Scenario: Login records last_login
- **WHEN** a user is auto-logged-in through activation
- **THEN** `last_login` is set on the account, as with any interactive login

#### Scenario: Banned account is not signed in
- **WHEN** the confirmation form is submitted for an account with `is_active=False`
- **THEN** no session is created and the failure page is shown

### Requirement: Already-active account with a valid key is not an error
The system SHALL treat an activation request (GET or POST) whose key is valid but whose address is already confirmed as a benign repeat and SHALL route the user onward rather than showing a failure page. It SHALL NOT sign the user in on such a repeat — the key must not function as a reusable login credential.

#### Scenario: Second visit to an already-consumed link
- **WHEN** an activation URL with a valid key is opened for an account whose address is already confirmed
- **THEN** the user is redirected to the login page (or `/editor/` when their session is already authenticated), and no failure page is shown

#### Scenario: Replayed confirmation does not sign in
- **WHEN** the confirmation form is submitted for an account whose address is already confirmed
- **THEN** no session is created and the user is redirected to the login page

### Requirement: Activation key validity window
The activation key SHALL remain valid for 7 days by default, configurable via the `ACCOUNT_ACTIVATION_DAYS` environment variable. Every page and mail that states the link's validity SHALL take it from that setting, and pages shown after registration or a resend SHALL also state the 24-hour sign-in grace period separately, never as the link's validity.

#### Scenario: Click within the window
- **WHEN** a user opens their activation link 6 days after registration
- **THEN** confirmation succeeds

#### Scenario: Click after the window
- **WHEN** a user opens their activation link more than 7 days after registration
- **THEN** confirmation fails and the failure page offers the resend-activation flow

#### Scenario: Texts follow the setting
- **WHEN** `ACCOUNT_ACTIVATION_DAYS` is 3
- **THEN** the activation mail and the resend confirmation page say the link is valid for 3 days, and no page says the link expires in 24 hours

### Requirement: Resend activation email
The system SHALL provide an unauthenticated form at a dedicated URL where a user can enter an email address and request a fresh activation email. For an email that matches an unconfirmed, non-banned account, the system SHALL send a new activation email using the standard activation template with a freshly signed key. The same send SHALL back the editor banner's resend button and the automatic resend on a refused sign-in, under one per-email limit.

#### Scenario: Expired-key holder requests a new link
- **WHEN** a user whose activation key expired submits the resend form with their registered email
- **THEN** a new activation email is sent, and the new link confirms the address within the validity window

#### Scenario: Failure page links to resend
- **WHEN** activation fails for any reason (expired, invalid, or missing key)
- **THEN** the failure page contains a link to the resend-activation form and does not suggest re-registering

### Requirement: Resend flow does not leak account existence
The resend endpoint SHALL respond identically — redirect to a neutral "check your inbox" page — whether the submitted email matches an unconfirmed account, a confirmed account, a banned account, or no account at all. Email SHALL be sent only in the unconfirmed, non-banned case.

#### Scenario: Unknown email
- **WHEN** the resend form is submitted with an email that matches no account
- **THEN** the response is the same neutral confirmation, and no email is sent

#### Scenario: Already-confirmed account
- **WHEN** the resend form is submitted with the email of an account whose address is confirmed
- **THEN** the response is the same neutral confirmation, and no activation email is sent

#### Scenario: Banned account
- **WHEN** the resend form is submitted with the email of a banned account
- **THEN** the response is the same neutral confirmation, and no activation email is sent

### Requirement: Resend flow is abuse-hardened
The resend endpoint SHALL be protected by the same defense layers as registration: a hidden honeypot field that silently fake-succeeds when filled, and rate limits per client IP and per target email (settings-configurable, defaulting to 3/hour per IP and 3/day per email). Rate limiting SHALL fail open when the cache backend is unreachable. Over-limit attempts SHALL be recorded in the abuse audit log.

#### Scenario: Honeypot filled
- **WHEN** the resend form is submitted with the honeypot field non-empty
- **THEN** the response is the neutral confirmation and no email is sent

#### Scenario: Per-IP rate limit exceeded
- **WHEN** a client IP exceeds the per-IP resend limit within the window
- **THEN** subsequent submissions from that IP receive the neutral confirmation without sending email, and an abuse event is recorded

#### Scenario: Cache backend down
- **WHEN** the rate-limit cache backend is unreachable
- **THEN** the resend request is processed as if under the limit (fail-open)

### Requirement: Activation requires explicit confirmation
Opening the activation URL with GET SHALL NOT change account state. A valid, unexpired key for an unconfirmed account SHALL render a confirmation page containing a single-button form; confirmation SHALL occur only on the form's POST submission. This keeps mail-security link scanners (which follow links but do not submit forms) from consuming the confirmation.

#### Scenario: Scanner pre-fetch does not confirm
- **WHEN** a mail scanner issues GET (or HEAD) requests against a valid activation URL for an unconfirmed account
- **THEN** the address remains unconfirmed and no session is created

#### Scenario: Human confirms
- **WHEN** a user opens the activation URL (GET) and submits the confirmation form (POST)
- **THEN** the address is confirmed

#### Scenario: Expired key skips the confirmation page
- **WHEN** the activation URL is opened with an expired or tampered key
- **THEN** the failure page (with the resend link) renders directly, with no confirmation button

