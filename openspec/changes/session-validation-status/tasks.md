## 1. Model and Migration

- [x] 1.1 Add `VALIDATION_STATUS_CHOICES` tuple to `survey/models.py` at module level (after `INPUT_TYPE_CHOICES`)
- [x] 1.2 Add `SurveySessionQuerySet` class with `active()` and `deleted()` methods
- [x] 1.3 Add `SurveySessionManager` using `SurveySessionQuerySet.as_manager()` pattern
- [x] 1.4 Add three fields to `SurveySession`: `validation_status` (CharField, max_length=15, choices, default='', db_index), `is_deleted` (BooleanField, default=False, db_index), `deleted_at` (DateTimeField, null, blank)
- [x] 1.5 Set `objects = SurveySessionManager()` on `SurveySession`
- [x] 1.6 Create migration `0024_session_validation_status.py`
- [x] 1.7 Run `python manage.py migrate` and verify

## 2. Service Layer

- [x] 2.1 Add `include_deleted` parameter to `SurveyAnalyticsService.__init__`; store `self.base_qs` using `SurveySession.objects.active().filter(survey=survey)` or unfiltered
- [x] 2.2 Replace all `SurveySession.objects.filter(survey=self.survey)` calls in `SurveyAnalyticsService` with `self.base_qs` (get_overview, get_session_hours, get_hourly_sessions, get_table_page — ~7 call sites)
- [x] 2.3 Add `.filter(survey_session__is_deleted=False)` to `get_geo_feature_collection()` Answer queryset
- [x] 2.4 Add `.filter(survey_session__is_deleted=False)` to `get_answer_matrix()` Answer querysets
- [x] 2.5 Add `validation_status` system column at index 1 in `get_table_page()` system_cols
- [x] 2.6 Add `show_trash` parameter to `get_table_page()`; when True, override queryset to `SurveySession.objects.deleted().filter(survey=self.survey)`
- [x] 2.7 Add `validation_status` and `is_deleted` keys to row dicts in `get_table_page()`
- [x] 2.8 Update `matches_search` in `get_table_page()` to include `validation_status` in system col check
- [x] 2.9 Add `SessionValidationService` class with methods: `set_status()`, `trash()`, `restore()`, `hard_delete()`

## 3. Views and URLs

- [x] 3.1 Parse `?trash=1` in `analytics_table` view; pass `show_trash` to `get_table_page()` and template context; pass `include_deleted=show_trash` to `SurveyAnalyticsService`
- [x] 3.2 Add `analytics_session_set_status` view: `@require_POST`, `@survey_permission_required('editor')`, validates status, calls `SessionValidationService.set_status()`
- [x] 3.3 Add `analytics_session_trash` view: soft-deletes session via `SessionValidationService.trash()`
- [x] 3.4 Add `analytics_session_restore` view: restores session via `SessionValidationService.restore()`
- [x] 3.5 Add `analytics_session_hard_delete` view: permanently deletes trashed session via `SessionValidationService.hard_delete()`
- [x] 3.6 Add 4 URL patterns to `survey/urls.py` under analytics namespace

## 4. Templates

- [x] 4.1 Add trash toggle button and `show_trash` hidden input to `analytics_table.html` toolbar and state form
- [x] 4.2 Add select-all checkbox `<th>` in header and per-row checkbox `<td>` in body
- [x] 4.3 Add `validation_status` column rendering: inline `<select>` with 4 options, color-coded border, disabled when trashed
- [x] 4.4 Add row action buttons: trash icon (normal rows), restore + hard-delete icons (trashed rows)
- [x] 4.5 Style trashed rows with `table-secondary` class
- [x] 4.6 Add inline JS: `setSessionStatus()`, `toggleShowTrash()`, `toggleSelectAll()`
- [x] 4.7 Add session action JS functions to `analytics_dashboard.html`: `trashSession()`, `restoreSession()`, `hardDeleteSession()`, `_sessionAction()`
- [x] 4.8 Update `analytics_session_detail.html`: validation status badge + trash/restore/hard-delete buttons in header
- [x] 4.9 Add `loadTable()` integration: include `trash` param from hidden form in table URL; `show_trash` state in `#table-state-form`

## 5. Serialization

- [x] 5.1 Add `validation_status` and `is_deleted` to `serialize_sessions()` output in `survey/serialization.py`

## 6. Tests

- [x] 6.1 Test `SurveySession` field defaults: `validation_status=''`, `is_deleted=False`, `deleted_at=None`
- [x] 6.2 Test `SurveySession.objects.active()` excludes `is_deleted=True` sessions
- [x] 6.3 Test `SurveySession.objects.deleted()` returns only `is_deleted=True` sessions
- [x] 6.4 Test `SessionValidationService.set_status()` with valid and invalid values
- [x] 6.5 Test `SessionValidationService.trash()` sets `is_deleted=True` and `deleted_at`
- [x] 6.6 Test `SessionValidationService.restore()` clears `is_deleted` and `deleted_at`
- [x] 6.7 Test `SessionValidationService.hard_delete()` removes session from DB
- [x] 6.8 Test `get_overview()` excludes trashed sessions from total count
- [x] 6.9 Test `get_table_page(show_trash=False)` excludes trashed sessions
- [x] 6.10 Test `get_table_page(show_trash=True)` returns only trashed sessions
- [x] 6.11 Test `get_geo_feature_collection()` excludes geo answers from trashed sessions
- [x] 6.12 Test `analytics_session_set_status` endpoint: valid status returns 204, invalid returns 400
- [x] 6.13 Test `analytics_session_trash` endpoint: returns 204, session becomes `is_deleted=True`
- [x] 6.14 Test `analytics_session_restore` endpoint: returns 204, session becomes `is_deleted=False`
- [x] 6.15 Test `analytics_session_hard_delete` endpoint: returns 204, session gone from DB
- [x] 6.16 Test viewer role cannot call mutation endpoints (403)
- [x] 6.17 Test `analytics_table` view with `?trash=1` returns trashed sessions only
