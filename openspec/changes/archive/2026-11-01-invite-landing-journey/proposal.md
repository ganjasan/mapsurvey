## Why

A person invited into a workspace expects the invitation link to put them in that workspace.
Today a NEW account almost never gets there (#512, reproduced 2026-10-31 with the test client on
`master`): the link path creates the membership but lands on an empty "My Surveys" with an
unrequested personal workspace beside it; registering directly, or on another device, lands in the
personal workspace and on the start page "How do you want to start?"; and confirming the address
afterwards creates the membership silently while the active workspace stays personal, so the
invitee is offered "create a new survey" instead of the team they were asked to join. Invitations
are how a workspace grows past one person, and each one that dead-ends costs a seat that was
already won.

## What Changes

- **One acceptance path.** `survey/invitations.py` is the one module that reads a pending
  invitation (session, `?invite=<token>`), accepts it (membership, `accepted_at`, active workspace,
  the "just joined" mark) and that every entry point calls — the accept view, the sign-in and
  registration follow-ups, the email confirmation. No second copy of the membership write.
- **No personal workspace for an invited registration.** When the registration carries an
  acceptable invitation, the account is created INSIDE the inviting workspace and no "<name>'s
  workspace" is made; the invitee creates one only when they want one. A registration whose
  invitation has meanwhile expired or been used gets the personal workspace as before, so nobody
  ends up without a workspace.
- **The landing carries the token forward.** The invitation page's *Create account* link is
  `/accounts/register/?invite=<token>` (the form pre-fills the invited address) and *Sign in* is
  `/accounts/login/?next=/invitations/<token>/accept/`, so the token survives a lost session and the
  link can be re-opened in another browser.
- **Landing in the workspace.** After registration, sign-in or email confirmation that accepted an
  invitation, the active workspace is the inviting one and the response goes to ITS dashboard,
  which shows a "You've joined <workspace>" banner. The dashboard's redirect to the start page is
  skipped on that first view, and an `editor` who sees none of the workspace's surveys reads what
  that means instead of a bare "No surveys yet. Create your first one!".
- **Confirmation lands there too.** `accept_invitations_for_email` (the confirmation-time join,
  rule of #487 unchanged) now also switches the active workspace and marks the join, so the
  confirmation's redirect reaches the team's dashboard with the banner.

## Capabilities

### New Capabilities
- `workspace-invitation-journey`: the invitation link for signed-out visitors (landing page, token
  carried into registration and sign-in), the one acceptance path, where an invitee lands after
  registration / sign-in / confirmation, the joined banner and the editor's empty state.

### Modified Capabilities
- `registration-abuse-defenses`: "Existing registration flow remains intact" — the personal
  organisation is created unless the registration carries an acceptable invitation.
- `sign-in-grace-period`: "Anything matched by address alone waits for confirmation" — confirming
  an address that was invited also switches the active workspace to the one joined and lands the
  confirmation redirect on its dashboard.

## Impact

- Code: `survey/org_views.py::accept_invitation`, `survey/middleware.py::ActiveOrgMiddleware`,
  `survey/signals.py` (`create_personal_org_on_registration`, `accept_invitations_for_email`),
  `survey/views.py` (`AbuseProtectedRegistrationView`, `DirectActivationView._signed_in_redirect`,
  `editor`), new `survey/invitations.py`, templates `org/invitation_landing.html`,
  `django_registration/registration_form.html`, `editor.html`.
- Tests: new `survey/tests/test_workspace_invitation_journey.py` (the three journeys end to end);
  `test_org_access_control.py` invitation tests follow the single acceptance path; the
  registration-abuse "personal organisation" scenario is unchanged for a registration without an
  invitation.
- Creator strings: the landing page, the banner and the empty state are new creator-facing text
  and go into all offered catalogs.
- No data migration; `Invitation`, `Membership`, `Organization` unchanged.
