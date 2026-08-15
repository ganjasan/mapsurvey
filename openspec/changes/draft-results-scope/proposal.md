## Why

A draft copy is invisible to the version family, and both consequences are creator-facing.

**Results go blank.** Opening Results on a draft copy of `demo_city_feedback` reports **1 result** —
a single empty test session from a preview — while the published survey holds **1839**. The scope is
built from `canonical_survey`, but a draft is linked through `published_version` instead
(`versioning.py:35`, `40`). `canonical_of(draft)` therefore returns the draft itself, the family is
`{draft}`, and every count, chart, map and violation on the page describes the draft's own preview
traffic. A creator who clicks "Go to draft" to edit a live survey sees their responses disappear.

**Discard returns 500.** `SurveySession.survey` is `PROTECT` (`models.py:140`), and
`editor_discard_draft` calls `survey.delete()` with the draft's test sessions still attached
(`editor_views.py:1447-1457`) → `ProtectedError`. `publish_draft` gets this right — it clears test
sessions before deleting the header (`versioning.py:459-461`) — discard never got the same line. Any
draft that has been previewed even once cannot be discarded; the only way out of the draft state is
to publish it.

Both come from the same fact: a draft owns test sessions, and nothing in the read path or the delete
path accounts for them.

## What Changes

- Version scope resolution follows `published_version`, so a draft copy resolves to its canonical's
  version family. The default scope on a draft's Results is the family — the full 1839 responses.
- The version picker gains a **Draft** option whenever the family has a draft copy. It is the only
  way to see the draft's own test sessions; `All versions` and `vN` never mix test traffic into real
  data. The picker now renders for a single-version survey that has a draft (it previously rendered
  only for multi-version surveys).
- Question lineages include the draft's questions under the draft scope, so a draft's test answers
  report against the same columns as the published ones.
- Session-level actions in analytics (open, edit, tag, status, trash, restore, hard delete) accept
  the draft's sessions, so a session visible under the Draft filter is also actionable.
- `editor_discard_draft` deletes the draft's test sessions before deleting the header, inside one
  transaction.
- The data export inherits the scope change through the shared resolver: downloading from a draft
  exports the published family, and `version=draft` exports the test sessions.

## Impact

- Affected specs: `draft-copy-results` (new), `draft-copy-lifecycle` (new)
- Affected code: `survey/versioning.py`, `survey/analytics.py`, `survey/analytics_views.py`,
  `survey/editor_views.py`, `survey/templates/editor/analytics_dashboard.html`
- No migration. `family_ids()` keeps its published-only meaning, so the public results page
  (`public_results.py:67`) still cannot publish draft test data.
