## Why

The `download_data` view exports ALL survey sessions regardless of moderation status. After #40 (Session Validation Status), researchers can mark sessions as "Not approved" and trash junk responses — but the export still includes them. Researchers must manually filter the CSV/GeoJSON after download, defeating the purpose of in-platform moderation.

## What Changes

- `download_data` excludes trashed and "not approved" sessions by default
- New `?include_all=1` parameter exports everything (for audit purposes)
- `validation_status` added as a column in CSV export and as a property in GeoJSON features
- `session_id` added to GeoJSON feature properties
- Dashboard UI gets "Export all (including excluded)" link alongside the existing Download button

## Capabilities

### Modified Capabilities
- `download_data`: Respects session moderation state; clean export by default, full export via param
- `_export_survey_data`: Accepts excluded session IDs set for filtering both geo and CSV paths

## Impact

- `survey/views.py` — `download_data` and `_export_survey_data` modified
- `survey/templates/editor/editor.html` — "Export all" link in dashboard download area
- `survey/tests.py` — tests for clean vs full export
