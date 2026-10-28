# Proposal: fix-opaque-script-errors

## Why

The largest error group in the project carries no information at all:
[`01a00c89`](https://eu.posthog.com/project/248938/error_tracking/01a00c89-ca7a-7cf2-8f6b-824c5bfe3489)
— **107 events, 37 sessions, 18 people over 30 days**, every one of them the bare string
`Script error.` with no message, no file, no line, no stack.

That string is what a browser reports when an exception is thrown inside a **cross-origin script
served without CORS**. The details are withheld on purpose; the fix is to declare
`crossorigin="anonymous"` on the tag so the browser is allowed to hand them over.

Scanning every `<script src>` in the templates we ship, exactly one external script lacks the
attribute — Plausible, in `partials/_analytics.html`:

```django
<script async src="{{ PLAUSIBLE_SCRIPT_URL }}"></script>
```

Every CDN tag in `base.html`, `editor_base.html` and `base_survey_template.html` already has it, and
the PostHog snippet sets `crossOrigin="anonymous"` on the element it injects.

The distribution confirms it. `_analytics.html` is included by `base.html` and `editor_base.html`
but **not** by `base_survey_template.html` — respondent pages deliberately load no analytics. Split
by URL path:

| surface | events |
|---|---|
| pages that include the analytics partial | **107** |
| respondent `/surveys/…` | 0 |
| respondent `/r/…` | 0 |

The opaque errors appear on exactly the pages that load this script and on no others.

An earlier guess in this review — that Tawk was responsible, since it sets
`s1.setAttribute('crossorigin','*')` and `*` is not a valid keyword — was **wrong**. An invalid
keyword maps to the anonymous state, so Tawk loads with CORS, and its errors already arrive fully
described (`t.$_Tawk.i18next is not a function`, file `twk-vendor.js`). It was checked and cleared.

`plausible.io` answers with `access-control-allow-origin: *`, verified against the exact script URL
production serves, so the attribute is safe to add: a host that did **not** send that header would
refuse to execute the script, which is the one way this change could do harm.

## What Changes

- **`crossorigin="anonymous"` on the Plausible tag.**
- **A guard test that scans the shipped templates** and fails if any external `<script src>` lacks a
  `crossorigin` attribute, plus a second test pinning the scanner itself so a regex that stopped
  matching could not make the first pass forever.

The guard is the point. A missing `crossorigin` breaks nothing visible — it silently blinds error
tracking for that script, so nothing else in the suite would ever catch it, and the next script
someone adds would be as opaque as this one has been.

## What this will and will not do

**It will not reduce the event count.** It converts 107 opaque events per month into described ones.
Whatever is throwing will keep throwing; we will finally know what and where. It is entirely
possible that a real defect has been hiding in this group — that is the reason to do it before the
remaining product work, not after.

## Capabilities

### Modified Capabilities

- `product-analytics`: scripts we load from other origins are loaded so that exceptions inside them
  can be attributed.

## Impact

- **Code**: `survey/templates/partials/_analytics.html`, tests in `survey/tests.py`.
- **No migrations, no settings, no Python changes.**
- **Risk**: if `plausible.io` ever stopped sending `access-control-allow-origin`, the script would
  fail to execute and Plausible would stop recording. Verified present today; noted here because it
  is the failure mode to check first if Plausible numbers ever go flat after this ships.
