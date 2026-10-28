# Design — expert help service page

## Context

Landings are plain function views that `render` a template extending
`base_landing.html` (see `for_government`), wired in `survey/urls.py`, with
`capture_signup_source(request)` for attribution. Copy uses `{% trans %}`. This
page follows the same pattern exactly.

## Decisions

### 1. Position as optional help, not a paywall

The platform's whole pitch is "free, open source, no per-project fees"
(`for_government` even badges it). The service page MUST reinforce that: the
platform stays free; this is optional paid help for teams that want a hand. Lead
copy says so explicitly so the page cannot read as "the real product costs money."

### 2. Sell the verified outcome, not features

The offer targets the observed pain: teams build + publish but get ~0 responses.
So the page sells outcomes — a well-designed survey and real responses — in two
tiers:
- **Launch help**: design the survey right (question types, map setup, bilingual)
  and set up distribution (shareable / QR / tracked links) so the team can run it.
- **Done-with-you engagement**: Launch help plus planning and driving distribution
  to a response target, watching drop-off, and delivering clean GeoJSON/analysis.

For agency/consultancy visitors (who are themselves the engagement provider to
their client), the copy frames us as their production/success partner, not a
replacement — so we don't scare the ICP.

### 3. No hard prices; book a call

Pricing is scoped per project on a call. This matches the Mom-Test approach used
across outreach (learn their numbers first) and avoids anchoring a wrong price
before the payment rail exists. CTA = book a short call via mailto.

## Non-Goals

- No pricing table, checkout, or payment integration.
- No new nav/menu restructure beyond linking the page where natural.
- No i18n copy beyond wrapping strings in `{% trans %}` (translations later).

## Risks / Trade-offs

- A services page can dilute the free positioning — mitigated by decision 1.
- No price may lower conversion — acceptable; the goal is qualified calls, and
  price belongs on the call until the offer is validated.
