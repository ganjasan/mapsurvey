# Design: activation-confirm-post

## Context

`DirectActivationView` (survey/views.py) activates accounts and auto-logs-in on GET — shipped in `activation-funnel-autologin` (archived 2026-07-27). Production logs from the same day show Microsoft Defender Safe Links issuing **GET** requests (full Chrome UA, Azure IPs) against activation links minutes before the human clicks. The scanner consumes the single inactive→active transition; the human hits the already-activated branch and gets a login form instead of the promised signed-in landing. Confirmed twice in one day (DECYP Tasmania, Silesian University of Technology), both ending in duplicate accounts.

Upstream django-registration's `ActivationView` is a FormView that activates on POST precisely to be scanner-proof; the GET shortcut was a local customization predating this project phase.

## Goals / Non-Goals

**Goals:**

- The human, not the mail scanner, consumes the activation transition — so auto-login lands on the human's session on every mail host, including Microsoft 365.
- GET on the activation URL has no side effects.

**Non-Goals:**

- No change to replay semantics (already-active + valid key never signs in — the bearer-token argument from the previous change).
- No scanner fingerprinting (IP ranges / UA heuristics) — the scanner presents a full Chrome UA; heuristics would be both brittle and bypassable.
- No change to the resend flow, rate limits, or funnel dashboard.

## Decisions

### D1. Same URL, GET renders confirmation, POST activates

GET `/accounts/activate/?activation_key=…` validates the key (signature + expiry, stateless) and branches:

- missing/expired/tampered key → failure page (with resend link), as today;
- valid key, account already active → login redirect (`?activated=1`) or `/editor/` when authenticated, as today;
- valid key, account inactive → **render `activation_confirm.html`**: one form, hidden `activation_key`, one "Confirm my email" button, standard CSRF token.

POST re-validates the key from the form body and performs activate + auto-login + redirect to `/editor/`. `ActivationError(already_activated)` on POST → login redirect (same rationale: a form submission proves a human is present, not that the *owner* is — the key must not become a reusable credential).

*Alternative considered*: JS auto-submit of the confirm form on page load (zero extra click). Rejected — link scanners that execute JS (Safe Links detonation does) would submit it too, reintroducing the bug for exactly the affected population.

### D2. Validation shared between GET and POST via `ActivationForm`

Both verbs run the upstream `ActivationForm` (signature + expiry → username), then a user lookup. GET uses the result only for routing (no writes); POST proceeds to `activate()`. Keeps one validation path and the upstream salt/expiry semantics.

### D3. HEAD stays harmless

Django serves HEAD through `get()`; since GET no longer mutates, the EOP HEAD probes observed in logs become no-ops by construction.

## Risks / Trade-offs

- [One extra click for every user] → accepted; the click is a single button on a page that explains itself. This is the industry-standard shape for exactly this reason.
- [Scanner "detonation" that submits forms] → known Safe Links behavior is link-following, not form submission with CSRF cookies; if that ever changes, no design at this layer survives, and the fallback is magic-link login (out of scope).
- [Users with stale emails containing pre-change links] → unaffected: the URL is unchanged, old links land on the confirm page and work.

## Migration Plan

Code + template only. Deploy normally; rollback = revert. No data or settings migration.

## Open Questions

_None._
