## ADDED Requirements

### Requirement: Open registration with email activation
The system SHALL allow new users to register via a form at `/accounts/register/`. Registration SHALL use `django-registration` activation backend with email verification. The registration link SHALL be visible on the login page.

#### Scenario: Successful registration
- **WHEN** a visitor submits the registration form with valid username, email, and password
- **THEN** a new inactive User is created
- **AND** an activation email is sent to the provided email address
- **AND** the user is redirected to the registration-complete page

#### Scenario: Account activation via email link
- **WHEN** a user clicks the activation link from the email within `ACCOUNT_ACTIVATION_DAYS`
- **THEN** the User account is activated
- **AND** the user is redirected to the activation-complete page

#### Scenario: Expired activation link
- **WHEN** a user clicks the activation link after `ACCOUNT_ACTIVATION_DAYS` have passed
- **THEN** the system SHALL display an activation-failed page

#### Scenario: Registration link visible on login page
- **WHEN** a visitor views the login page at `/accounts/login/`
- **THEN** the page SHALL display a "Register" link pointing to `/accounts/register/`

#### Scenario: Duplicate email rejected
- **WHEN** a visitor submits the registration form with an email already in use
- **THEN** the system SHALL display a validation error and NOT create a new user

#### Scenario: Duplicate username rejected
- **WHEN** a visitor submits the registration form with a username already in use
- **THEN** the system SHALL display a validation error and NOT create a new user

### Requirement: Personal organization created on registration
The system SHALL automatically create a personal organization when a new user account is activated. The user SHALL be assigned as the organization's owner.

#### Scenario: Personal org created on activation
- **WHEN** a user's account is activated
- **THEN** a new Organization is created with name "<username>'s workspace"
- **AND** a Membership is created with user=activated_user, organization=new_org, role="owner"
- **AND** the session's `active_org_id` is set to the new organization

#### Scenario: Personal org name collision
- **WHEN** a user activates and an organization with name "<username>'s workspace" already exists
- **THEN** the system SHALL append a numeric suffix to make the name unique (e.g., "<username>'s workspace 2")

### Requirement: Login redirects to editor
The system SHALL redirect authenticated users to `/editor/` after login. The login page SHALL be accessible at `/accounts/login/`.

#### Scenario: Successful login redirect
- **WHEN** a user logs in successfully without a `next` parameter
- **THEN** the user is redirected to `/editor/`

#### Scenario: Login with next parameter
- **WHEN** a user logs in with `?next=/editor/surveys/<uuid>/`
- **THEN** the user is redirected to the specified URL after login

### Requirement: Logout
The system SHALL provide a logout action accessible from the editor navigation. After logout, the user SHALL be redirected to the login page.

#### Scenario: Logout clears session
- **WHEN** an authenticated user clicks "Logout"
- **THEN** the session is cleared
- **AND** the user is redirected to the login page

### Requirement: Email backend configuration
The system SHALL support configurable email backends via environment variables for sending activation and invitation emails.

#### Scenario: Console backend in development
- **WHEN** `EMAIL_BACKEND` is set to `django.core.mail.backends.console.EmailBackend`
- **THEN** activation emails are printed to stdout instead of being sent

#### Scenario: SMTP backend in production
- **WHEN** `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` are configured
- **THEN** activation emails are sent via the configured SMTP server
