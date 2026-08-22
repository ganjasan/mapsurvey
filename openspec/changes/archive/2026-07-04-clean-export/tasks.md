## 1. Export Logic

- [x] 1.1 In `download_data`, parse `?include_all=1` param
- [x] 1.2 When not include_all, compute `excluded_session_ids` set: sessions where `is_deleted=True` OR `validation_status='not_approved'`
- [x] 1.3 Pass `excluded_session_ids` to `_export_survey_data`
- [x] 1.4 In `_export_survey_data` geo path: skip answers whose `survey_session_id` is in excluded set
- [x] 1.5 In `_export_survey_data` CSV path: skip sessions in excluded set
- [x] 1.6 Add `validation_status` column to CSV output
- [x] 1.7 Add `validation_status` and `session_id` to GeoJSON feature properties

## 2. UI

- [x] 2.1 Add "Export all (including excluded)" link in dashboard download area

## 3. Tests

- [x] 3.1 Test clean export excludes trashed sessions
- [x] 3.2 Test clean export excludes not_approved sessions
- [x] 3.3 Test `?include_all=1` includes all sessions
- [x] 3.4 Test CSV contains `validation_status` column
- [x] 3.5 Test GeoJSON features have `validation_status` and `session_id` properties
