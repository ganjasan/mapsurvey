# Tasks — restore-survey-version

## 1. Backend

- [x] 1.1 `clone_survey_for_draft(canonical, structure_source=None)`: sections,
      translations and questions clone from `structure_source or canonical`;
      header settings and collaborators keep coming from the canonical
- [x] 1.2 `editor_restore_version` (owner, POST, `version=vN`): resolve the archived
      family member (404 unknown), 400 unless canonical is published, 409 when a
      draft already exists; create the draft and redirect to its Build
- [x] 1.3 URL `editor/surveys/<uuid>/restore-version/`

## 2. UI

- [x] 2.1 Publishing widget Version section: list `get_version_history()` rows
      (vN · Closed) with a "Restore as draft" POST form, shown only when the
      canonical is published and has no draft copy

## 3. Verification

- [x] 3.1 Test: restored draft's structure equals the archived version (resurrected
      question comes back with its original code; v3-only question absent)
- [x] 3.2 Test: guards — 409 with an existing draft, 404 for an unknown version,
      403/redirect for a non-owner editor
- [x] 3.3 Test: publish of a restored draft (force) → new version number; the
      previously archived lineage reports as current again with its historical
      answers merged (no Archived badge)
- [x] 3.4 Test: widget shows Restore rows for owners on published surveys only
- [x] 3.5 Full `./run_tests.sh survey` green
