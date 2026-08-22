## Context

`download_data` and `_export_survey_data` currently iterate all sessions/answers without filtering. After #40, `SurveySession` has `validation_status` and `is_deleted` fields. The export needs to respect these.

Two export paths exist:
1. **Geo path**: iterates `question.answers()` → builds GeoJSON features
2. **CSV path**: iterates `survey.sessions()` → builds DataFrame rows

Both need filtering. The geo path goes through Answer objects (no direct session queryset), so filtering must happen by checking `answer.survey_session_id` against an excluded set.

## Goals / Non-Goals

**Goals:**
- Exclude trashed (`is_deleted=True`) and not-approved (`validation_status='not_approved'`) sessions from export by default
- `?include_all=1` param bypasses filtering for audit export
- `validation_status` column in CSV, `validation_status` + `session_id` in GeoJSON properties
- UI link for "Export all" in dashboard

**Non-Goals:**
- Filtering by arbitrary validation_status values (e.g., only approved)
- Per-question export filtering
- New export formats

## Decisions

### 1. Pre-compute excluded session IDs in `download_data`, pass to `_export_survey_data`

Compute a set of session PKs to exclude once, then pass it down. `_export_survey_data` checks membership for both geo answers and CSV sessions. This avoids modifying `Question.answers()` or `SurveyHeader.sessions()` model methods.

### 2. Filter in `_export_survey_data`, not in model methods

The model methods (`survey.sessions()`, `question.answers()`) are used elsewhere and have instance-level caching. Adding filter logic there would break other callers. Instead, filter at the export function level.
