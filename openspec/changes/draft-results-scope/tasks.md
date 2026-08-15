# Tasks

## 1. Draft-aware scope (`survey/versioning.py`)

- [x] 1.1 `canonical_of()` falls back to `published_version`, so a draft copy resolves to its
      canonical. Updated the docstring and the `family_ids` docstring, which stated the draft
      exclusion as intent.
- [x] 1.2 Added `draft_copy_of(survey)` — the family's draft copy or `None` — and
      `family_ids_with_draft(survey)` for the session-action guards.
- [x] 1.3 `resolve_version_scope()` accepts `draft` (constant `DRAFT_SCOPE`): a single-header scope
      over the draft copy when one exists, otherwise it falls through to the family (the `v99` rule).
- [x] 1.4 `lineage_map(survey, include_draft=False)` includes the draft's questions when asked; the
      `vN–vM` label ignores draft headers and a draft-only lineage is labelled `draft`.

## 2. Analytics (`survey/analytics.py`, `survey/analytics_views.py`)

- [x] 2.1 `version_choices()` appends a `Draft (test)` option when the family has a draft copy, and
      renders for a single-version survey that has one (it previously returned `[]`).
- [x] 2.2 `SurveyAnalyticsService._lineages` passes `include_draft=(scope.value == 'draft')`.
      `PerformanceAnalyticsService` needed no change — it resolves the same shared scope.
- [x] 2.3 Session-level views use `family_ids_with_draft`: session detail, answer edit, tags,
      status, trash, restore, hard delete, `_parse_bulk_session_ids`, and the text-answers partial's
      question lookup.
- [x] 2.4 `current_version` in the dashboard context is now the *resolved* scope value, so an
      unresolvable parameter cannot leave the picker disagreeing with the numbers below it.

## 3. Export (`survey/views.py`)

- [x] 3.1 No change needed: `download_data` → `_get_version_surveys` → the shared resolver, so a
      draft uuid exports the family and `version=draft` exports the draft with unprefixed
      filenames. Covered by a test rather than left to inspection.

## 4. Discard (`survey/editor_views.py`)

- [x] 4.1 `editor_discard_draft` deletes the draft's sessions and the header in one
      `transaction.atomic()` block; the audit entry still names the canonical and is written first.

## 5. UI

- [x] 5.1 Version picker renders the `draft` option after a separator (`analytics_dashboard.html`).
- [x] 5.2 A draft's Results carries a line stating whose responses are shown — and, under the draft
      scope, that those test responses die with the draft.
- [x] 5.3 Dashboard export menu (`_survey_more_menu.html`) checked: a draft has no prefetched
      archived versions, so it renders the plain Download entries. No change.
- [x] 5.4 Out of the reported scope but the same misreading: the draft chip showed `Draft · v1`
      (the draft's placeholder `version_number`) on a survey whose current version is v5. It now
      shows `Draft → v6`, matching the number the publish dialog names.

## 6. Tests (`survey/tests.py`, GIVEN/WHEN/THEN)

- [x] 6.1 `DraftCopyResultsScopeTest`: `canonical_of(draft)` is the canonical; family ids exclude the
      draft; `family_ids_with_draft` includes it.
- [x] 6.2 A draft's default scope reports the canonical family's sessions and excludes its own test
      sessions (the 1839-vs-1 case); the canonical's Results is unaffected by the draft.
- [x] 6.3 `version=draft` reports the draft's sessions alone, from the draft and from the canonical;
      without a draft copy it falls back to the family.
- [x] 6.4 `version_choices` includes `draft` on a single-version survey with a draft, and returns
      `[]` when there is none.
- [x] 6.5 Lineage: a cloned question reports its draft answers under `version=draft`; a draft-only
      question appears; the published scope counts only published answers.
- [x] 6.6 Session actions accept a draft session (200) and still reject a foreign one (404).
- [x] 6.7 `test_discard_draft_with_test_sessions_succeeds` — redirect, not 500; draft, sessions and
      answers gone; a sibling test proves the canonical's sessions survive.
- [x] 6.8 Public results aggregates ignore draft test sessions.
- [x] 6.9 Export from a draft uuid resolves to the published family.

## 7. Verification

- [x] 7.1 `./run_tests.sh survey` — 1066 tests, OK (1 skipped).
- [x] 7.2 Manual, on the worktree's dev stand (port 8130) seeded with a v2 survey holding 8
      responses across v1+v2 and a draft previewed twice:
      - the draft's Results reports **8**, picker values `all v2 v1 draft`, banner "Responses of the
        published survey";
      - `?version=draft` on the draft **2**, with the "test responses" banner; the table partial
        agrees (2 results, 8 unfiltered);
      - `?version=draft` from the canonical also **2**; the canonical's default stays **8**;
      - export from the draft's uuid yields `v1_…csv` + `v2_…csv`, 8 data rows;
      - the pre-fix cause reproduced directly (`draft.delete()` → `ProtectedError`), then
        discard-draft over HTTP returned **302** to the canonical, and the picker lost its draft
        option;
      - a draft test session and a canonical session both open from the draft's page (200), a
        foreign session id still 404s;
      - the draft chip reads `Draft → v3` on a canonical at v2.
- [x] 7.3 No backlog entry covers either bug (both came in from production today), so nothing to
      strike in `openspec/backlog/INDEX.md`.
