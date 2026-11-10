## ADDED Requirements

### Requirement: A used invitation link leads its member back into the workspace
An invitation link whose invitation is already accepted SHALL NOT offer account creation. A
signed-in visitor who is a member of the inviting workspace SHALL have that workspace made active
and SHALL be redirected to the dashboard, with no error message and no "joined" mark. A signed-in
visitor who is not a member SHALL be redirected to the dashboard with the message that the
invitation has already been used. A signed-out visitor SHALL see a page that says they have
already joined the workspace (by name), whose primary action is *Sign in* with `next` set to the
same accept URL, with a *Forgot password?* link and no link to registration. Nothing SHALL be
written to the invitation on any of these paths.

#### Scenario: Member opens the old link while signed in
- **WHEN** a signed-in member of workspace W, whose active workspace is another one, opens the
  link of an accepted invitation into W
- **THEN** the response redirects to `/editor/`, W is the active workspace, no "already used"
  message is queued and the session carries no joined mark

#### Scenario: Non-member opens a used link while signed in
- **WHEN** a signed-in user who is not a member of W opens the link of an accepted invitation into W
- **THEN** the response redirects to `/editor/` with the message "This invitation has already been
  used." and the active workspace is unchanged

#### Scenario: Signed-out visitor opens a used link
- **WHEN** a signed-out visitor opens the link of an accepted invitation into W
- **THEN** the page names W, links *Sign in* to `/accounts/login/?next=/invitations/<token>/accept/`
  and to the password reset page, and contains no link to `/accounts/register/`

#### Scenario: Sign in through the used link
- **WHEN** that visitor signs in as a member of W through the page's *Sign in*
- **THEN** they land on `/editor/` with W active
