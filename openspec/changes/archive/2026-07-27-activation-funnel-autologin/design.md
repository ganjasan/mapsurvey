# Design: activation-funnel-autologin

## Context

Registration uses `django_registration`'s two-step activation backend. `AbuseProtectedRegistrationView` creates the user inactive and emails an activation link; `DirectActivationView` (survey/views.py:198) activates on GET and redirects to `django_registration_activation_complete` — a static page whose only affordance is a "Sign In" button. `ACCOUNT_ACTIVATION_DAYS = 1`. The failed-activation page links to "Try registering again", which dead-ends because the inactive account still holds the username/email.

Prod funnel (2026-07-27): 53 accounts never activated; 24 activated but never logged in (~11 distinct people, disproportionately institutional leads). The staff growth-funnel dashboard (`survey/funnel.py` + `admin/funnel_dashboard.html`) currently has no visibility into either stage: its cohort rows jump from `regs` straight to `created`.

Constraints:

- The platform was attacked via subscription-bombing in May 2026 (registration welcome emails to harvested addresses). Any new unauthenticated endpoint that sends email must be defended in the same way as `/accounts/register/` (rate limit via `django-ratelimit` patterns in `survey/abuse.py`, fail-open on Redis outage, no account-existence leak).
- Single auth backend: `survey.backends.EmailOrUsernameBackend`.
- Funnel dashboard derives all stages live from existing tables — no event log; new stages must follow the same pattern (`is_active`, `last_login` are already on `auth_user`).

## Goals / Non-Goals

**Goals:**

- A user who clicks a valid activation link lands in `/editor/` already authenticated.
- An activation link stays valid for 7 days.
- A user with an expired/invalid key can request a fresh activation email without re-registering; the flow is not usable for email-bombing or account enumeration.
- The staff funnel dashboard shows per-cohort and all-time counts for **activated** and **logged in**, positioned between registrations and created-survey.

**Non-Goals:**

- No email-verification-before-account restructuring (backlog: `feature-email-verification-before-account`).
- No duplicate-account merging or same-email signup rerouting (backlog: `improvement-account-dedup-signup-ux`).
- No changes to the registration endpoint or its defenses.
- No historical backfill of "when did activation happen" — `auth_user` has no activation timestamp; cohort stages count current state, same as every other funnel stage.

## Decisions

### D1. Auto-login inside `DirectActivationView.get()`, not via `RegistrationView` signals

After `self.activate(form)` returns the user, call `django.contrib.auth.login(request, user, backend='survey.backends.EmailOrUsernameBackend')` and redirect to `settings.LOGIN_REDIRECT_URL` (`/editor/`). The explicit `backend=` kwarg is required because `login()` otherwise expects `user.backend` set by `authenticate()`, which never ran.

*Alternative considered*: listening to `django_registration`'s `user_activated` signal in an app hook. Rejected — the signal handler has no clean way to influence the view's redirect, and we already own the view subclass.

*Kept*: the `activation_complete` template remains as a fallback (direct visits to the URL, e.g. from history), now with a line "you are signed in" only when relevant — in practice the redirect bypasses it entirely; the template's "Sign In" button stays for the anonymous case.

### D2. `ACCOUNT_ACTIVATION_DAYS = 7`, env-overridable

Match django-registration's default. Read from `os.environ` with default 7, consistent with how the abuse settings are configured. Keys signed with the old 1-day window automatically benefit (validity is checked against the setting at activation time, not at signing time).

### D3. Resend flow: separate endpoint, silent success, signed-key regeneration

