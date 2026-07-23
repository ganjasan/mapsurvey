## Why

Every outreach lead worked so far (Jaakko, Decisio, MIG, Holly, Justin, SPEN)
builds and often publishes a survey, then gets **~0 real external responses**. The
bottleneck is survey design and getting responses, not the tool. That is exactly
what people pay for, and it points at a **paid service** (help design the survey +
drive real responses) as a monetization to test alongside the free self-serve
platform. We have no public surface describing that help, so there is nothing to
point a lead at and no way for inbound visitors to ask for it.

## What Changes

- Add a public **"Expert help" service page** at `/services/`, styled like the
  existing audience landings (`base_landing.html`), that offers optional paid help
  with survey design and getting responses.
- Frame it as **optional help on top of the free, open-source platform** so it
  does not undercut the "free / no per-project fees" positioning.
- Two tiers (launch help; done-with-you engagement), pricing scoped on a call
  (no hard numbers on the page — consistent with the book-a-call approach).
- Primary CTA books a short call (mailto konuchovartem@mapsurvey.org); add the
  path to robots.txt allow-list.

## Capabilities

### New Capabilities

- **expert-help-service**: a public page describing the paid help service and a
  way to request it.

## Impact

- New view `services` + URL `services/` + template `services.html`.
- `robots.txt` gains `Allow: /services/`.
- No model/migration changes.
