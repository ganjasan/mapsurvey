# Restore an old survey version

## Why

Archived versions keep the full structure of every published revision, but there is no
way back: a creator who published v3 and regrets it can only view/export v2's data —
not make v2's questionnaire current again. The only path forward is manually rebuilding
the old structure by hand in a new draft, which is error-prone and loses lineage
continuity (hand-rebuilt questions get new codes).

## What Changes

- **Restore as draft** ("git revert, not reset"): a new draft copy whose sections and
  questions are cloned from a chosen archived version instead of the canonical. The
  standard draft flow then applies — review/edit, then Publish creates a new version
  (v4 ≡ v2's structure). History is append-only; no version is ever rewritten and no
  session moves.
- **Lineage continuity for free**: cloning preserves question codes, so questions that
  were removed in a later version come back with their original codes — their lineages
  become current again and the historical answers return from the Archived group into
  the main analytics automatically.
- **Version history in the publishing widget**: the Version section lists archived
  versions (vN · closed) with a "Restore as draft" action, available to owners when the
  survey is published and has no active draft (same rule as "Create a draft to edit").

## Capabilities

### New Capabilities

- `survey-version-restore`: `clone_survey_for_draft(canonical, structure_source=...)`,
  the restore endpoint, availability rules, and the version-history rows in the
  publishing widget.

## Impact

- `survey/versioning.py`: `clone_survey_for_draft` gains an optional `structure_source`
  (defaults to the canonical — existing behavior unchanged).
- `survey/editor_views.py`: `editor_restore_version` (owner, POST, `version=vN`).
- `survey/urls.py`: `editor/surveys/<uuid>/restore-version/`.
- `survey/templates/editor/partials/_publishing_widget.html`: version-history rows.
- Tests: restored draft structure equals the archived version; guards (draft exists,
  non-owner, bad version); publish-of-restored-draft returns an archived lineage to
  current with its historical answers.
