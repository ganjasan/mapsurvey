## Why

The funnel monitoring dashboard measures whether registered creators keep using
the platform ("returned", "active_7/30/90"). Today its only signal of a creator
*entering the system* is Django's `auth_user.last_login`, plus `SurveyHeader.updated_at`
as an edit proxy. Both under-count real activity:

- `last_login` updates **only on explicit authentication** (`login()`), not on
  activity under a live session cookie. A creator can work for weeks without it
  moving.
- `SurveyHeader.updated_at` (`auto_now=True`) moves only when the parent survey
  is saved (settings / status / map position / password). The core editor work —
  adding, editing, reordering, deleting sections and questions, choices, and
  translations — saves child rows and never touches the parent, so it is
  invisible to the metric.

Net effect: the dashboard **overstates dormant creators and understates
active/returned ones** — the exact "user is quietly building a survey" behavior
we most want to see is not counted. Confirmed on real leads (e.g. a user whose
`last_login` was 2026-06-17 but who created a new survey on 2026-07-10).

## What Changes

- Add a persisted per-user `last_activity` timestamp, updated on **any**
  authenticated request via middleware (throttled so it is at most one write per
  user per few minutes, not a write per request).
- Fold `last_activity` into the funnel `active_user_metrics` so "returned" and
  the active windows reflect genuine system entry, not just explicit logins or
  parent-survey saves.
- Forward-only: `last_activity` starts populating at deploy. Existing signals
  (`last_login`, `SurveyHeader.updated_at`, latest response) remain as fallbacks
  so historical users are not wrongly reclassified.

## Capabilities

### New Capabilities

- **user-activity-tracking**: record the last time each authenticated user
  interacted with the system, and expose it to the funnel dashboard as the
  primary "creator activity" signal.

### Modified Capabilities

- **creator-funnel-dashboard** (from `funnel-monitoring`): the "returned" and
  "active_N" metrics additionally consider `last_activity`.

## Impact

- New model `UserActivity` (OneToOne → User) + one migration.
- New `LastActivityMiddleware` in `survey/middleware.py`, registered in settings.
- `survey/funnel.py::active_user_metrics` reads `last_activity`.
- Adds at most one lightweight DB write per active user per throttle window
  (default 5 min); anonymous requests do nothing.
