## Context

The attribute table (#39) is complete on `feature/data-management` branch. It shows all survey sessions in a paginated table with per-column search, sort, hide/freeze, and FilterManager integration. The table is an HTMX partial (`analytics_table.html`) loaded lazily into the analytics dashboard.

`SurveySession` currently has only 4 fields: `survey` (FK PROTECT), `start_datetime`, `end_datetime`, `language`. All analytics queries in `SurveyAnalyticsService` use unfiltered `SurveySession.objects.filter(survey=self.survey)`.

## Goals / Non-Goals

**Goals:**
- 4-state validation status (no status, approved, not approved, on hold) changeable via inline dropdown in table
- Soft-delete (trash) orthogonal to validation status, with restore and hard delete
- Trashed sessions invisible to all analytics (overview counts, hourly charts, geo map, stats, answer matrix)
- "Show trash" toggle to view and manage trashed sessions
- Session detail modal shows status and trash/restore actions
- Checkbox per row + select/deselect all (UI prep for #42 Bulk Operations)

**Non-Goals:**
- Bulk action toolbar (deferred to #42)
- Export filtering by status (deferred to #41)
- Audit trail / who changed what (deferred to #53)
- Validation status filtering in analytics charts/map (depends on FilterManager extension)

## Decisions

### 1. Custom QuerySet with `active()`/`deleted()` on SurveySession

Add `SurveySessionQuerySet` with named scopes and `SurveySessionManager`. The default manager stays unfiltered (views need to fetch trashed sessions for restore/hard-delete). `SurveyAnalyticsService.__init__` stores `base_qs = SurveySession.objects.active().filter(survey=survey)` by default, or unfiltered when `include_deleted=True`.

**Alternative considered**: `_live_sessions()` helper method per call site. Rejected — with 11 remaining epic tasks all needing session filtering, a central QuerySet abstraction is more maintainable.

### 2. Trash as separate `is_deleted` boolean, orthogonal to validation_status

A session can be "Approved" and later trashed (e.g., discovered duplicate after approval). Two separate fields: `is_deleted` BooleanField + `deleted_at` DateTimeField. The validation status is preserved when trashing and restored when untrashing.

**Alternative considered**: Trash as a 5th status value. Rejected — loses the original validation status when trashing.

### 3. `SessionValidationService` for mutation logic

All writes to `validation_status`, `is_deleted`, `deleted_at` go through `SessionValidationService` methods. Views call service methods, never write fields directly. This encapsulates validation logic and provides a single seam for future audit trail integration (#53).

### 4. Inline `<select>` for status, `fetch()` for mutations

Status changes use an inline `<select>` in the table cell. On change, a `fetch()` POST fires to the server. No full table reload — the dropdown already shows the new value. Trash/restore/hard-delete use `fetch()` + `loadTable()` on success (row appears/disappears).

**Alternative considered**: HTMX `hx-post` on the `<select>`. Rejected — would require `hx-swap="none"` plus custom handling, and `fetch()` is simpler for fire-and-forget mutations where the UI is already updated client-side.

### 5. `show_trash` as URL param with hidden form state

The "Show trash" toggle sets `?trash=1` in the table URL. The hidden `#table-state-form` carries this state across paginations and sorts. When in trash mode, FilterManager choice filters are ignored (their session IDs come from `answer_matrix` which only contains active sessions).

### 6. Session action JS functions in `analytics_dashboard.html`

`trashSession()`, `restoreSession()`, `hardDeleteSession()`, `_sessionAction()` are defined in the dashboard's main `<script>` block (not in the table partial). This ensures they're available when the session detail modal is opened from the geo map tab before the table has loaded.

### 7. No changes to `_stats_*` methods for now

The per-question stat methods (`_stats_choices`, `_stats_number`, `_stats_text`, `_stats_geo`) query `Answer` by question only. Adding `survey_session__is_deleted=False` to each would add JOINs. Accepted trade-off: stats may show slightly inflated counts when sessions are trashed but not hard-deleted. These methods will gain `session_ids` filtering in a future task.

### 8. `get_geo_feature_collection()` and `get_answer_matrix()` filter deleted sessions

These query `Answer` directly (not through `base_qs`). Add `survey_session__is_deleted=False` filter. This is critical — geo answers from trashed sessions must not appear on the analytics map, and the answer matrix must not include trashed session IDs for FilterManager.

## Risks / Trade-offs

- **Stats inflation** — `_stats_*` methods count answers from trashed sessions. Acceptable for v1; fix when stats gain session_ids filtering.
- **No undo on hard delete** — confirmed as acceptable; editor role sufficient per user decision.
- **Checkbox column without bulk toolbar** — UI-only prep for #42. Selecting rows does nothing yet.
- **Reserved section names** — no new reserved names; all new URLs are under `/analytics/sessions/`.
