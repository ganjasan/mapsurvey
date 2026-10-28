# account-activation Specification (delta)

## ADDED Requirements

### Requirement: Activation requires explicit confirmation
Opening the activation URL with GET SHALL NOT change account state. A valid, unexpired key for an inactive account SHALL render a confirmation page containing a single-button form; activation SHALL occur only on the form's POST submission. This keeps mail-security link scanners (which follow links but do not submit forms) from consuming the activation.

#### Scenario: Scanner pre-fetch does not activate
- **WHEN** a mail scanner issues GET (or HEAD) requests against a valid activation URL for an inactive account
- **THEN** the account remains inactive and no session is created

#### Scenario: Human confirms and is activated
- **WHEN** a user opens the activation URL (GET) and submits the confirmation form (POST)
- **THEN** the account becomes active

#### Scenario: Expired key skips the confirmation page
- **WHEN** the activation URL is opened with an expired or tampered key
- **THEN** the failure page (with the resend link) renders directly, with no confirmation button

## MODIFIED Requirements

### Requirement: Auto-login after successful activation
The system SHALL, upon successful account activation via the confirmation form's POST with a valid activation key, log the activated user in and redirect them to the editor dashboard (`LOGIN_REDIRECT_URL`) without requiring credential entry.

#### Scenario: Confirmed activation signs in
- **WHEN** an anonymous user submits the confirmation form with a valid, unexpired activation key for an inactive account
- **THEN** the account becomes active, the user's session is authenticated as that account, and the response redirects to `/editor/`

#### Scenario: Login records last_login
- **WHEN** a user is auto-logged-in through activation
- **THEN** `last_login` is set on the account, as with any interactive login

### Requirement: Already-active account with a valid key is not an error
The system SHALL treat an activation request (GET or POST) whose key is valid but whose account is already active as a benign repeat and SHALL route the user onward rather than showing a failure page. It SHALL NOT sign the user in on such a repeat — the key must not function as a reusable login credential.

#### Scenario: Second visit to an already-consumed link
- **WHEN** an activation URL with a valid key is opened for an account that is already active
- **THEN** the user is redirected to the login page (or `/editor/` when their session is already authenticated), and no failure page is shown

#### Scenario: Replayed confirmation does not sign in
- **WHEN** the confirmation form is submitted for an account that is already active
- **THEN** no session is created and the user is redirected to the login page
