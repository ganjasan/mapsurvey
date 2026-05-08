# Registration Rate Limiting

**Type**: feature
**Priority**: very high
**Area**: backend
**Epic**: abuse-prevention
**Created**: 2026-05-08

## Description

Hard rate-limits on the `/register/` endpoint. A defense-in-depth layer behind Turnstile (see [feature-registration-captcha.md](feature-registration-captcha.md)) — if a bot solves the CAPTCHA at scale, rate-limiting still caps damage.

## Goals

- Cap the maximum number of new accounts a single IP can create per time window.
- Cap the rate of registration POSTs total (global flood protection).
- Make it cheap for the attacker to fail and expensive to succeed.

## Proposed Limits (initial — tune from real traffic)

| Scope | Limit | Rationale |
|-------|-------|-----------|
| Per IP | 3 accounts / hour | Real users almost never sign up >1 account in an hour |
| Per IP | 10 accounts / day | Allows shared-NAT classroom contexts (Mora, NYU labs) but blocks single-IP bot bursts |
| Global | 60 successful registrations / hour | Soft alarm (Slack/email notification), not a hard block |

Limits are configurable via Django settings so they can be tuned from production data.

## Goals

- Block volumetric bot bursts (the 2026-05-07/08 incident hit ~1.1 accounts/hour from probably-rotating IPs — a per-IP limit alone wouldn't have stopped it; need both per-IP and global).
- Avoid blocking legitimate classroom signups: a teacher demoing Mapsurvey to 30 students from one school WiFi should still work, but slowly. Per-IP/day = 10 covers most classes; for true classroom mass-signup, the teacher creates accounts via the admin or a future bulk-invite feature.

## Implementation Notes

- `django-axes` or `django-ratelimit` — both well-maintained.
- `django-axes` is auth-focused; `django-ratelimit` is more general — the latter is the better fit because we want IP-based registration limits, not failed-login lockouts.
- Cache backend: Redis (already on Render or via Render Redis add-on).
- Counters are a sliding window or fixed bucket — fixed bucket is simpler and good enough.
- Return HTTP 429 with `Retry-After` header on hit, with a friendly UI message.

## Out of Scope

- IP geolocation blocking (too many false positives — VPN-using academics).
- Rate limits on survey-response submission (different concern).

## Open Questions

- Per-email-prefix rate limiting (e.g. block 5+ accounts with the same `before-the-@` part)? Some attackers use `victim+1@gmail.com`, `victim+2@gmail.com` to bypass duplicate-email checks. Worth adding to Phase 2.
- Render is behind Cloudflare — make sure we get the real client IP via `HTTP_CF_CONNECTING_IP`, not `HTTP_X_FORWARDED_FOR`'s last hop.

## Related

- Epic: [abuse-prevention](epics/abuse-prevention.md)
- Sibling: [feature-registration-captcha.md](feature-registration-captcha.md)
