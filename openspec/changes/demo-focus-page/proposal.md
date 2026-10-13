## Why

`/demo/` (shipped in #292) renders inside the full marketing chrome: navbar, hero grid background and a five-column footer. The single email field we want filled competes with about forty links. Notion's `/contact-sales` shows the pattern that works: a focused page with one question and one field. Issue #294.

## What Changes

- `/demo/` (all three states: email, details, done) becomes a focused split page:
  - no navbar, no footer — only the Mapsurvey wordmark top-left, linking home;
  - left: a large question ("What's your work email?" on step one), the field, a full-width "Next" button;
  - right: a carousel of real, attributed customer quotes from published stories (Anna M. Pyziak, TUP; Julian Thomas and Cliff Schraibman, Whitehouse Community Council), with initials as avatars until a photo is approved, instead of an illustration;
  - bottom: a strip of customer logos built from published stories that have a credit logo, each linking to its story; omitted when there are none.
- On phones the columns stack: form first, quote under it, logos last.
- `base_landing.html` gains `nav` and `footer` blocks so a page can opt out of the chrome; every other page renders as before.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `demo-request`: the page requirement gains the focused layout, the quotes carousel and the logo strip.

## Impact

- Templates: `base_landing.html` (two blocks, no markup change), `demo.html`.
- Code: `survey/demo_request.py` (quote constant, logo query), `survey/demo_request_views.py` (context).
- CSS: `landing.css` (`demo-*` rules replaced).
- Tests: `DemoRequestTest` additions.
