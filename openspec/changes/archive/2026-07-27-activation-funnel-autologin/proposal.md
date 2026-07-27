# Proposal: activation-funnel-autologin

## Why

Production funnel data (2026-07-27): of 269 registered users, **53 never activated** their account and a further **24 activated but never logged in** (~11 distinct people after deduplication). The second cohort is disproportionately high-value institutional leads — DECYP Tasmania, Flagship Housing (both accounts), Riverside County, LichtBlick, SMU, Columbia — people who clicked the activation link and then abandoned at the "Sign In" screen. Three compounding causes:

1. After successful activation, `DirectActivationView` redirects to a static "Account Activated" page that asks the user to **re-enter credentials they typed two minutes ago**. This is the observed drop-off point.
2. `ACCOUNT_ACTIVATION_DAYS = 1`: the activation link dies after 24 hours (django-registration's own default is 7 days). Anyone who opens the email late is dead-ended.
3. The "Activation Failed" page suggests "Try registering again" — which cannot succeed, because the inactive account still holds the username and email. There is no way to re-send an activation link.

The duplicate-account pattern documented in `openspec/backlog/improvement-account-dedup-signup-ux.md` (same person registering 2–3 times: tcoombs/t.coombs, Fränze/fraenze, Echa/vnecha, Claire Cameron ×2) is a direct symptom of causes 2 and 3.

## What Changes

- **Auto-login after activation**: on successful activation, log the user in (via the configured `EmailOrUsernameBackend`) and redirect straight to `/editor/` instead of showing the "Account Activated → Sign In" page.
- **Extend activation window**: `ACCOUNT_ACTIVATION_DAYS` 1 → 7.
- **Resend activation link**: replace the "Try registering again" dead end on the failed/expired-key page with a resend flow — request a fresh activation email for a not-yet-activated account. Abuse-hardened: rate-limited per IP and per account, no account-existence leak (always fake-success response), no-op for already-active accounts.
- **Funnel dashboard: activation stages**: the staff growth-funnel dashboard gains two stages between "registrations" and "created survey" — **activated** (`is_active=True`) and **logged in** (`last_login IS NOT NULL`) — in the monthly cohort table and the all-time totals, so this leak is visible per cohort and the effect of the fixes above is measurable.

## Capabilities

### New Capabilities

- `account-activation`: the account activation flow — activation key lifecycle (validity window), post-activation auto-login and landing, expired/invalid-key handling, and the abuse-hardened resend-activation flow.

### Modified Capabilities

- `creator-funnel-dashboard`: the monthly cohort funnel and all-time totals gain two new stages — activated and logged-in — between registrations and created-survey.

`registration-abuse-defenses` covers `/accounts/register/` and is unchanged; the resend endpoint adopts the same defense patterns (rate limit, fail-open on Redis outage, no-enumeration) but its requirements live in the new `account-activation` spec.

## Impact

- **Code**: `survey/views.py` (`DirectActivationView`, new resend view), `mapsurvey/settings.py` (`ACCOUNT_ACTIVATION_DAYS`), `mapsurvey/urls.py` (resend route), templates `django_registration/activation_failed.html` (+ new resend request/sent templates), reuse of helpers in `survey/abuse.py`; `survey/funnel.py` (cohort stages) and `survey/templates/admin/funnel_dashboard.html` (columns).
- **No schema/migration changes** — no model changes anticipated.
- **Security surface**: new unauthenticated endpoint that sends email → must not become an email-bombing vector (the platform was already attacked via the registration welcome-email path in May 2026); rate limiting and silent no-ops are requirements, not niceties.
- **Interactions**: complements (does not replace) backlog items `feature-email-verification-before-account`, `improvement-account-dedup-signup-ux`, `feature-funnel-monitoring`.
- **Sessions**: auto-login issues a session cookie on the activation GET — flow remains a top-level navigation, so `SESSION_COOKIE_SAMESITE=Lax` is unaffected.
