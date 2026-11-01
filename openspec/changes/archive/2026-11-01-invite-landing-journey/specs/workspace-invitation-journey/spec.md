## ADDED Requirements

### Requirement: One acceptance path for workspace invitations
The system SHALL accept a workspace invitation in exactly one module (`survey/invitations.py`):
accepting SHALL create the membership with the invitation's role (an existing membership keeps its
role), record `accepted_at`, and — when a request is at hand — make the inviting workspace the
active one and mark the session as having just joined it. The signed-in accept view, the
session-parked token consumed on the next signed-in request, the registration that carries an
invitation and the confirmation-time address match SHALL all call this path; no other code SHALL
write an invitation's acceptance. An invitation SHALL be acceptable while it is unaccepted and no
older than seven days (`Invitation.is_acceptable`); the address match SHALL use the same rule.

#### Scenario: Signed-in visitor opens the link
- **WHEN** a signed-in user opens `/invitations/<token>/accept/` for an acceptable invitation
- **THEN** they are a member of the workspace with the invitation's role, the invitation is
  accepted, the workspace is active and the response redirects to the dashboard

#### Scenario: Parked token on the first signed-in request
- **WHEN** a signed-out visitor opened the link, then signs in without following the landing's
  links, and makes any request
- **THEN** the invitation is accepted on that request, the workspace is active and the token is
  no longer in the session

#### Scenario: Dead token is dropped
- **WHEN** a parked token names an invitation that is used, expired or deleted
- **THEN** nothing is written, the token is removed from the session and the request proceeds

### Requirement: The landing page carries the token into registration and sign-in
For a signed-out visitor the invitation landing page SHALL link *Create account* to the
registration page with `?invite=<token>` and *Sign in to accept* to the sign-in page with `next`
set to the accept URL, besides parking the token in the session. The registration page opened with
an acceptable `invite` SHALL park that token, pre-fill the email field with the invited address
(editable) and say which workspace the account will join; an unacceptable `invite` SHALL be ignored
and the page SHALL render as plain registration. The parameter SHALL NOT take part in the honeypot,
rate-limit or attribution logic.

#### Scenario: Landing links
- **WHEN** a signed-out visitor opens an acceptable invitation link
- **THEN** the page names the inviter, the workspace and the role, and its two actions are
  `/accounts/register/?invite=<token>` and `/accounts/login/?next=/invitations/<token>/accept/`

#### Scenario: Registration page from the landing
- **WHEN** the registration page is opened with the invitation's `invite` parameter in a fresh
  browser session
- **THEN** the email field holds the invited address, the page says the account will join the
  workspace, and the token is parked in that session

#### Scenario: Expired invite parameter
- **WHEN** the registration page is opened with `invite` naming an expired invitation
- **THEN** the page is the plain registration page and nothing is parked

### Requirement: A registration that carries an invitation joins the workspace and creates no personal workspace
The system SHALL accept a parked, acceptable invitation as the account is created and SHALL NOT
create a personal workspace ("<name>'s workspace") for that registration; the account's only
membership is the inviting workspace, and the registration's redirect lands on that workspace's
dashboard. When no acceptable invitation is
parked (none, used, expired), registration SHALL create the personal workspace as before. The
address typed on the form need not equal the invited address: the token is the credential.

#### Scenario: Register through the link
- **WHEN** a signed-out visitor opens an acceptable invitation link, follows *Create account* and
  registers
- **THEN** the account is a member of the inviting workspace with the invited role, no
  organisation named after the account exists, the inviting workspace is active and `/editor/`
  renders its dashboard

#### Scenario: Invitation died between landing and submit
- **WHEN** the parked invitation is accepted by someone else or expires before the form is
  submitted
- **THEN** registration creates the personal workspace and the account is not a member of the
  inviting workspace

#### Scenario: Different address on the form
- **WHEN** the invited address is `a@example.org` and the form is submitted with `b@example.org`
- **THEN** the account still joins the workspace through the token and no personal workspace is
  created

### Requirement: The invitee lands on the workspace dashboard with a joined banner
On the first dashboard request after an acceptance that marked the session, `/editor/` SHALL render
the active workspace's dashboard — not redirect to the start page, whatever the workspace's survey
count — with a dismissible banner "You've joined <workspace>." and, for the `editor` role, the
sentence that surveys they create there and surveys a colleague adds them to appear on this page
(left out when the editor's empty state below already says it).
The mark SHALL be consumed by that render: a later `/editor/` request follows the ordinary rule
(start page when the workspace has no surveys and the role may create). The old flash message
"You've joined …" SHALL not be shown anywhere.

#### Scenario: Banner once
- **WHEN** an invitee's first `/editor/` request follows an acceptance into a workspace with no
  surveys
- **THEN** the response is the dashboard (200) with the banner naming the workspace, and the next
  `/editor/` request redirects to the start page

#### Scenario: Banner names the active workspace only
- **WHEN** the session carries the joined mark but the active workspace is another one
- **THEN** no banner renders and the mark is cleared

#### Scenario: Confirmation lands there
- **WHEN** an account registered without a token with an invited address confirms its email
- **THEN** the activation's redirect reaches the inviting workspace's dashboard with the banner,
  and the personal workspace remains a second membership

### Requirement: An editor who sees none of the surveys reads why
Both empty states of the dashboard (cards and list) SHALL read "No surveys of yours in <workspace>
yet. Surveys you create here, and the ones a colleague adds you to, appear on this page." when the
active workspace has canonical surveys, the viewer's role is `editor` and the list is empty. The
default empty state ("No surveys yet. Create your first one!") SHALL remain for every other case
and SHALL be translatable.

#### Scenario: Editor in a populated workspace
- **WHEN** an `editor` with no own or collaborated survey opens the dashboard of a workspace that
  has surveys
- **THEN** the page shows the editor's empty state naming the workspace

#### Scenario: Owner of an empty workspace
- **WHEN** an owner opens `/editor/?dashboard=1` on a workspace with no surveys
- **THEN** the page shows the default empty state

### Requirement: Acceptance is measured
Every acceptance SHALL emit the server event `invitation_accepted` with the organisation id, the
role and `surface` ∈ `link | register | sign_in | confirm` — never the address or the token.

#### Scenario: Registration surface
- **WHEN** an invitation is accepted as part of a registration
- **THEN** one `invitation_accepted` event with `surface=register` is emitted
