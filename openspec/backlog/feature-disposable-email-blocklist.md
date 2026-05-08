# Disposable-Email-Domain Blocklist

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: abuse-prevention
**Created**: 2026-05-08

## Description

Reject registration when the email domain is on a curated list of disposable / throwaway email providers. We've already seen real users on these domains in audit logs:

- `bitoini.com` (Feb 2026 — `aew`, `asef`)
- `ellbit.com` (May 2026 — `orco`, who also created a survey with 9 responses, so blanket rejection isn't always right)
- `mozmail.com` (Firefox Relay — disposable but used by privacy-conscious legit users)
- `immenseignite.info` (May 2026 — bot batch)

## Goals

- Block obvious throwaway-email signups before they create any DB row or send any email.
- Keep the list **curated and conservative** — overblocking will hurt privacy-conscious legitimate users (Firefox Relay, ProtonMail aliases, Apple Hide My Email).

## Scope

### In Scope

- Configurable Django setting `DISALLOWED_EMAIL_DOMAINS` (list).
- Validation in registration form's `clean_email` method.
- Friendly error message ("This email domain is not supported. Please use a different email address.").
- Pull initial list from a maintained open-source dataset (e.g. `disposable-email-domains` GitHub project).
- Update mechanism: a periodic job that pulls fresh upstream and proposes diffs for review (NOT auto-applies).

### Out of Scope

- Allowlist (would restrict to a known set, too restrictive for our use case).
- DNS MX-record validation (some legitimate domains have weird MX setups).
- Real-time email-validation services (Mailgun email validator, ZeroBounce) — costs money and adds latency.

## Open Questions

- Should we **whitelist** Firefox Relay (`mozmail.com`), Apple iCloud Hide-My-Email (`@privaterelay.appleid.com`), and DuckDuckGo Email Protection (`@duck.com`)? These are disposable but indicate privacy-conscious users, often academics. Default: yes, allow them.
- Should `orco`-style cases (real survey activity from a disposable email) be allowed? Easier to keep the simple rule (block disposable) and let edge cases reach out via support if they hit the wall.

## Related

- Epic: [abuse-prevention](epics/abuse-prevention.md)
- Sibling: [feature-email-verification-before-account.md](feature-email-verification-before-account.md)
