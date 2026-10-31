## MODIFIED Requirements

### Requirement: Existing registration flow remains intact for legitimate users

A legitimate registration SHALL require the `accept_terms` confirmation (see "Age and terms confirmation on sign-up"); apart from that the change SHALL NOT alter the post-registration behavior for legitimate users. The existing `user_registered` signal handler SHALL still create a personal `Organization` and `Membership` — unless the registration carries an acceptable workspace invitation, in which case it accepts that invitation and creates no personal organisation (see `workspace-invitation-journey`) — and the activation email SHALL still be sent in a background thread.

#### Scenario: Legitimate registration still creates personal organization

- **WHEN** a registration with empty honeypot and below rate limits is submitted with valid form data and `accept_terms` checked, and no invitation is parked in the session
- **THEN** a `User` SHALL be created with `is_active=True` and an unconfirmed `EmailVerification` (see `sign-in-grace-period`)
- **AND** an `Organization` SHALL be created via the existing `user_registered` signal
- **AND** a `Membership` SHALL link the user to the organization with role `owner`
- **AND** the activation email SHALL be sent in a background thread
- **AND** the session SHALL be signed in as the new user and the response SHALL redirect to `LOGIN_REDIRECT_URL`

#### Scenario: Registration through an invitation creates no personal organization

- **WHEN** the same registration is submitted while an acceptable invitation is parked in the session
- **THEN** the `User` is created and signed in as above, is a member of the inviting organisation with the invited role, and no organisation named after the account exists
