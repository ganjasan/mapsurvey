## Why

A member invited into a colleague's workspace accepted the invitation, came back two months later
through the same email with their session expired, and was shown "This invitation has already been
used." next to *Create Account* (PostHog replay 2026-11-09, issue #639). Registration does not check
the address, so they made a second account with the same email and landed in an empty personal
workspace. They looked for the colleague's workspace in the switcher twice and left. From then on,
signing in with that email opens the new, empty account: `find_user` matches the username first, and
the new username is the address. Production holds 38 addresses with more than one account.

## What Changes

- An already-accepted invitation link is a way back into the workspace, not a dead end:
  - a signed-in member of the inviting workspace is switched to it and sent to the dashboard;
  - a signed-out visitor sees "You've already joined <workspace>" with *Sign in* (back through the
    same link, so the switch happens after sign-in) and *Forgot password?*, and no *Create Account*.
- Registration refuses an email address that already belongs to an account (case-insensitive) with
  a field error, plus links to sign in and to reset the password.
- Existing duplicate accounts are left alone; merging them is a separate decision.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workspace-invitation-journey`: adds what a used invitation link does for a member and for a
  signed-out visitor.
- `registration-abuse-defenses`: the registration form gains the one-account-per-address rule.

## Impact

- `survey/org_views.py::accept_invitation` (used-invitation branch), `org/invitation_landing.html`.
- `survey/abuse.py::RegistrationAbuseForm` (`clean_email`), `django_registration/registration_form.html`.
- New strings in the offered catalogs (`survey/locale/<lang>/LC_MESSAGES/django.po`).
- Tests: `survey/tests/test_workspace_invitation_journey.py`, `test_registration_abuse_defenses.py`.
- Account existence becomes visible from the registration form for a typed address. Usernames
  already were, and the person who hits the wall needs to know at once.
