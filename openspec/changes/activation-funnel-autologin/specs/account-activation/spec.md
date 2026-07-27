# account-activation Specification (delta)

## ADDED Requirements

### Requirement: Auto-login after successful activation
The system SHALL, upon successful account activation via a valid activation key, log the activated user in and redirect them to the editor dashboard (`LOGIN_REDIRECT_URL`) without requiring credential entry.

#### Scenario: Valid key activates and signs in
- **WHEN** an anonymous user opens the activation URL with a valid, unexpired activation key for an inactive account
- **THEN** the account becomes active, the user's session is authenticated as that account, and the response redirects to `/editor/`

#### Scenario: Login records last_login
- **WHEN** a user is auto-logged-in through activation
- **THEN** `last_login` is set on the account, as with any interactive login

### Requirement: Already-active account with a valid key is not an error
The system SHALL treat an activation request whose key is valid but whose account is already active as a benign repeat (e.g. a mail scanner pre-fetched the link before the user clicked it) and SHALL route the user onward rather than showing a failure page.

#### Scenario: Second click on an already-consumed link
- **WHEN** an activation URL with a valid key is opened for an account that is already active
- **THEN** the user is redirected to the login page (or `/editor/` when their session is already authenticated), and no failure page is shown

### Requirement: Activation key validity window
The activation key SHALL remain valid for 7 days by default, configurable via the `ACCOUNT_ACTIVATION_DAYS` environment variable.

#### Scenario: Click within the window
- **WHEN** a user opens their activation link 6 days after registration
- **THEN** activation succeeds

#### Scenario: Click after the window
- **WHEN** a user opens their activation link more than 7 days after registration
- **THEN** activation fails and the failure page offers the resend-activation flow

### Requirement: Resend activation email
The system SHALL provide an unauthenticated form at a dedicated URL where a user can enter an email address and request a fresh activation email. For an email that matches a not-yet-activated account, the system SHALL send a new activation email using the standard activation template with a freshly signed key.

#### Scenario: Expired-key holder requests a new link
- **WHEN** a user whose activation key expired submits the resend form with their registered email
- **THEN** a new activation email is sent, and the new link activates the account within the validity window

#### Scenario: Failure page links to resend
- **WHEN** activation fails for any reason (expired, invalid, or missing key)
- **THEN** the failure page contains a link to the resend-activation form and does not suggest re-registering

### Requirement: Resend flow does not leak account existence
The resend endpoint SHALL respond identically — redirect to a neutral "check your inbox" page — whether the submitted email matches an inactive account, an active account, or no account at all. Email SHALL be sent only in the inactive-account case.

#### Scenario: Unknown email
- **WHEN** the resend form is submitted with an email that matches no account
- **THEN** the response is the same neutral confirmation, and no email is sent

#### Scenario: Already-active account
- **WHEN** the resend form is submitted with the email of an already-active account
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
