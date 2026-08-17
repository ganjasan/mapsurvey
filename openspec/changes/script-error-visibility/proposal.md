# Make "Script error." say what actually broke

## Why

Session replay was switched on this morning, and the first recorded creator session immediately
produced two unhandled JavaScript errors on `/editor/surveys/<uuid>/analytics/`. This is what error
tracking received:

```
Error: "Script error."   handled: false   ×2
```

That is the entire payload. No message, no stack, no source file, no line. `Script error.` is what a
browser reports when a script loaded from another origin throws and the page has no permission to
look inside — the same-origin policy blanks the details unless the `<script>` tag carries
`crossorigin="anonymous"` and the server replies with CORS headers.

So we have a defect that fires on the analytics page of a real creator, and our brand-new error
tracking can tell us nothing about it. Twenty of twenty-six external script tags in our templates
are missing the attribute, which means this blindness is the default for almost every third-party
script we load.

The fix is one attribute per tag. Verified before proposing: all twelve CDN hosts we load from —
jsdelivr, unpkg, cdnjs, code.jquery.com, stackpath, challenges.cloudflare.com — reply with
`Access-Control-Allow-Origin: *`, so adding the attribute cannot break loading.

## What Changes

- **`crossorigin="anonymous"` on every external `<script>` tag** in `survey/templates/`, so a
  throwing third-party script reports its message, stack and source instead of `Script error.`
- **A test that fails when a new external script tag arrives without it**, because this is exactly
  the kind of thing that decays: 20 of 26 tags are already missing it, one template at a time.
- **The two known errors get diagnosed** once the attribute is live and the analytics page throws
  again with detail. Fixing the underlying defect is deliberately *not* in this change — we do not
  know what it is yet, which is the whole point.

Out of scope: Subresource Integrity. Seven tags carry `integrity` today and the rest do not, and
adding SRI to a pinned-but-unhashed CDN URL is a separate decision with its own failure mode (a
CDN re-publishing a version takes the site down). Worth doing, not here.

## Capabilities

### New Capabilities

- `client-error-visibility`: what the browser is allowed to tell us when third-party code throws,
  and the guard that keeps it that way.

## Impact

**Code**

- `survey/templates/editor/editor_base.html` (7 tags), `base_survey_template.html` (3 of 6 missing),
  `editor/analytics_dashboard.html` (3), `public_results.html` (3), `survey_language_select.html`
  (2), `editor/survey_share.html` (1), `django_registration/registration_form.html` (1)
- `survey/tests.py` — a guard over the template tree

**Not affected**

- What we load and from where. No CDN is added, removed or re-pointed; this is purely about what the
  browser reports when their code fails.
- Respondent surfaces keep exactly the third-party scripts they already have. `/trust/` already
  states that survey pages load map and interface assets from CDNs, and that stays true.
