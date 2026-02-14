## Why

Survey names have a global `unique=True` constraint, which means two different users cannot create surveys with the same name (e.g., "DEMO", "TEST"). This blocks multi-user registration — the first user to claim a name locks it out for everyone.

## What Changes

- **BREAKING**: Add `SurveyHeader.uuid` field (UUIDField, unique, auto-generated) as the primary identifier for URL routing
- **BREAKING**: Remove `unique=True` from `SurveyHeader.name` — names are no longer globally unique
- **BREAKING**: Switch all editor URLs from `/editor/surveys/<name>/` to `/editor/surveys/<uuid>/`
- **BREAKING**: Switch public survey URLs from `/surveys/<name>/` to `/surveys/<uuid>/` (with optional name-based fallback for backward compatibility)
- Update serialization export/import to work without global name uniqueness
- Update editor forms and views to look up surveys by UUID instead of name
- Update export/delete URLs to use UUID instead of name

## Capabilities

### New Capabilities
- `uuid-survey-identification`: Covers UUID field addition, URL routing changes (editor + public), survey lookup by UUID, and backward-compatible name-based fallback for public URLs

### Modified Capabilities
- `survey-serialization`: Import no longer checks global name uniqueness; data-only import matches survey by UUID or name
- `survey-editor`: Editor URLs change from `<name>` to `<uuid>`; form validation changes (per-user name uniqueness instead of global)
- `survey-deletion`: Delete URL changes from `<name>` to `<uuid>`

## Impact

- **Models**: `SurveyHeader` — new `uuid` field, remove `unique=True` from `name`
- **Migrations**: 2-3 migrations (add nullable uuid, populate existing, make non-null unique)
- **URLs**: All `survey/urls.py` routes change from `<str:survey_name>` to `<uuid:survey_uuid>` (editor) or `<str:survey_slug>` (public with dual lookup)
- **Views**: `views.py`, `editor_views.py` — all view functions update parameter and lookup logic
- **Templates**: Links referencing `survey.name` in URLs update to `survey.uuid`
- **Serialization**: `serialization.py` — import logic no longer rejects duplicate names
- **Management commands**: `export_survey` command may need UUID support
- **Tests**: Significant test updates for new URL patterns
