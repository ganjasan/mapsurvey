# Signup Anomaly Dashboard

**Type**: improvement
**Priority**: medium
**Area**: backend
**Epic**: abuse-prevention
**Created**: 2026-05-08

## Description

Admin-only view that surfaces registration anomalies in the last 24h / 7d. The 2026-05-07/08 bot incident was caught by happenstance — looking at the report from the daily GTM command (then `/user-outreach`, now `/gtm-daily`) and noticing 41 unfamiliar usernames. With a dashboard, the same pattern would have been visible in minutes.

## Goals

- Detect registration spikes within minutes of them starting, not days.
- Give a one-glance ops view: "Is anything weird happening on signups right now?"
- Cheap to build, big payoff for incident response.

## What to Show

- **Registrations per hour, last 7 days** — sparkline, baseline-aware (highlight days with >3σ over rolling baseline).
- **Top email domains, last 24h** — flag unexpected ones.
- **Top IPs by registration count, last 24h** — flag any IP with >2 registrations.
- **Username pattern anomalies** — count of registrations with usernames matching `^[a-z]{10}$` (the bot pattern from 2026-05-08). This single regex would have flashed red on day 1 of the attack.
- **Unconfirmed-signup rate** — percentage of last-24h signups that haven't confirmed (after [feature-email-verification-before-account.md](feature-email-verification-before-account.md) ships).
- **Email-prefix collision rate** — count of distinct accounts sharing the local-part-before-the-@.

## Implementation Notes

- Plain Django template + queries — no JS framework needed.
- Admin-only access (`@staff_member_required`).
- Refresh button only — no real-time push (overkill for traffic levels).
- Optional: weekly digest emailed to admins, "X new accounts this week, anomalies: …".

## Out of Scope

- ML-based detection (too much for the scale).
- Automatic blocking (dashboard surfaces, human acts).
- Public stats dashboard (this is internal ops).

## Related

- Epic: [abuse-prevention](epics/abuse-prevention.md)
- Sibling: [feature-unconfirmed-signup-purge.md](feature-unconfirmed-signup-purge.md)
- Adjacent: [feature-funnel-monitoring.md](feature-funnel-monitoring.md) (#16 in INDEX) — analogous monitoring for the conversion funnel
