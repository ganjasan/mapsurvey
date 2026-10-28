## Context

`AbuseProtectedRegistrationView` currently evaluates its defenses in two places. `dispatch()` runs the
per-IP rate limit (two stacked windows, hour and day) with `increment=True` for every POST, before any
knowledge of what was posted. `post()` then runs honeypot → form validation → Turnstile.

That ordering was deliberate and is documented in `registration-abuse-defenses` under "Defense
composition order": honeypot first (cheapest, silent), then rate limit (cheap, local), then Turnstile
(network call to Cloudflare). The reasoning — spend the least resource on the most likely attacker —
is still correct. What was missed is that the rate-limit *counter* is a different thing from the
rate-limit *check*. Checking early is right. Counting early is what traps humans: a person who mistypes
a password three times looks identical, to a counter that runs before validation, to a bot that posted
three registrations.

The production incident of 2026-08-17 is the reference case: three form-invalid POSTs (200), then three
429s, no account, no way to contact the person afterwards. See proposal.md.

Constraints carried into this design:

- The repo is public and merges reach production within minutes, with no staging gate.
- `AbuseEvent` stores no email or username and must keep that guarantee.
- Rate limiting must fail open when Redis is unreachable; that behaviour is already specified and
  tested and must survive this change.
- The registration page must work with JavaScript disabled.

## Goals / Non-Goals

**Goals:**

- A human who fails form validation is never rate-limited out of registering.
- A bot posting well-formed registrations is limited exactly as it is today.
- A refusal, when it does happen, is legible: the user learns what happened and what to do next.
- A user learns their password is unacceptable before spending a submission on it.

**Non-Goals:**

- Reworking the honeypot or Turnstile defenses. Both stay as they are.
- Contacting or recovering the users already lost — the data to do so does not exist and this change
  does not create it.
- Client-side validation as a security control. It is a convenience layer; the server stays the
  authority.
- Changing what `AbuseEvent` stores. No new PII, no migration.

## Decisions

### D1: Split the rate-limit *check* from the rate-limit *increment*

The check stays where it is — early, in `dispatch()`, before form parsing — so an already-limited IP is
refused without spending CPU on validation or a network call to Cloudflare. The increment moves into
`post()`, after `form.is_valid()` is known, and targets one of two independent counters:

- form valid → the existing counter (`registration_hour` / `registration_day`, 3/h, 10/d)
- form invalid → a new counter (`registration_invalid_hour` / `registration_invalid_day`, 15/h, 50/d)

`django-ratelimit`'s `is_ratelimited()` takes `increment` as a parameter, so both phases use the same
helper and the same key function (`survey.abuse.ratelimit_key`, which reads `request.cf_ip`). No new
dependency.

*Alternative considered — keep one counter, raise the limit to 15.* Rejected: it weakens the actual
bot defense by 5×. The whole point is that the two populations are distinguishable, and validity is
exactly the signal that distinguishes them.

*Alternative considered — increment always, then decrement on valid.* Rejected: not atomic, and a
crash between the two leaves the counter permanently wrong.

### D2: A Turnstile failure counts against the strict (valid) counter

A submission with well-formed data and a bad CAPTCHA token is the shape of an automated attempt, not
of a confused human. It counts against the 3/hour budget. This keeps the effective bot limit identical
to today's.

### D3: The invalid-attempt ceiling exists to bound abuse, not to catch it

15/hour and 50/day are set far above plausible human friction (the incident case needed 3) and far
below what makes the endpoint useful as a password-validator oracle or a CPU sink. Nobody legitimate
should ever see this limit; if the `AbuseEvent` rows say otherwise, the number is wrong, not the user.

Rows written by this counter use `defense='ratelimit'` with `detail='invalid_hour'` / `'invalid_day'`,
so the two populations stay distinguishable in the audit log without a schema change.

### D4: The 429 becomes a rendered template, keeping status and headers

