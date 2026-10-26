## Context

`django.contrib.auth.urls` serves `LogoutView`, which since Django 5.0 answers only POST (and
OPTIONS). All four Logout controls are anchors, so they send GET and get 405.

## Decisions

- **POST form, not a GET-tolerant view.** Re-enabling GET (a custom view calling `logout()`) would
  bring back the logout-CSRF hole Django closed. A form costs one partial.
- **One partial for four places.** `{% include "partials/_logout_form.html" with btn_class=… %}`;
  the form is `display:inline` / `margin:0` so it sits where the anchor sat, the button resets
  browser chrome (`background:none; border:0; padding:0; font:inherit; color:inherit;
  cursor:pointer`) and takes the anchor's class (`dropdown-item`, `nav-desktop`) so Bootstrap's
  dropdown styling and the mobile hide rule keep applying. A `form` with class `nav-desktop` is
  hidden on mobile the same way the anchor was.
- **No `next`.** `LOGOUT_REDIRECT_URL = '/'` already decides where the creator lands.

## Risks

- A `<button>` inside `.dropdown-menu` gets Bootstrap's `.dropdown-item` styles only when it has the
  class — passed explicitly. Checked in the browser on the editor and dashboard.
