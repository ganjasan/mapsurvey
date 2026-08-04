# Epic: Abuse Prevention

**Slug**: abuse-prevention
**Created**: 2026-05-08

## Description

Defenses against automated registration abuse on `mapsurvey.org`. Triggered by a real incident on 2026-05-07/08 where 41 bot accounts registered in ~36 hours using random 10-character usernames paired with real (apparently harvested) email addresses from a wide range of providers. Several email addresses repeated across multiple accounts.

The pattern matches a **subscription bombing / email-bomb** attack: the bot's goal is not to use Mapsurvey but to **make Mapsurvey send welcome/verification emails to a list of victim addresses**, which the attacker uses to bury legitimate notifications (often password-resets, fraud alerts) in the victim's inbox during a separate fraud workflow elsewhere.

Mapsurvey is not the target — it is being used as an unwilling email cannon. The cost is real:

- **SMTP reputation damage** — bursts of welcome emails to unrelated addresses look like spam to provider abuse-detection systems. Reputation loss makes legitimate outreach (Decisio, StefSier, hmsbrito7 etc.) start landing in spam folders.
- **Blocklist exposure** — victims report mapsurvey.org as a spam source. Domain ends up on RBLs.
- **Resource and metric pollution** — junk users in `auth_user`, distorted active-user counters, wasted email budget.
- **Operational risk** — without rate limits, a single attacker can scale to hundreds/day at zero cost to themselves.

The 41 bot accounts from this incident were deleted manually on 2026-05-08 (DB IDs 112-157, excluding 121/122/128/135/148). This epic exists so we don't have to do that again.

## Vision

> A bot that hits the registration endpoint at `mapsurvey.org/register/` cannot create a Mapsurvey account, cannot trigger an email send to a victim's inbox, and cannot get past the first request. Real users (a teacher in Mora, a researcher in Cairo, a consultant in Torino) experience zero added friction — Turnstile invisibly clears them in <1s, and their welcome email is the first one they see in their inbox, not the 47th.

## Scope

### In Scope

- Bot detection on the registration endpoint (CAPTCHA / Turnstile / hCaptcha).
- Email verification **before** the `auth_user` row is created — no DB pollution from unconfirmed signups.
- Rate-limiting registrations by IP and by email-address-prefix collision.
- Honeypot field on the registration form.
- Blocklist of known disposable / throwaway email domains (ellbit.com, bitoini.com, immenseignite.info, mozmail.com, …).
- Periodic audit-and-purge cron for accounts that signed up but never confirmed within N days.
- Documentation on what to do operationally if another incident slips past these defenses (the cleanup query used on 2026-05-08).

### Out of Scope (for this epic)

- General fraud detection on survey responses (separate concern, belongs under data-management).
- Auth flow rewrite (Django allauth migration etc.) — orthogonal.
- WAF / Cloudflare Bot Management at edge — would help but is a separate infra epic.
- 2FA for survey creators.

## Phases

### Phase 1: Stop the bleeding (high priority, blocks outreach)

1. Cloudflare Turnstile (or hCaptcha) on `/register/`.
2. Rate-limit registration requests per IP (django-axes or middleware).
3. Honeypot field.

These three together block ~99% of automated subscription-bombing scripts and can ship in days, not weeks. **They block the outreach campaign**: if we keep getting bot bursts, deliverability of the 30+ legitimate outreach emails currently in flight drops further.

### Phase 2: Reduce friction and DB noise

4. Email verification before account creation (move user creation to post-confirmation step).
5. Disposable-email-domain blocklist.
6. Auto-purge of unconfirmed signups after N days.
7. IP / CIDR blocklist (app-layer; complements but does not replace edge WAF).

### Phase 3: Operational hardening

8. Admin dashboard view: "registrations in the last 24h grouped by IP / email domain" — so the next incident is detected in minutes, not days.
9. Documented incident-response runbook (FK chain, cleanup query, deliverability check).

## Real-World Driver

**2026-05-07/08 subscription-bombing attack.** 41 accounts in 36 hours; emails harvested from US, DE, UK, NL, AU domains; some emails repeated 2x; nobody logged in after registration; nobody created surveys.

This was almost certainly **not** a one-time event — bot operators rotate target services. Without defenses, the next wave will be larger. The earlier incidents (`aew@bitoini.com`, `asef@bitoini.com` in February — 2 accounts that did create empty surveys) suggest the site has been on lower-volume bot lists for months; the 2026-05 incident is the escalation.

The cost of inaction = lost deliverability = the carefully-built outreach campaign (~30 emails, several active conversations) silently degrades.

## Related Backlog Items

- feature-registration-captcha.md — Phase 1 item 1
- feature-registration-rate-limiting.md — Phase 1 item 2
- feature-registration-honeypot.md — Phase 1 item 3
- feature-email-verification-before-account.md — Phase 2 item 4
- feature-disposable-email-blocklist.md — Phase 2 item 5
- feature-unconfirmed-signup-purge.md — Phase 2 item 6
- feature-ip-asn-blocklist.md — Phase 2 item 7
- improvement-signup-anomaly-dashboard.md — Phase 3 item 8

## Blocks / Blocked By

- **Blocks**: User outreach campaign deliverability — every additional bot burst chips at SMTP reputation. Treat as a hidden dependency for any feature that relies on outbound email.
- **Blocked by**: Nothing. Phase 1 can ship immediately; the work is small and well-known (Turnstile is a 30-line integration).

## Notes

- Counter-intuitively, **email verification alone (Phase 2.4) is not enough** — the welcome/verification email itself is what the attacker wants to send. We must block bots **before** they can trigger any outbound mail. CAPTCHA on the form is the load-bearing defense.
- Cloudflare Turnstile is preferred over hCaptcha because it has invisible / managed challenges by default, lower friction for legitimate users.
- Keep the OpenSpec change scope tight: each Phase 1 item is its own change so they can ship in parallel.