`survey/templates/registration/rate_limited.html`, extending `base.html`, in the site layout. It states
what happened, when to retry (derived from `Retry-After`), and links to sign-in and password reset — the
two things a person who is actually a returning user needs. The HTTP status stays 429 and `Retry-After`
is unchanged, so nothing about the machine-readable contract shifts.

The response deliberately does not explain *which* limit was hit or how many attempts remain: that
would let an attacker map the thresholds.

### D5: The live password checklist is progressive enhancement

A small script mirrors the four `AUTH_PASSWORD_VALIDATORS` rules and ticks them off as the user types.
Its only job is to prevent a wasted round-trip. With JS off, the styled static help text (D6) remains
and behaviour is exactly as today. The script never blocks submission — a user who wants to submit an
apparently-bad password may, and the server decides.

The similarity check (`UserAttributeSimilarityValidator`) is approximated client-side against the
email and username fields as typed. An approximation that disagrees with the server is acceptable in
the permissive direction only: the checklist may say "ok" and the server still reject, but it must not
claim a rule is violated when the server would accept.

### D6: Auth-page form styling is a new capability, not a patch to `question-card-styling`

`.errorlist` is currently styled only under `.question-card`, which is respondent-facing survey UI.
Auth pages are a different surface with a different owner. Rather than widening a survey selector to
reach into auth templates, `auth-form-feedback` owns the auth-page presentation rules. Editing happens
in `survey/assets/css/main.css`, followed by `collectstatic`.

### D7: Help text states the constraint that can actually be violated

Django's stock username help text advertises a 150-character ceiling. Replacement text names the
minimum and the allowed character set. Same principle applies to email and password fields: describe
the wall a person can walk into, not the one they cannot reach.

## Risks / Trade-offs

- **[A bot now gets 15 invalid POSTs/hour instead of 3 total]** → Those POSTs cost one form validation
  each and produce no account, no email, and no external network call (Turnstile is never reached on an
  invalid form). The valid-submission path — the one that creates users and sends mail — is unchanged
  at 3/hour.
- **[The endpoint becomes a slightly better password-policy oracle]** → Our policy is Django's stock
  validator set and is not secret. The 15/hour ceiling bounds the query rate regardless.
- **[Moving the increment into `post()` means a request that raises mid-validation never counts]** →
  Acceptable and fails in the safe direction for users; an exception in form validation is a defect we
  would want to see in PostHog error tracking anyway, not a case to meter.
- **[The client-side checklist drifts from server validators when settings change]** → It reads the
  four stock validators, which have not changed in the project's lifetime. A test asserts the rendered
  checklist matches `AUTH_PASSWORD_VALIDATORS`, so a settings change fails the suite rather than
  shipping a lying UI.
- **[Existing tests assert the old counting behaviour and are green]** → They encode the defect. They
  get rewritten as part of this change, not adjusted to pass. This is called out explicitly because a
  green suite is what let this ship.

## Migration Plan

1. Ship behind `REGISTRATION_SPLIT_RATE_LIMIT` (default `True` in code, settable to `False` from the
   Render dashboard without a rebuild). Flipping it off restores today's single-counter behaviour.
   Merge reaches production in minutes with no staging gate, so a dashboard-flippable switch is the
   rollback.
2. No migration. `AbuseEvent` is unchanged; the new counters live in Redis under new group names and
   expire on their own.
3. After deploy, watch `AbuseEvent` rows with `detail='invalid_hour'`. A nonzero rate means either the
   ceiling is too low or something is genuinely hammering the endpoint; both are worth knowing within
   the first day.
4. Verify a real registration end-to-end on production after merge, including the 429 page (reachable
   by exceeding the limit deliberately from a throwaway IP).

## Open Questions

- Should the 429 page offer a "email me when I can try again" escape hatch? It would recover exactly
  the population this change is about, but it means collecting an email address on a request we have
  just classified as abusive — which cuts against `AbuseEvent`'s no-PII stance. Deferred; not in this
  change.
- The incident also showed six POSTs producing zero funnel visibility. Whether `AbuseEvent` should feed
  the funnel dashboard as a distinct "blocked before registration" stage is a separate change.
