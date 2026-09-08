## Why

`creator_activated_account` has never been emitted live. `DirectActivationView.post` calls
`self.activate(form)` directly, but django-registration sends `user_activated` from `form_valid`,
which that path bypasses — so the receiver in `survey/signals.py` never runs. The PostHog series
exists only as backfill with a proxy timestamp, and the "registration → activation 47%" reading on
the AARRR dashboard is an artefact: the database shows ~90% of creators activate (July 37/40,
August 56/59, September 17/19). Every Activation decision would be measured with a broken ruler.

## What Changes

- `DirectActivationView.post` sends `user_activated` after a successful `activate()`, exactly as
  the library's `form_valid` would, so every receiver of that signal runs on the real path.
- A test that drives the real activation POST and asserts the live event — the gap that let this go
  unnoticed since 2026-07-27.
- Operational: `backfill_posthog_events` is re-run once after deploy (idempotent UUIDs) to fill the
  August/September activations the live path missed; from then on the series is live.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `creator-funnel-events`: the activation event is emitted on the direct-activation path.

## Impact

`survey/views.py` (one call in `DirectActivationView.post`), `survey/tests.py`. No migration, no
template. The `account-activation` behaviour itself is unchanged — only the signal that was
supposed to accompany it.
