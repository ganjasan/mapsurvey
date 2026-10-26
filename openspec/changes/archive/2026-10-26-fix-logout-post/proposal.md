## Why

Since the Django 5.2 upgrade (#190) clicking **Logout** anywhere shows the browser's "HTTP ERROR 405"
page and the creator stays signed in (#432). Django 5.0 removed GET support from `LogoutView` (a GET
logout lets any page sign a visitor out with an `<img>`), and every Logout control on the site is a
plain `<a href="/accounts/logout/">`. No test requested the logout URL, so the upgrade passed CI.

## What Changes

- One partial, `partials/_logout_form.html`: a POST form to `logout` with the CSRF token and a
  submit button that keeps the look of the link it replaces (class passed by the includer).
- The four Logout links — editor account menu, editor desktop header, dashboard header
  (`base.html`), landing nav (`base_landing.html`) — include it.
- No GET fallback: a GET to `/accounts/logout/` stays 405, as Django intends.
- Tests: POST logs out and redirects to `LOGOUT_REDIRECT_URL`; the editor, dashboard and a landing
  page render a POST logout form and no GET logout link.

## Capabilities

### New Capabilities

- `account-logout`: how a signed-in creator signs out.

### Modified Capabilities

_None._

## Impact

Templates `editor/editor_base.html`, `base.html`, `base_landing.html`, new
`partials/_logout_form.html`, tests in `survey/tests.py`. No model, URL or settings change.
