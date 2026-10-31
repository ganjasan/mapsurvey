## Context

An `Invitation` (address, organisation, role, UUID token, 7-day life) is mailed as
`/invitations/<token>/accept/`. Today four places write the acceptance — `accept_invitation`
(signed-in visitor), `ActiveOrgMiddleware._process_pending_invitation` (token parked in the session
by the landing page, consumed on the first signed-in request), `signals.accept_invitations_for_email`
(address match, at confirmation; rule of change `login-grace-period`, #487) — and a fourth place,
`create_personal_org_on_registration`, decides where a new account lives without knowing about any
of them. The result is what #512 reproduced: the membership appears, the personal workspace appears
too, the active workspace is whichever was written last, the dashboard redirects to the start page
("How do you want to start?") because the active workspace has no surveys, and nothing says "you are
in". Owner decision 2026-10-31: an account registered through an invitation gets no personal
workspace.

## Goals / Non-Goals

**Goals**
- One module decides what a pending invitation is and performs the acceptance; every entry point
  calls it.
- A new account registered with an acceptable invitation lives in the inviting workspace only.
- After registration, sign-in or confirmation that accepted an invitation, the invitee sees the
  inviting workspace's dashboard with a "You've joined" banner, never the start page.
- An `editor` who sees none of the workspace's surveys reads why.
- The token survives a lost session (register / sign-in links carry it).

**Non-Goals**
- Accepting an address-matched invitation before the address is confirmed (#487 stays).
- Showing the workspace's surveys to an `editor` who is not a collaborator — roles are unchanged.
- Changing the invitation mail, the members page, or the `Invitation` model.
- A help-centre page about inviting colleagues (none exists; separate work).

## Decisions

### D1. `survey/invitations.py` is the one acceptance path
```
SESSION_TOKEN_KEY = 'pending_invitation_token'   # unchanged name: live sessions carry it
JOINED_KEY        = 'ms_joined_org_id'

acceptable(token) -> Invitation | None     # by token, select_related organisation, is_acceptable
remember(request, invitation)              # park the token in the session
pending(request) -> Invitation | None      # the parked token, validated; a dead token is dropped
accept(invitation, user, request=None) -> Membership
    # Membership.get_or_create(role=invitation.role); accepted_at=now;
    # with a request: session active_org_id = org, session JOINED_KEY = org, token forgotten
accept_pending(request, user) -> Organization | None    # pending() + accept(); None if nothing
join_by_address(user, request=None) -> list[Organization]
    # every acceptable invitation to user.email; replaces signals.accept_invitations_for_email,
    # uses Invitation.is_acceptable instead of its own 7-day arithmetic; with a request the LAST
    # joined workspace becomes active and JOINED
take_joined(request) -> int | None         # pop JOINED_KEY (the dashboard reads it once)
```
Callers: `accept_invitation` (signed-in branch → `accept`), `ActiveOrgMiddleware` (→
`accept_pending`), `create_personal_org_on_registration` (→ `accept_pending`, D2),
`accept_invitations_on_confirmation` (→ `join_by_address(user, request)`).
`Membership.get_or_create` keeps an existing member's higher role, as today.

*Why not keep the middleware as the acceptor for registration too?* It runs on the NEXT request,
after the personal workspace has already been created and made active. The decision "personal
workspace or not" has to be made where the account is created, synchronously, with the
invitation's acceptability checked at that moment — otherwise an invitation that expired between the
landing page and the submit would leave an account with no workspace at all.

### D2. No personal workspace for an invited registration
`create_personal_org_on_registration(sender, user, request)` first calls
`invitations.accept_pending(request, user)`; when that returns a workspace the receiver returns
without creating anything. Otherwise (no token, dead token) it creates the personal workspace
exactly as before. The address on the form need not equal the invited address: the token was mailed
to the invitee and is the credential, as it already is for `accept_invitation`.

An invited account therefore has one membership; "+ New workspace" (`org_create`) is how it gets
a personal one later. `ActiveOrgMiddleware`'s fallback (first membership by `joined_at`) and
`org_permission_required` work unchanged because the membership exists before the redirect.

### D3. The landing page carries the token into both doors
`org/invitation_landing.html`: *Create account* → `{% url 'django_registration_register' %}?invite=<token>`,
*Sign in to accept* → `{% url 'login' %}?next=/invitations/<token>/accept/`. The landing still
parks the token in the session (unchanged), so a visitor who ignores both links and registers from
the header later is still carried.

`AbuseProtectedRegistrationView`: on GET with `?invite=<token>` and `acceptable(token)`, `remember`
it and pass `invitation` to the template — the subtitle becomes "Create an account to join
<workspace>." and the email field is pre-filled with the invited address (editable). An
unacceptable `invite` is ignored (plain registration page; the landing already explained the
expiry). The parameter never reaches the honeypot, the rate limiter or the attribution capture.

Sign-in with `next` to the accept URL ends in `accept_invitation`'s signed-in branch → `accept` →
`redirect('editor')`; sign-in without `next` while the token is parked ends in the middleware →
`accept_pending`. Both are the same write.

### D4. Landing on the dashboard, once, with the banner
`editor` (`survey/views.py`) pops `invitations.take_joined(request)`; when it names the active
workspace, the view (a) does not redirect to the start page even if the workspace has no surveys
and (b) renders `joined_org` — a dismissible banner above the list: "You've joined <workspace>."
plus, for an `editor`, "Surveys you create here, and the ones a colleague adds you to, appear on
this page." The mark is consumed on that render, so a reload behaves as before (an owner/admin/
editor in a workspace with no surveys goes to the start page from the second visit on — the
47 %-of-registrations argument that put the redirect there is about a solo creator's empty
workspace and stays). `messages.success("You've joined …")` in the old acceptors goes; the banner
replaces it everywhere so the text exists once and is translated once.

### D5. The editor's empty state says what it means
When `org_role == 'editor'`, the workspace has canonical surveys and `survey_headers` is empty,
the two empty-state boxes (grid and list) read "No surveys of yours in <workspace> yet. Surveys you
create here, and the ones a colleague adds you to, appear on this page." instead of "No surveys
yet. Create your first one!". The default text (now `{% trans %}`) stays for every other case.
Context: `editor_sees_none` computed in the view from the unfiltered canonical count it already
runs for the start redirect.

### D6. Confirmation lands in the joined workspace
`accept_invitations_on_confirmation` → `invitations.join_by_address(user, request)`, which with a
request sets `active_org_id` and `JOINED_KEY`. `DirectActivationView.post` signs in BEFORE sending
`user_activated` (today the order is signal, then `auth_login`): `login()` flushes the session when
a different account was signed in, which would lose the two keys; signing in first and then sending
the signal keeps them in the surviving session. `_signed_in_redirect` splits into `_sign_in` (login,
or None on a banned/missing user) and the redirect, so the signal fires only on a real sign-in.

### D7. Events
`invitation_accepted` (server, `product_events`) with `organization_id`, `role`, `surface` ∈
`link | register | sign_in | confirm` — ids and names of surfaces only, never the address or the
token. Emitted from `accept` with the surface passed by the caller; `join_by_address` passes
`confirm`. This is the first measurement of how invitations convert; nothing else is changed in
analytics.

## Risks / Trade-offs

- **An invited account has no workspace of its own.** If the owner later removes them, the
  middleware's fallback finds no membership and the editor returns 403 — the same state a member
  removed from their only workspace is in today. Out of scope; noted for the members page.
- **Session-flush edge.** A browser signed in as account A opening B's invitation landing: the
  token is parked in A's session; A would accept B's invitation on their next request (unchanged
  behaviour — the token is the credential). The `?invite=` on the register link does not change
  this; the landing already shows who the invitation is for.
- **Order change in the activation view** (D6) moves `auth_login` before the signal. The receivers
  (`accept_invitations_on_confirmation`, `emit_activation_event`) read `user` and `request.session`
  only, so none depends on being anonymous; `test_sign_in_grace_period` keeps covering the
  activation flow.
- **Strings**: five new creator strings in eleven catalogs, appended by hand (PR #274 style) and
  compiled; `TranslationCatalogHygieneTest` enforces completeness.

## Migration Plan

No schema change. Deploy is one release; parked tokens in live sessions keep their key name and are
consumed by the new `accept_pending`. Rollback is a revert — a registration in between with an
invitation simply has no personal workspace, which is the intended state anyway.

## Open Questions

None. Owner decided 2026-10-31: no personal workspace for an invited registration.
