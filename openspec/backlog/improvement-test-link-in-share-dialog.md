# Test link is hidden in password settings while a Share button exists

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-23

## Description

For a survey in `testing` status, the tokenized test URL (`/surveys/<uuid>/?token=<test_token>`)
is only surfaced inside the password/access block of the survey settings
(`editor/partials/survey_password_modal.html`) — a place nobody looks for a shareable link,
given that the editor has a dedicated Share button/dialog. The Share dialog should show the
test link (with copy button and the "regenerate token" action) whenever the survey is in
testing, and label it for what it is: the link you hand to testers.

Observed in practice 2026-08-23: the owner-developer himself could not find the test link in
the UI while preparing the Olney demo (see docs/marketing/user-outreach/olney/) and pulled the
token from the database instead — then pasted the plain section URL into chat, unaware the
token even existed. If the author of the feature can't find it, users won't.

## Notes

- Related: #128 (improvement-share-flow-private-dead-end.md) — same surface, same theme: the
  share dialog doesn't lead with "here is the link a respondent/tester actually needs, and
  here is who can open it". Worth fixing together.
- Access nuance discovered in the same session: `_check_testing_access` allows OPEN access to
  a testing survey when no password is set — the token only gates anything once a password
  exists. Whatever the Share dialog says must reflect that honestly ("anyone with the link"
  vs "testers with the token link; others need the password").
