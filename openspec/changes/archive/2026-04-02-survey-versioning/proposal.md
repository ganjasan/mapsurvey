## Why

Published surveys are edited in-place — every change to a question, section, or choice immediately affects active respondents mid-session. This can break active sessions, cause data inconsistency, and lose answers. Survey versioning introduces a draft-copy workflow where the published survey is read-only, edits happen on a draft copy, and publishing a new version atomically archives the old structure (preserving all answers) while swapping in the new one. Respondents mid-survey continue on the old version (grace period), and data export supports per-version filtering.

## What Changes

- **BREAKING**: Published and closed surveys become read-only in the editor — all structural edits require creating a draft copy
- Add `canonical_survey` (self-FK), `version_number` (int), `is_canonical` (bool) fields to `SurveyHeader` for version tracking
- Add `published_version` (self-FK) to `SurveyHeader` for linking draft copies to their canonical survey
- **BREAKING**: Change `SurveySession.survey` FK from CASCADE to PROTECT — prevents accidental deletion of surveys with session data
- Add "Edit Published Survey" action that creates a draft copy with cloned structure (same question codes)
- Add "Publish Version" action that atomically archives old structure (moves sections via FK update), moves sessions to archive, and swaps in new structure from draft
- Add backward compatibility check before publish: blocks if questions with answers were deleted, changed type, or lost choice codes — unless owner force-publishes
- Add grace period: respondents mid-survey continue on the archived version's structure via their session FK
- Add version-aware data export: `download_data` supports `?version=v1|v2|latest|all`
- Add "Discard Draft" action that deletes the draft without affecting the published survey
- Public URL always resolves to the canonical survey; archived versions are invisible to respondents
- Editor shows version badge, read-only state, draft indicators, version history, and version-filtered download
- Serialization exports `version` field; import defaults to version 1; archived versions are not exported

## Capabilities

### New Capabilities
- `survey-versioning`: Draft-copy workflow for published surveys — create draft copy (same question codes), backward compatibility check, publish via atomic structure move (archive old + swap new), discard draft. Grace period for in-flight respondents. Version tracking. Version-aware data export.

### Modified Capabilities
- `survey-editor`: Published surveys become read-only; add "Edit Published Survey", "Publish Version", "Discard Draft" actions; show version/draft/read-only indicators; version history; version-filtered download UI
- `survey-serialization`: Export/import `version` field; archived versions excluded from export

## Impact

- **Models**: `SurveyHeader` gets 4 new fields (`canonical_survey`, `version_number`, `is_canonical`, `published_version`). `SurveySession.survey` FK changes to PROTECT. New model methods for version history and draft management.
- **Views**: `survey_section` gets session-based version routing. Editor gets 4 new endpoints (create-draft, publish-draft, discard-draft, check-compatibility). `download_data` gets version filtering. `resolve_survey` filters for canonical surveys. Structural editor endpoints get read-only guard.
- **Templates**: Editor shows read-only state for published surveys. Header shows version badge and draft indicator. New confirmation modals. Version history section. Version selector in download UI.
- **New file**: `survey/versioning.py` — clone, compatibility check, and publish logic.
- **Serialization**: Minor addition of `version` field to export/import.
- **Migrations**: 1 schema migration for new fields + FK change.
- **No URL changes for respondents**: Public URLs unaffected. Draft copies and archived versions use existing editor/access-control patterns.
