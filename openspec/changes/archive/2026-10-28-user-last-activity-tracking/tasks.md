# Tasks — user last-activity tracking

## 1. Model + migration

- [x] Add `UserActivity` model in `survey/models.py` (OneToOne → `settings.AUTH_USER_MODEL`,
      `on_delete=CASCADE`, `related_name='activity'`; `last_activity = DateTimeField(db_index=True)`).
- [x] Generate migration `survey/migrations/0035_useractivity.py`.

## 2. Middleware

- [x] Add `LastActivityMiddleware` to `survey/middleware.py`: on
      `request.user.is_authenticated`, cache-gated throttle (key
      `last_activity_seen:{uid}`, timeout `LAST_ACTIVITY_THROTTLE_SECONDS`,
      default 300), `update_or_create` the row, swallow write errors.
- [x] Register it in `mapsurvey/settings.py` MIDDLEWARE, immediately after
      `AuthenticationMiddleware`.
- [x] Add `LAST_ACTIVITY_THROTTLE_SECONDS` setting (default 300).

## 3. Funnel dashboard

- [x] In `survey/funnel.py::active_user_metrics`, build a `last_activity` map from
      `UserActivity` and include it in `creator_acts` (returned) and `live`
      (active windows), keeping existing signals as fallbacks.

## 4. Tests (GIVEN/WHEN/THEN)

- [x] Middleware sets `last_activity` for an authenticated request.
- [x] Anonymous request creates/updates nothing.
- [x] Second request within the throttle window does not re-write; after the
      window it writes again.
- [x] Write failure does not break the request.
- [x] `active_user_metrics` counts a user as returned/active from `last_activity`
      alone (unchanged `last_login`, no parent-survey save).
- [x] User without a `UserActivity` row keeps prior classification.

## 5. Verify

- [x] `openspec validate user-last-activity-tracking`.
- [x] Run `./run_tests.sh survey` (PostGIS up) for the affected tests.
