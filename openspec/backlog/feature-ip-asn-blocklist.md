# IP / ASN Blocklist

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: abuse-prevention
**Created**: 2026-05-10

## Description

Reject registration requests when the source IP belongs to an entry on a curated blocklist of individual IPs and CIDR ranges. Application-layer fallback for the case where edge-level Cloudflare Bot Management is bypassed, misconfigured, or absent.

Real data from `AbuseEvent` on 2026-05-09 motivates two granularities:

- **Per-IP** — `193.34.225.177` was a single repeat offender (8 hits, curl/8.5.0, tripped honeypot+captcha+ratelimit consecutively). Cheap to block by exact IP.
- **Per-CIDR / ASN** — three of seven attacking IPs (`192.210.150.199`, `192.210.198.197`, `198.46.154.21`, `107.173.160.167`) all sit on **ColoCrossing AS36352**, a known bulletproof-hosting AS heavily represented on abuse feeds. A point-IP blocklist would chase a moving target as the attacker rotates within the AS; a CIDR-range entry catches the whole tenant.

Both are configured via the same Django setting; ASN-level lookup is deferred (see Out of Scope) — initial release uses CIDR ranges, which is enough for ColoCrossing-style cases without adding a MaxMind/IP2ASN dependency.

## Goals

- Block obvious abuse-source networks (bulletproof hosters, known botnet C2 ranges) before they consume CAPTCHA quota or trigger rate-limit churn on legitimate co-tenants.
- Stop repeat offenders from the same IP without manual SQL or guessing.
- Provide a tactical knob for fast response to a fresh attack wave (add IP/CIDR, redeploy, monitor).
- Stay in-app — this is the safety net behind the edge WAF, not a replacement for it.

## Why this is Phase 2, not Phase 1

Same shape as the disposable-email blocklist: curated, conservative, sits behind the load-bearing defenses (Turnstile + rate-limit + honeypot). It also overlaps in implementation with the disposable-email feature — both are "match a request attribute against a curated list, reject on hit, log to `AbuseEvent`."

Not Phase 1 because Phase 1 already blocks ~99% of the current attack pattern. This is for the long tail and for fast incident response.

## Scope

### In Scope

- Configurable Django setting `BLOCKED_IPS` — list of strings, each either a single IP or a CIDR (`["193.34.225.177", "192.210.0.0/16"]`).
- IP match runs **first** in `AbuseProtectedRegistrationView` (cheapest filter).
- Reuse `survey.middleware.CloudflareIPMiddleware` for real-client-IP resolution (CF-Connecting-IP) — never block on Cloudflare's own edge IPs.
- Extend `AbuseEvent.DEFENSE_CHOICES` with `('ip_blocklist', 'IP/CIDR Blocklist')` (no migration — `defense` is `CharField`).
- Friendly 403 page with a support-contact line, so legit users hitting from a NAT/co-tenant range can ask for unblock.
- Documented operational runbook step: "to block a fresh attack source, add CIDR to `BLOCKED_IPS`, redeploy, watch `AbuseEvent` for 24h."

### Out of Scope

- ASN-level lookup at request time. Requires a third-party DB (MaxMind GeoLite2 ASN, IP2ASN) — added latency and dependency. Re-evaluate once the Phase 3 anomaly dashboard surfaces ASN clustering as a recurring need.
- Auto-blocking based on `AbuseEvent` thresholds. Thresholds are tricky to get right and false-positives hurt — defer to Phase 3 dashboard with manual approval.
- Edge-level rules (Cloudflare WAF, IP access rules). That belongs in a separate infra epic; the epic's "Out of Scope" section already calls this out.
- Geo-blocking countries. Mapsurvey serves civic-engagement use cases globally — country bans would hit researchers and NGOs in the very regions where participatory mapping matters most.

## Curated Initial List (proposed)

From 2026-05-09 `AbuseEvent` data:

- `193.34.225.177/32` — single-IP repeat offender, curl/8.5.0
- ColoCrossing ranges (verify with WHOIS before committing — published ranges are large; a too-broad CIDR could hit shared VPS users):
  - `192.210.0.0/16`
  - `198.46.128.0/17`
  - `107.173.0.0/16`

Optional one-time seed from public abuse feeds (Spamhaus DROP, Project Honeypot, Stopforumspam toxic CIDR) — imported manually for review, never auto-synced. Same caution applies as for the disposable-email-domain list.

## Open Questions

- Scope: registration endpoint only, or all unauthenticated POST endpoints (login, password-reset, email-resend)? Default — registration only for v1; widen if abuse spreads to other endpoints.
- Publish the blocklist publicly (transparency) or keep private (don't help bots probe)? Default — private; the operational runbook is internal.
- Manual unblock procedure when a legit user reports "I can't register from my office network" — needs a documented path with an audit-log entry.
- ColoCrossing CIDRs are large. Worth narrowing via WHOIS to specific allocations before adding `/16` ranges — verify before commit.

## Related

- Epic: [abuse-prevention](epics/abuse-prevention.md)
- Sibling Phase 2: [feature-disposable-email-blocklist.md](feature-disposable-email-blocklist.md) — same "curated list, validate-then-reject, log to AbuseEvent" pattern
- Sibling Phase 3: [improvement-signup-anomaly-dashboard.md](improvement-signup-anomaly-dashboard.md) — surfaces candidate IPs/CIDRs to add here