- `GET /accounts/activate/resend/` renders a one-field form (email). `POST` always redirects to a "check your inbox" page regardless of whether the email matched anything (**no enumeration**).
- Handler behaviour: look up `User` by email (case-insensitive). If found AND `is_active=False` → re-send the standard activation email using the same machinery as registration (`RegistrationView.get_activation_key(user)` + the existing `django_registration/activation_email*` templates, reusing `AbuseProtectedRegistrationView.email_html_template`). Found-and-active or not-found → do nothing, same redirect. Activation keys are stateless signed values (`TimestampSigner` over the username), so "regeneration" is just signing again — no DB writes.
- **Rate limits**: reuse the `survey/abuse.py` pattern — per-IP `3/h` and per-email `3/d` (settings-backed like `REGISTRATION_RATE_LIMIT_*`), fail-open if Redis is down, over-limit logged to `AbuseEvent` with a new `event_type='resend_rate_limited'` (existing choices permitting; otherwise reuse the generic rate-limit type — resolve in implementation against the `AbuseEvent` model).
- **Honeypot**: same hidden `website` field trick as registration; a filled honeypot silently fake-succeeds.
- *Alternative considered*: auto-resend on expired-key detection in `DirectActivationView` (no form). Rejected — the activation URL with a stale key can be re-fetched by mail scanners and would trigger unsolicited email sends; an explicit user-facing form with rate limits is the safer shape.

### D4. Failed-activation page routes to resend, not re-register

`activation_failed.html` replaces "Try registering again" with a link to the resend form (email prefilled when derivable — it is not, from a signed key alone, so no prefill). Copy explains the link may have expired and a new one can be requested.

### D5. Funnel stages: `activated` and `logged_in` from `auth_user` columns

`survey/funnel.py`:

- `_blank_row` gains `activated` and `logged_in` keys (after `regs`).
- `cohort_funnel()` iterates `self._real_users().values_list("id", "date_joined", "is_active", "last_login")` and increments the two counters; `alltime_totals()` adds the keys to its sum list.
- Dashboard template `admin/funnel_dashboard.html` gains two `<th>/<td>` columns between Regs and Created, in both cohort table and all-time header cards.

Semantics are point-in-time (an account activated today counts in its signup cohort's `activated` immediately), identical to how `created`/`published` behave today. `last_login` is maintained by Django's `user_logged_in` signal, which `login()` fires — so the auto-login of D1 correctly marks users as logged-in.

*Alternative considered*: tracking activation timestamps for time-boxed columns (activated-within-7d). Rejected — `auth_user` stores no activation time; adding a model/table for it is out of proportion for a staff dashboard.

## Risks / Trade-offs

- [Resend endpoint as spam vector] → honeypot + per-IP and per-email rate limits + silent no-op for active/unknown accounts; only ever emails an address that already registered, and at most 3/day.
- [Auto-login on a GET link: mail scanners pre-fetching the link] → the scanner activates the account and receives a session cookie *in its own session*; the user's later click re-runs activation, which now raises `ActivationError(code="already_activated")` → previously a dead-end failure page. Mitigation: that code is treated as benign and redirects to login (`?activated=1`), or to `/editor/` if the session is already authenticated.
  **Auto-login fires only on the genuine inactive→active transition, never on the already-activated replay.** This is deliberate: activation can only succeed once, so signing in there keeps the key single-use as a credential. Signing in on replay would instead turn the activation link into a bearer token valid for the whole `ACCOUNT_ACTIVATION_DAYS` window — anyone later obtaining the email (forward, shared inbox, browser-history sync) could sign in as that user. Given the user base includes government and child-services accounts, the small UX loss for the scanner-then-human sequence (one login form) is the correct trade.
- [Fail-open rate limiting] → same accepted trade-off as registration (documented in `registration-abuse-defenses`); Redis outage briefly disables throttling rather than blocking real users.
- [Cohort `activated`/`logged_in` are current-state, not as-of-cohort-age] → same caveat as every other stage in this dashboard; documented in the template legend.

## Migration Plan

Code + settings only; no migrations expected (unless `AbuseEvent.event_type` choices need a new value — that is a choices-only change, still no schema migration in Django for `choices`). Deploy normally on Render. Rollback = revert commit. Existing unexpired activation emails keep working; expired-key holders gain the resend path immediately.

## Open Questions

- Whether `AbuseEvent.event_type` has a reusable value for resend rate-limiting or needs a new choice — resolve against `survey/models.py` during implementation.
