# account-logout Specification

## Purpose
How a signed-in creator signs out: a POST with the CSRF token from every Logout control, never a GET link (Django 5 answers GET on the logout URL with 405).
## Requirements
### Requirement: Signing out is a POST
Every Logout control a signed-in creator sees SHALL submit a POST with the CSRF token to the
`logout` URL. No page SHALL render a link that sends GET to the logout URL. A POST to the logout
URL SHALL end the session and redirect to `LOGOUT_REDIRECT_URL`; a GET SHALL not sign anyone out.

#### Scenario: Logout from the editor signs the creator out
- **WHEN** a signed-in creator submits the Logout form
- **THEN** the response redirects to `/`
- **AND** the next request to the editor is treated as anonymous

#### Scenario: Pages render a POST logout form
- **WHEN** a signed-in creator opens the dashboard, a survey editor page or a landing page
- **THEN** the page contains a `<form method="post">` whose action is the logout URL and which carries a CSRF token
- **AND** the page contains no `<a>` whose `href` is the logout URL

#### Scenario: GET does not sign out
- **WHEN** a signed-in creator requests the logout URL with GET
- **THEN** the session stays signed in

