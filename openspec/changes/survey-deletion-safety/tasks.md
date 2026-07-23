## 1. Models & Migration

- [x] 1.1 Add `SurveyHeader.deleted_at` (nullable, indexed DateTimeField) + `is_trashed`/`purge_after` properties
- [x] 1.2 Add `AuditLog` model (created_at, actor SET_NULL, action choices, survey_uuid, survey_name, ip, metadata JSON) per design D4
- [x] 1.3 Generate single additive migration

## 2. Audit helper & call sites

- [x] 2.1 Create `survey/audit.py` with `audit(request, action, survey=None, **metadata)` — actor + `client_ip()` extraction, never raises (mirror `emit_event`)
- [x] 2.2 Add audit calls to `editor_survey_transition` (status_transition, clear_test_data with session count), `editor_survey_password` (password_set/password_remove/token_regenerate), `editor_publish_draft` (draft_publish), `editor_discard_draft` (draft_discard)
- [x] 2.3 Register read-only `AuditLog` admin (no add/change/delete)

## 3. Soft-delete & trash endpoints

- [x] 3.1 Add `allow_trashed=False` param to `survey_permission_required`; default filters `deleted_at__isnull=True`
- [x] 3.2 Rewrite `delete_survey` as soft-delete: set `deleted_at`, audit `survey_trash`, message mentions Trash recovery
- [x] 3.3 Extract shared `purge_survey(survey)` routine: media cleanup (cover + question images via storage API), handle Story FK, delete sessions/versions/draft copy/header — based on the old hard-delete cascade
- [x] 3.4 Add `restore_survey` endpoint (POST, owner, `allow_trashed=True`): clear `deleted_at`, audit `survey_restore`
- [x] 3.5 Add `purge_survey` endpoint (POST, owner, `allow_trashed=True`, reject non-trashed): call purge routine, audit `survey_purge`
- [x] 3.6 Exclude trashed from `resolve_survey`, dashboard query, public survey list, and data export

## 4. Trash UI

- [x] 4.1 Trash view/section in editor listing trashed surveys with trash date + days-until-purge, Restore and Delete-forever buttons (confirm modal on purge)
- [x] 4.2 Update delete confirm modal copy: "move to trash, restorable for 30 days"

## 5. Auto-purge job

- [x] 5.1 Management command `purge_trashed_surveys --days 30 --dry-run`: purge routine + `survey_auto_purge` audit entries (actor=None)
- [x] 5.2 Extract shared `purge_expired_surveys()` core into trash.py; command becomes a thin wrapper
- [x] 5.3 Internal endpoint `POST /internal/purge-trash/` gated by `PURGE_TASK_TOKEN` env (constant-time compare, 403 when unset), returns purge count JSON; tests for token auth + purge + disabled state
- [ ] 5.4 Render Cron Job (native runtime, curl) hitting the endpoint daily; `PURGE_TASK_TOKEN` env var on the web service

## 6. Tests (GIVEN/WHEN/THEN docstrings)

- [x] 6.1 Trash lifecycle: soft-delete preserves sessions/answers; dashboard/public list/public URL/editor endpoints exclude trashed (404)
- [x] 6.2 Restore: returns to dashboard with original status, public URL works again
- [x] 6.3 Purge: cascade deletes data + versions, removes media files from storage, rejects non-trashed target
- [x] 6.4 Auto-purge command: purges >30d, keeps <30d, writes auto-purge audit rows; --dry-run touches nothing
- [x] 6.5 Audit: entries written for trash/restore/purge/transition/clear_test_data/password ops; survive purge; helper swallows exceptions
- [x] 6.6 Run full suite `./run_tests.sh survey`, fix regressions (existing deletion tests will need updating)

## 7. Backlog & deploy housekeeping

- [x] 7.1 Create `openspec/backlog/feature-audit-trail.md` (fix dangling INDEX #59), note promotion of the operations-audit slice into this change
- [x] 7.2 Deploy note in change: create Render Cron Job running `python manage.py purge_trashed_surveys` daily (post-merge step)
