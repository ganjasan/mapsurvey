## Context

`accept_invitation` (`survey/org_views.py`) treats an accepted invitation as an error for everyone:
a signed-in user gets a flash "already been used" and the dashboard of whatever workspace is active;
a signed-out visitor gets `invitation_landing.html` in its error state, whose links are *Sign In* and
*Create Account* (plain `/accounts/register/`, no token). `RegistrationAbuseForm` extends
django-registration's `RegistrationForm`, which checks username uniqueness only.

The invitation email is the link people keep; months later it is the bookmark they use to reach
the workspace.

## Goals / Non-Goals

**Goals:** an accepted invitation link returns its member to the workspace; nobody can create a
second account on an address that has one.

**Non-Goals:** merging or cleaning up the 38 existing duplicates; changing `find_user`; expired or
unknown invitations (unchanged); email changes (there is no form that edits an account's email).

## Decisions

1. **Member check, not "who accepted".** `Invitation` does not record which account accepted it.
   The signed-in branch asks `Membership.objects.filter(user=request.user,
   organization=invitation.organization).exists()`: a member is switched to that workspace
   (`session['active_org_id']`) and redirected to `/editor/` with no message and no "joined" banner,
   because nothing was joined. A non-member keeps today's flash and redirect.
2. **Signed-out used state is its own landing variant** (`used=True`), not the generic error:
   heading "You've already joined <workspace>", one primary *Sign in* button with
   `?next=<accept URL>` (sign-in → the accept view → member branch → the workspace) and
   *Forgot password?*. No *Create Account*. Naming the workspace is no new disclosure: the token
   holder saw it on the open invitation.
3. **Uniqueness lives in the form** (`RegistrationAbuseForm.clean_email`, `email__iexact`, any
   account including banned ones), so the honeypot-before-validation order and the invalid-attempt
   counter are untouched. The template cannot put links into an escaped error string, so the form
   sets `email_taken = True` and the template renders the two links under the field.
   Alternative considered: a silent success that mails the existing address. Rejected: registration
   signs the new account in at once (grace period), so a fake success is detectable anyway, and the
   person in the replay needed the answer on the page.
4. **No database constraint.** 38 duplicates exist; a unique index would need the merge first.

## Risks / Trade-offs

- [Account enumeration by email through the registration form] → bounded by the existing per-IP
  registration limits (invalid attempts have their own counter); usernames were already enumerable.
- [Duplicates already on file stay broken for email sign-in] → out of scope, listed in #639.
