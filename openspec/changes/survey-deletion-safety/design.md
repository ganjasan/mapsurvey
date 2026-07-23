## Context

`delete_survey` (`survey/views.py:1079`) hard-deletes a survey, its archived versions, and all sessions/answers in one POST guarded only by a JS confirm modal. There is no audit trail of any editor operation (the only logs are `AbuseEvent` for registration and `django_admin_log` for admin actions). Media files (`SurveyHeader.cover_image`, `Question.image`) are never removed from storage, so deletion also leaks orphaned files.

Relevant existing machinery:
- `survey_permission_required` decorator (`survey/permissions.py:108`) resolves the survey by UUID for **every** editor endpoint and attaches `request.survey`.
- `resolve_survey` (`survey/views.py:217`) is the single public-URL resolution point.
- `client_ip(request)` helper in `survey/abuse.py` (Cloudflare-aware).
- `emit_event` (`survey/events.py`) — established "never raise from instrumentation" pattern.
- Celery worker runs on Render (`mapsurvey-celery`), but **no beat scheduler** is deployed.

## Goals / Non-Goals

**Goals:**
- No survey data is irreversibly destroyed by a single user action; a 30-day recovery window exists.
- Every destructive/lifecycle editor operation leaves an append-only audit record that survives the deletion of its target.
- Permanent deletion cleans up media files for both local-disk and S3 storage.

**Non-Goals:**
- Full edit-history/versioned undo of survey content (backlog #59 remains open for field-level history).
- Auditing read operations or respondent actions (covered by `SurveyEvent`).
- Trash for individual sections/questions/sessions (session deletion via analytics panel stays as-is).
- A user-facing audit log UI (admin-only for now).

## Decisions

**D1 — Soft-delete via `deleted_at` timestamp, not a lifecycle status.**
`SurveyHeader.deleted_at` (nullable `DateTimeField`, indexed). Trash state is orthogonal to `status`: restoring returns the survey exactly as it was (a published survey stays published). Adding a `deleted` status to `VALID_TRANSITIONS` would destroy the prior status and entangle two independent state machines. `is_trashed` property; `purge_after` computed as `deleted_at + 30 days`.

**D2 — Explicit exclusion at the three resolution points, no default-manager override.**
Overriding `SurveyHeader.objects` to hide trashed rows would silently affect admin, migrations, versioning internals, and serialization — too much magic for a safety feature. Instead:
- `survey_permission_required` gains `allow_trashed=False`; the default filters `deleted_at__isnull=True`, covering **all** editor endpoints at once. Trash endpoints (restore/purge) opt in with `allow_trashed=True`.
- `resolve_survey` excludes trashed → public URLs 404.
- Dashboard and public-list queries add the filter explicitly.

**D3 — Trash covers the canonical survey and its satellites.**
`delete_survey` sets `deleted_at` on the canonical header only; archived versions and a live draft copy are unreachable without the canonical and follow it implicitly. Restore clears the single timestamp. Purge reuses the current hard-delete cascade (sessions of canonical + archived versions + draft copy, then headers) plus media cleanup.

**D4 — `AuditLog` stores identity, not FKs to the target.**
Columns: `created_at`, `actor` (FK user, `SET_NULL`), `action` (choices), `survey_uuid` (plain `UUIDField`), `survey_name` (`CharField`), `ip` (`GenericIPAddressField`, null), `metadata` (`JSONField`). No FK to `SurveyHeader` — the record must survive the purge of its target. Actions: `survey_trash`, `survey_restore`, `survey_purge`, `survey_auto_purge`, `status_transition`, `clear_test_data`, `draft_publish`, `draft_discard`, `password_set`, `password_remove`, `token_regenerate`. Admin registration is read-only (`has_add/change/delete_permission → False`).

**D5 — Explicit `audit(request, action, survey, **metadata)` calls, not signals.**
Helper in new `survey/audit.py`, mirroring `emit_event`: extracts actor from `request.user`, IP via `client_ip(request)`, swallows all exceptions so auditing can never break the operation it observes. Signals were rejected: they cannot see the request (actor/IP) and hide the write sites.

**D6 — Auto-purge as a management command, scheduled externally.**
`manage.py purge_trashed_surveys [--days 30] [--dry-run]`. No Celery beat is deployed; adding a beat process for one job is operational overhead, and Render Cron Jobs already fit (run `python manage.py purge_trashed_surveys`). The command writes `survey_auto_purge` audit entries with `actor=None`. Manual purge from the Trash UI shares the same purge routine.

**D7 — Media cleanup through the Django storage API only.**
On purge: `cover_image.delete(save=False)` and each `Question.image.delete(save=False)` before the DB cascade. Works identically for local disk and S3 (`USE_S3`). No path arithmetic, no `os.remove`.

## Risks / Trade-offs

- [Unfiltered access path shows a trashed survey] → the permission decorator covers every editor endpoint centrally; `resolve_survey` covers every public endpoint; tests assert 404/exclusion for dashboard, public list, direct URL, and export.
- [Auto-purge destroys data silently] → 30-day window surfaced in the Trash UI ("purges in N days"), audit entry per purge, `--dry-run` for operators.
- [Cron not configured after deploy → trash grows unbounded] → deploy checklist item in tasks.md; command is idempotent so a late first run is harmless.
- [Trashed survey still referenced by a public `Story`] → story pages resolve their own survey FK; purge cascade will fail on `PROTECT`? No — `Story.survey` is a plain FK; verify cascade behavior in implementation and delete/unlink stories of purged surveys explicitly.
- [Name collision on restore] → `name` is not globally unique (per-user uniqueness enforced in forms only), so restore cannot hard-fail; acceptable.

## Migration Plan

1. Single additive migration: `SurveyHeader.deleted_at` + `AuditLog` table. Zero-downtime, no data migration.
2. Deploy code; existing surveys are unaffected (`deleted_at IS NULL`).
3. Create Render Cron Job for `purge_trashed_surveys` (daily).
4. Rollback: revert code; the extra column/table are inert.

## Open Questions

- None blocking. (Story/trashed-survey interaction resolved during implementation per Risks.)
