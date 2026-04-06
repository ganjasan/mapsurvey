## Why

After collecting survey responses, researchers need to review and moderate their data before analysis or export. Currently there's no way to mark sessions as approved/rejected or remove junk responses — the analytics dashboard and export include everything. Researchers must download raw data and clean it in QGIS/Excel, losing the map+table context that Mapsurvey provides.

This is the second task in the data-management epic (#40), building on the attribute table (#39). It adds the foundational moderation layer that #41 (Clean Export), #42 (Bulk Operations), and #43 (Auto-Validation) will build upon.

## What Changes

- Add `validation_status` field to `SurveySession` with 4 values: no status, approved, not approved, on hold
- Add soft-delete (trash) with `is_deleted` + `deleted_at`, orthogonal to validation status
- Validation status column in the attribute table (2nd system column, after #ID) with inline dropdown
- Trashed sessions excluded from all analytics queries (overview, hourly, geo, stats, answer matrix)
- Table hides trashed sessions by default; "Show trash" toggle reveals them
- Trash, restore, and hard delete actions per session row
- Session detail modal shows validation badge and trash/restore actions
- Checkbox selector per row + select/deselect all (UI preparation for future bulk operations #42)

## Capabilities

### New Capabilities
- `session-validation-status`: 4-state validation workflow (no status / approved / not approved / on hold) with inline status change in attribute table
- `session-soft-delete`: Trash/restore/hard-delete sessions with soft-delete semantics; trashed sessions excluded from analytics

### Modified Capabilities
- `SurveyAnalyticsService`: Custom QuerySet with `active()`/`deleted()` scoping; `base_qs` pattern excludes trashed sessions from all analytics methods
- `analytics_table`: New validation column, checkbox column, trash toggle, row-level actions

## Impact

- `survey/models.py` — `SurveySessionQuerySet`, `SurveySessionManager`, 3 new fields + choices constant
- `survey/analytics.py` — `base_qs` in `SurveyAnalyticsService.__init__`, `SessionValidationService` class, validation column in `get_table_page()`
- `survey/analytics_views.py` — `show_trash` param, 4 new HTMX endpoints
- `survey/urls.py` — 4 new URL patterns
- `survey/templates/editor/partials/analytics_table.html` — validation column, checkbox column, trash toggle, action buttons, JS
- `survey/templates/editor/partials/analytics_session_detail.html` — status badge, trash/restore buttons
- `survey/templates/editor/analytics_dashboard.html` — session action JS functions
- `survey/serialization.py` — `validation_status` in session serialization
- Migration 0024
