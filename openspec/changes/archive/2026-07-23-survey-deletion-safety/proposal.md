## Why

A production incident (July 2026, user holly@agnewbeck.com) showed that a survey owner can irreversibly destroy a month of work in 13 seconds: login → dashboard → Delete → confirm. The investigation succeeded only through incidental artifacts (orphaned `SurveyEvent` rows, 30-day Render request logs) — the platform itself keeps **no record** of who deleted what and when, and offers **no recovery path**. Deletion also orphans media files (the survey's cover image is still on disk in prod).

## What Changes

- **Soft-delete (trash) for surveys**: `delete_survey` moves the survey to trash (`deleted_at` timestamp) instead of hard-deleting. Trashed surveys disappear from the dashboard and public URLs but keep all sessions/answers. A Trash view lets the owner restore or permanently delete; auto-purge runs after 30 days. **BREAKING** for the `survey-deletion` spec: cascade deletion now happens at purge time, not delete time.
- **Audit log**: new append-only `AuditLog` model recording destructive and lifecycle operations (survey delete/restore/purge, status transitions, clear-test-data, publish/discard draft, password set/remove) with actor, action, target survey uuid+name, client IP, timestamp, and metadata JSON. Readable via Django admin.
- **Orphaned media cleanup**: permanent deletion (manual purge or auto-purge) removes the survey's cover image and answer image uploads from storage.
- **Backlog housekeeping**: create the missing `openspec/backlog/feature-audit-trail.md` referenced by INDEX.md #59 (dangling link) and mark it as promoted to this change.

## Capabilities

### New Capabilities
- `audit-log`: append-only recording of destructive/lifecycle editor operations with actor, target, IP and metadata; admin-readable, never user-editable.
- `survey-trash`: trash lifecycle for deleted surveys — listing, restore, permanent delete with media cleanup, 30-day auto-purge.

### Modified Capabilities
- `survey-deletion`: the delete endpoint becomes a soft-delete (move to trash); cascade removal of sessions/answers/sections/questions and media happens only at purge time; confirmation messaging changes accordingly.

## Impact

- **Models** (`survey/models.py`): new `AuditLog` model; `SurveyHeader.deleted_at` field; new migration(s).
- **Views** (`survey/views.py`, `survey/editor_views.py`): `delete_survey` rewritten as soft-delete; new trash/restore/purge endpoints; audit emit calls added to lifecycle endpoints (transition, password, publish/discard draft, clear test data).
- **Queries**: dashboard, public survey resolution (`resolve_survey`), and export must exclude trashed surveys (`deleted_at__isnull=True`).
- **Templates**: editor dashboard gains a Trash view/section; delete modal copy changes ("move to trash").
- **Background job**: auto-purge task (Celery beat — worker `mapsurvey-celery` already runs) purging surveys trashed >30 days ago, with media cleanup.
- **Admin** (`survey/admin.py`): read-only `AuditLog` admin.
- **Helpers**: client IP extraction reuses `survey.middleware.CloudflareIPMiddleware` conventions (via `survey/abuse.py` helper).
- **Tests** (`survey/tests.py`): trash lifecycle, exclusion from dashboard/public, restore, purge cascade + media cleanup, audit entries per operation.
