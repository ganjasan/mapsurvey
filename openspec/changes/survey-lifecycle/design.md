## Context

`SurveyHeader` currently has two state-related fields: `visibility` (private/demo/public) controlling landing page display, and `is_archived` (bool) marking completed surveys. Neither field prevents public URL access — any survey is reachable at `/surveys/<uuid>/` regardless of settings. There is no draft concept, no password protection, and no way to test a survey with a limited audience before opening it to everyone.

The editor creates surveys that are immediately live. The public views (`survey_header`, `survey_section`, `survey_language_select`) call `resolve_survey()` and proceed without any status check.

## Goals / Non-Goals

**Goals:**
- Introduce a `status` field with five states and enforced transitions
- Block public access to draft surveys, gate testing surveys with password/token
- Provide password protection mechanism reusable for both testing and published states
- Give survey owners UI controls for state transitions in dashboard and editor
- Preserve backward compatibility for existing surveys (migrate to `published`)

**Non-Goals:**
- Survey versioning (draft-copy-of-published workflow) — deferred to a future change
- Per-respondent access codes — only shared password in this MVP
- State transition audit log / history tracking
- Automatic scheduling (publish at date X, close at date Y)
- Notification system for state changes

## Decisions

### 1. Lifecycle state as a CharField on SurveyHeader (not a separate model)

All existing state-like fields (`visibility`, `is_archived`, `thanks_html`) live directly on `SurveyHeader`. A separate `SurveyLifecycle` model would add join complexity with no benefit — lifecycle is 1:1 with the survey.

**Alternative considered**: Separate `SurveyState` model with history tracking. Rejected because audit trail is a non-goal, and the pattern doesn't match the existing codebase.

### 2. State machine logic as methods on SurveyHeader (not a service class)

Transition validation (`can_transition_to`) and business rules live as model methods. The transitions are simple enough (5 states, ~7 valid transitions) that a separate `SurveyLifecycleManager` service class would be over-engineering.

**Alternative considered**: Service class in `lifecycle.py`. Rejected because Django convention is "fat models", the logic is simple, and all data needed for validation is on the model instance.

### 3. Access control as a function, not a decorator

The existing public views call `resolve_survey(survey_slug)` internally. A `check_survey_access(request, survey)` function called after `resolve_survey()` is less invasive than a decorator that would need to also resolve the survey and refactor all views to use `request.survey`.

**Alternative considered**: `@public_survey_access_required` decorator that resolves survey and attaches to request. Rejected because it would require refactoring the signature and body of every public view.

### 4. Password stored as hash using Django's `make_password` / `check_password`

Reuses Django's battle-tested password hashing (PBKDF2 by default, timing-safe comparison). The `password_hash` field is `CharField(max_length=128)`, nullable. No plaintext ever stored.

**Alternative considered**: Custom hashing or separate password model. Rejected — Django's hashers are the standard approach.

### 5. Test token as auto-generated UUID on model

`test_token = UUIDField(default=uuid.uuid4)` provides 128 bits of entropy. Test URLs look like `/surveys/<uuid>/?token=<token-uuid>`. Token stored in session after first valid use to avoid re-checking on every page.

**Alternative considered**: Signed URLs (Django's `signing` module). Rejected because UUID token is simpler, doesn't expire implicitly, and the session caching pattern works well.

### 6. Session-based password/token persistence

After validating password or test token, store boolean in Django session (`survey_password_{survey_id}` / `test_access_{survey_id}`). This avoids re-entering password on every page of a multi-section survey.

### 7. Keep `visibility` and `is_archived` fields, sync on archive

`visibility` still controls landing page display independently of `status`. When transitioning to `archived`, set `is_archived=True` for backward compatibility with any code checking that field. The `status` field is the authoritative lifecycle state.

### 8. Landing page filtering: add status filter alongside visibility

The `index` view currently filters by `visibility__in=['demo', 'public']`. Add `.exclude(status='draft')` to also hide draft surveys. Closed/archived surveys with public visibility still show on landing but link to a "closed" message instead of the survey.

### 9. Transition validation rules

| From | To | Pre-conditions |
|---|---|---|
| draft | testing | Password must be set; at least one section with questions; head section exists |
| draft | published | At least one section with questions; head section exists |
| testing | draft | None (always allowed) |
| testing | published | None (option to clear test sessions) |
| published | closed | None |
| closed | published | None (reopen) |
| closed | archived | None |

Archived is a terminal state — no transitions out. If a survey needs to be reopened from archived, it should be exported and re-imported as a new survey.

### 10. Test data cleanup on Testing → Published

When transitioning from `testing` to `published`, the UI offers a checkbox "Delete test responses". If checked, all `SurveySession` objects for that survey are deleted (cascading to `Answer`). Simple approach — no `is_test` flag needed.

### 11. Password entry page as a standalone view

`/surveys/<slug>/password/` renders a form. On POST with correct password, sets session key and redirects to `/surveys/<slug>/`. This is a separate URL rather than inline in `survey_header` to keep the access control function clean (it returns a redirect response, not a rendered form).

**Alternative considered**: Rendering password form inline within `check_survey_access`. Rejected because it complicates the function's return type and mixes concerns.

## Risks / Trade-offs

**[Risk] Editing published surveys can break active respondent sessions** → Not addressed in this MVP. Versioning (deferred) will solve this. For now, survey owners should close the survey before making structural changes.

**[Risk] Password in URL token is visible in browser history and server logs** → The test token URL is intended for controlled sharing during testing. Document in UI that test links should not be shared publicly. Token is regenerated when re-entering testing state.

**[Risk] Session-based password auth doesn't survive session expiry** → Acceptable trade-off. Sessions default to 2 weeks in Django. Respondents filling out a survey in one sitting won't be affected.

**[Risk] Bulk-deleting test sessions is irreversible** → Mitigated by confirmation dialog in the UI. The "clear test data" checkbox is checked by default but can be unchecked.

**[Risk] `is_archived` and `status='archived'` could diverge** → Mitigated by always syncing `is_archived=True` when status transitions to `archived`. The `status` field is authoritative; `is_archived` exists only for backward compatibility.

## Migration Plan

1. **Schema migration**: Add `status` (default='draft'), `password_hash` (null), `test_token` (auto-generated) to `SurveyHeader`
2. **Data migration**: Set `status='published'` for all existing surveys (preserves current unrestricted access behavior); set `status='archived'` for surveys where `is_archived=True`
3. **Rollback**: Remove fields. No data loss since existing `visibility` and `is_archived` remain unchanged throughout.

## Open Questions

- Should closed surveys still appear on the landing page (linking to a "closed" message), or be hidden entirely? Current design: show with "closed" indicator.
- Should the password entry page show the survey name, or be generic? Current design: show survey name for usability.
