# Migrate Transactional Email to a Dedicated ESP (Deliverability)

**Type**: feature
**Priority**: very high
**Area**: infra
**Epic**: —
**Created**: 2026-07-05

## Description

Move all Django-generated transactional email (account activation, password reset, and any future system mail) off the shared Namecheap PrivateEmail SMTP relay and onto a dedicated transactional Email Service Provider (Postmark / Amazon SES / Resend / Brevo). Add the missing DMARC record and fix the `http://` links in outgoing mail as part of the same hardening.

Today the app sends everything through PrivateEmail's shared outbound IP (`198.54.118.213`). We do not control the reputation of that IP — hundreds of unrelated domains send from it. When a neighbour spams, the IP gets listed and **our** activation emails silently fail to deliver.

## Incident that triggered this

On 2026-07-04, Tyler Mitchell (`spatialguru@shaw.ca`, `auth_user.id = 313`) — OSGeo co-founder and author of *Web Mapping Illustrated*, a high-value lead — signed up but never received his activation email. Shaw's mail filter (Cloudmark, `cloudfilter.net`) rejected it with:

```
552 5.2.0 ... mail accepted for delivery AUP#BL
```

`AUP#BL` = the sending IP is on Cloudmark's blocklist. The misleading "mail accepted for delivery" wording hides a hard rejection. His account had to be activated manually via the prod DB, and the welcome email had to be sent from a personal address to route around the block.

## Root cause

- **Shared sending IP with no reputation control.** `198.54.118.213` is clean on public blocklists (Spamhaus, Barracuda, SpamCop, SORBS, PSBL all return clean) but is listed by **Cloudmark**, which is a private, reputation-based feed used by Shaw/Rogers, Comcast, Charter and other large North American ISPs. Cloudmark listings can't be fixed via public delisting — only the IP owner (Namecheap) can request a CSI reset.
- **No isolation between "human mailbox" and "app mail."** `hello@` / `konuchovartem@mapsurvey.org` share the same relay as automated activation mail, so one reputation problem takes down both.
- **Silent failure.** The bounce only surfaced because the NDR happened to be read by hand. Any other blocked activation is invisible — the user just never logs in, and it counts as a lost activation against the North Star metric.

## Goals

- Activation and password-reset email delivers reliably to the major consumer ISPs (Shaw/Rogers, Gmail, Outlook, Yahoo, Comcast).
- Sending-IP reputation is controlled and monitored by a provider whose whole business is deliverability.
- Bounces and blocks become visible (provider webhooks / dashboard) instead of silently swallowed.
- Domain email auth is complete: SPF + DKIM + **DMARC** all present and aligned.

## Scope

### In Scope

- **Pick and integrate a transactional ESP.** Candidates: Postmark (best-in-class transactional deliverability, ~$15/mo), Amazon SES ($0.10 / 1k, cheapest at scale), Resend (3k emails/mo free, modern DX), Brevo (free tier). All expose SMTP, so the Django code does not change — only `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` env vars on Render.
- **DNS records for the ESP**: add the provider's DKIM CNAME/TXT, extend the SPF `include:` to cover the ESP, keep PrivateEmail in SPF for the human mailboxes.
- **Add a DMARC record** — currently absent for `mapsurvey.org`. Start `p=none` with `rua=mailto:konuchovartem@mapsurvey.org` to collect reports, then tighten to `p=quarantine`.
- **Keep human mailboxes on PrivateEmail.** Only Django-generated mail moves; `hello@` / `konuchovartem@` stay for real correspondence.
- **Fix `SECURE_PROXY_SSL_HEADER`** so `request.is_secure()` is true behind Render's proxy and activation links render as `https://` instead of `http://` (the current `http://` scheme both hurts spam scoring and is a bug on its own).
- **Bounce visibility**: wire the ESP's bounce/complaint webhook (or at minimum a "registered but not activated > 24h" indicator on the funnel dashboard / Discord alert) so the next blocked activation is caught automatically instead of by hand.

### Out of Scope

- Migrating the human `hello@` / `konuchovartem@` mailboxes off PrivateEmail.
- Marketing / bulk email (outreach campaigns) — those are sent manually and are a separate deliverability profile.
- Rewriting the activation flow itself (see abuse-prevention epic for the pending-signup redesign) — this change is purely about the transport.

## Immediate mitigation (do before the migration lands)

1. **Open a Namecheap support ticket** with the bounce report to request a Cloudmark CSI delisting of `198.54.118.213`. This unblocks current mail while the ESP migration is in flight, but on a shared IP a re-list is only a matter of time — it is a stopgap, not the fix.
2. **Add the DMARC record now** — it's DNS-only, independent of the ESP choice, and helps overall domain reputation immediately.

## Open Questions

- **Which ESP?** Default recommendation: Resend or SES for cost at current volume; Postmark if we want the strongest transactional deliverability out of the box. Decision driver is volume trajectory and willingness to pay ~$15/mo vs. usage-based.
- **Dedicated vs. shared IP at the ESP.** At our current low volume a shared-but-well-managed ESP pool beats a cold dedicated IP (dedicated IPs need consistent warm-up volume to build reputation). Revisit only if volume grows enough to warrant a dedicated IP.
- **DMARC policy ramp**: how long to sit at `p=none` before moving to `p=quarantine` / `p=reject` — depends on what the aggregate reports show.

## Related

- Incident record: `docs/marketing/user-outreach/spatialguru/` (Tyler Mitchell profile + correspondence)
- Epic: [abuse-prevention](epics/abuse-prevention.md) — adjacent (also touches the registration/activation flow), but this is a delivery-transport concern, not an anti-abuse one
- Sibling: [feature-email-verification-before-account.md](feature-email-verification-before-account.md) — reshapes *when* activation mail is sent; this reshapes *how* it's delivered
