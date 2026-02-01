## Why

Survey definitions (structure, questions, options) are created manually through Django admin, making it time-consuming to recreate surveys on different instances or restore after data loss. Teams need to backup survey configurations and migrate them between environments (dev → staging → production). Survey administrators need a self-service way to export/import without SSH access.

## What Changes

- Add Web UI in `/editor/` dashboard for export/import surveys
- Add Django management commands `export_survey` and `import_survey` for CLI automation
- Export format: ZIP archive with mode parameter (`structure`, `data`, `full`)
- **Structure mode**: `survey.json` + question images
- **Data mode**: `responses.json` + geo files (replaces current download_data CSV/GeoJSON)
- **Full mode**: Complete backup - structure + responses + all media
- Import supports restoring both structure and responses with full ID remapping

## Capabilities

### New Capabilities

- `survey-serialization`: ZIP-based serialization format for complete survey definitions including all related models (sections, questions, options) with proper handling of foreign keys, hierarchical relationships, and media files

### Modified Capabilities

None - this is a new standalone feature that doesn't modify existing behavior.

## Impact

- **New files**:
  - `survey/management/commands/export_survey.py`
  - `survey/management/commands/import_survey.py`
  - `survey/serialization.py` (shared logic for CLI and Web)
- **Modified files**:
  - `survey/views.py` (add export/import views)
  - `survey/urls.py` (add routes)
  - `survey/templates/editor.html` (add UI buttons)
- **Dependencies**: No new dependencies (uses Python's zipfile, Django's built-in tools)
- **Database**: Read-only for export; creates new records for import
- **Storage**: Reads/writes to MEDIA_ROOT for image files
