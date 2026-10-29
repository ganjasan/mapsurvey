# sign-in-grace-period Specification

## Purpose
A new account signs in at once and has 24 hours to confirm its email address. Past that, a
correct password is refused with the real reason and a fresh link, and the link is the way back
in. Nothing goes live from an unconfirmed address: publishing and workspace invitations wait for
it. Confirmation is recorded apart from `User.is_active`, which means only "not banned"
(change login-grace-period, #487).
## Requirements
### Requirement: Email confirmation is recorded apart from account activity
The system SHALL record whether an account's email address is confirmed in a dedicated record
(`EmailVerification`: the user, `verified_at`, `last_sent_at`), separate from `User.is_active`.
Registration SHALL create the account with `is_active=True` and an unconfirmed record.
`is_active=False` SHALL mean only that the account is barred (the phishing ban); it SHALL NOT be
used to mean "not yet confirmed". One module SHALL answer `is_verified(user)`,
`grace_deadline(user)` (= `date_joined` + `SIGN_IN_GRACE_HOURS`, default 24) and
`can_sign_in(user)` (`is_active` and (confirmed or now < deadline)); every other module SHALL ask
it rather than compute these itself. An account with no record SHALL be treated as confirmed
(accounts created by `createsuperuser`, the admin, fixtures).

#### Scenario: Registration creates an active, unconfirmed account
- **WHEN** a visitor completes registration
- **THEN** the account has `is_active=True` and an `EmailVerification` with `verified_at` empty

#### Scenario: A banned account cannot sign in whatever its confirmation
- **WHEN** an account with a confirmed address is banned (`is_active=False`)
- **THEN** `can_sign_in` is false

#### Scenario: Account without a record
- **WHEN** a superuser created with `createsuperuser` signs in
- **THEN** the account is treated as confirmed

### Requirement: Registration signs the creator in
On successful registration the system SHALL sign the new account in and redirect to the editor's
start page, and SHALL send the activation mail as before. The editor SHALL show an unconfirmed
creator a banner naming the address the mail went to, the time left in the grace period, and a
button that resends the mail (same limits as the resend form).

#### Scenario: Straight into the editor
- **WHEN** a visitor submits a valid registration
- **THEN** the response redirects to the editor start page with the session authenticated as the
  new account, and one activation mail is sent

#### Scenario: Banner on every editor page until confirmed
- **WHEN** an unconfirmed creator within the grace period opens any editor page
- **THEN** the page shows the confirm-your-email banner with the address and a resend button
- **AND** once the address is confirmed the banner no longer renders

### Requirement: Unconfirmed accounts sign in during the grace period
An account whose address is not confirmed SHALL be able to sign in with its password until
`grace_deadline`. After the deadline it SHALL NOT be able to sign in by password until the
address is confirmed; confirming through the activation link SHALL sign it in (no second grace
period).

#### Scenario: Sign-in one hour after registration
- **WHEN** an unconfirmed account signs in with the correct password 1 hour after registering
- **THEN** sign-in succeeds

#### Scenario: Sign-in 25 hours after registration
- **WHEN** an unconfirmed account signs in with the correct password 25 hours after registering
- **THEN** sign-in is refused and no session is created

#### Scenario: Confirmation after the deadline signs in
- **WHEN** the same account confirms through a valid activation link 30 hours after registering
- **THEN** the address is confirmed and the session is authenticated

### Requirement: After the grace period, sign-in names the reason and resends the link
The sign-in page SHALL, when the submitted password is correct for an account that is unconfirmed
past its deadline (and not banned), say that the address was not confirmed within 24 hours and
that a new activation link has been sent to the masked address (first character of the local
part, `•••`, `@`, the domain). The system SHALL send that link in the same request, subject to the
per-email resend limit; when the limit is reached it SHALL still show the message, worded as "we
have already sent a link", and send nothing. A wrong password, an unknown identifier and a banned
account SHALL get the generic failure message.

#### Scenario: Correct password past the deadline
- **WHEN** an unconfirmed account registered 2 days ago signs in with the correct password
- **THEN** the page shows the not-confirmed message with the masked address
- **AND** one activation mail with a fresh key is sent to the account's address

#### Scenario: Wrong password past the deadline stays generic
- **WHEN** the same account is submitted with a wrong password
- **THEN** the page shows the generic failure message and no mail is sent

#### Scenario: Repeated attempts do not flood the inbox
- **WHEN** the correct password is submitted five times within an hour past the deadline
- **THEN** the message shows each time, and no more mails are sent than the per-email resend limit
  allows

#### Scenario: Banned account
- **WHEN** a banned account signs in with its correct password
- **THEN** the page shows the generic failure message and no mail is sent

### Requirement: A grace-period session ends at the deadline
A session authenticated during the grace period SHALL end on its first request after
`grace_deadline` while the address is still unconfirmed: the user is signed out and an HTML
request is redirected to the sign-in page carrying the not-confirmed message (and the resend,
under the same rules as a password sign-in). Requests under the respondent prefixes (`/surveys/`,
`/r/`) SHALL NOT be affected.

#### Scenario: Editor tab left open overnight
- **WHEN** an unconfirmed creator signed in during the grace period loads an editor page 26 hours
  after registering
- **THEN** the session is ended and the response redirects to the sign-in page showing the
  not-confirmed message

#### Scenario: Confirmed in another tab
- **WHEN** the creator confirmed the address before the deadline
- **THEN** the session continues after the deadline

### Requirement: Publishing and inviting wait for a confirmed address
An unconfirmed account SHALL NOT publish a survey (the transition to `published` and publishing
unpublished changes), on any surface — the editor, the REST API, MCP — and SHALL NOT send a
workspace invitation. The refusal SHALL name the reason and offer the resend: the editor shows it
in place of the publish confirmation and of the invitation form's success; the REST API and MCP
answer `403` with error code `email_unconfirmed`. Every other editor action SHALL work during the
grace period.

#### Scenario: Publish from the editor
- **WHEN** an unconfirmed creator presses Publish on a draft survey
- **THEN** the survey stays a draft and the editor shows "Confirm your email to publish" with a
  resend button

#### Scenario: Publish through the API
- **WHEN** a token belonging to an unconfirmed account calls the publish endpoint
- **THEN** the response is `403` with code `email_unconfirmed` and the survey status is unchanged

#### Scenario: Invite a colleague
- **WHEN** an unconfirmed owner submits the workspace invitation form
- **THEN** no invitation is created, no mail is sent, and the page says the address must be
  confirmed first

#### Scenario: Building a survey works
- **WHEN** an unconfirmed creator creates a survey with the wizard, adds questions and opens the
  preview
- **THEN** every step succeeds

### Requirement: Anything matched by address alone waits for confirmation
Joining a workspace because an invitation was sent to the account's address SHALL happen when the
address is confirmed, not at registration: an account signs in before proving the mailbox, so
anyone could otherwise register with an invited address and walk into that workspace. An
invitation LINK (its token was mailed) SHALL keep working for a signed-in account. Product mail
sent to every creator (the newsletter) SHALL go only to confirmed addresses.

#### Scenario: Registering with an invited address
- **WHEN** someone registers with an address a workspace invited
- **THEN** the account is not a member of that workspace until the address is confirmed, and is
  a member right after confirming

#### Scenario: Newsletter recipients
- **WHEN** a newsletter campaign lists its recipients
- **THEN** an account with an unconfirmed address is not among them

### Requirement: Existing accounts are migrated by one rule
A data migration SHALL create an `EmailVerification` for every existing account: accounts with
`is_active=True` are confirmed (`verified_at` = `last_login`, else `date_joined`); accounts with
`is_active=False` and no `last_login` (registered, never activated) become `is_active=True`,
unconfirmed, their grace period long over; accounts with `is_active=False` and a `last_login`
(banned) keep `is_active=False` and are recorded as confirmed.

#### Scenario: Never-activated account after the migration
- **WHEN** an account that registered in September and never activated signs in with its correct
  password after the migration
- **THEN** it gets the not-confirmed message and a new activation mail

#### Scenario: Banned account after the migration
- **WHEN** an account banned by `confirm_phishing` signs in after the migration
- **THEN** it gets the generic failure message and no mail

