# Design — user last-activity tracking

## Context

`funnel.py::active_user_metrics` derives a creator's `activity_at` from
`last_login`, `Max(SurveyHeader.updated_at)`, and the latest response. The first
two under-count activity (see proposal). We need a signal that fires whenever a
logged-in user actually touches the app, without a schema change to the built-in
`auth_user` table and without a DB write on every request.

## Goals

- A truthful "user entered the system" timestamp per user, queryable across all
  users for the dashboard.
- Cheap: no write-per-request; no change to hot-path latency in a meaningful way.
- Non-destructive to existing metrics; forward-only (no backfill).

## Non-Goals

- Per-page or per-action analytics for creators (that is respondent-side
  `SurveyEvent`'s job; out of scope).
- Session-duration or engagement-depth tracking.
- Backfilling historical activity.

## Decisions

### 1. Storage: a dedicated `UserActivity` OneToOne model

The project uses Django's default `auth_user` (no `AUTH_USER_MODEL` override, no
profile model), so a column cannot be added to the user directly. Mirror the
existing `SignupAttribution` pattern: a `OneToOneField(settings.AUTH_USER_MODEL,
on_delete=CASCADE)` auxiliary model with an indexed `last_activity` datetime.

Rejected: putting `last_activity` on `SignupAttribution` — that model is
immutable first-touch acquisition data and only exists for post-launch signups;
mixing a mutable activity field there is semantically wrong and would miss older
users.

### 2. Update: throttled middleware

`LastActivityMiddleware` (in `survey/middleware.py`, registered right after
`AuthenticationMiddleware` so `request.user` is populated). On each request with
`request.user.is_authenticated`:

- Gate on the cache: key `last_activity_seen:{user_id}`. If present, do nothing
  (we already wrote within the throttle window).
- Otherwise `UserActivity.objects.update_or_create(user=..., defaults={'last_activity': now})`
  and set the cache key with `timeout = LAST_ACTIVITY_THROTTLE_SECONDS` (default
  300s).

This bounds writes to ~one per user per 5 minutes regardless of request volume.
The DB write is wrapped defensively so a failure never breaks the request. Cache
is already configured (used elsewhere); if the cache backend is unavailable the
middleware falls back to writing (fail-open toward correctness, matching the
ratelimit fail-open convention).

Rejected: signal on `user_logged_in` (that is just `last_login` again); writing
every request (write amplification); session-only storage (not queryable for the
dashboard across users).

### 3. Consume: fold into `active_user_metrics`

Add a `last_activity` map (`UserActivity` → `{user_id: last_activity}`) and
include it in both `creator_acts` (drives "returned") and `live` (drives active
windows). Order of signals becomes: `last_login`, `SurveyHeader.updated_at`,
`last_activity` for creator actions; plus latest response for liveness. Because
old users have no `UserActivity` row, the existing signals stay as fallbacks and
nobody is reclassified downward.

## Risks / Trade-offs

- **Write volume**: mitigated by the cache throttle. Worst case with a cold cache
  is one write per authenticated request until the key is set; acceptable and
  self-limiting.
- **Forward-only skew**: for a short window after deploy, "returned" still leans
  on `last_login`/`updated_at` for users who have not made a request yet. This is
  the same "rises from deploy onward" behavior as `SignupAttribution` and is
  acceptable.

## Migration Plan

Additive: new table only, no data migration. Deploy model + middleware together.
`last_activity` populates from first authenticated request post-deploy.
