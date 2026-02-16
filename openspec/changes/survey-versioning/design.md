## Context

Published surveys are edited in-place. Every change to a question, section, or choice in the editor immediately affects the live survey that respondents are filling out. This means:
- Adding/removing questions can break active sessions (answers reference questions that no longer exist or have changed type)
- Changing choices invalidates already-submitted `selected_choices` codes
- Reordering sections breaks the linked-list navigation for respondents mid-survey

The lifecycle feature (draft → testing → published → closed → archived) controls _when_ a survey is accessible but doesn't protect _what_ respondents see from changing under them.

## Goals / Non-Goals

**Goals:**
- **Published surveys are read-only** — all structural edits go through the draft-copy workflow
- Provide an atomic "publish new version" action that swaps the structure safely
- **Preserve old questions** — old answers keep valid FK references to their original questions
- **Grace period** — respondents mid-survey continue seeing the version they started on
- **Version-aware data export** — download_data supports filtering by version (v1, v2, all)
- Track version numbers for auditing which version collected which responses
- Keep the mental model simple: one draft copy at a time, owner-controlled

**Non-Goals:**
- Version history browser (viewing/restoring arbitrary past versions)
- Concurrent draft copies (multiple editors preparing different versions simultaneously)
- Per-question or per-section diff view between versions
- Automatic merging of changes
- Response migration between versions

## Decisions

### 1. Each published version becomes a separate SurveyHeader (archived version)

When a new version is published, the old structure (sections, questions, translations) is **moved** to a new `SurveyHeader` (the "archived version"). This is done via FK updates (`SurveySection.survey_header = archived_version`), not by cloning. Answers keep their FK to the exact same Question objects — zero data loss, zero FK breakage.

The canonical survey always holds the latest structure. Archived versions are frozen and invisible to respondents (they have `status='closed'` and the access control already blocks them).

**New fields on SurveyHeader:**
- `canonical_survey` (self-FK, nullable) — points to the canonical survey. NULL for canonical surveys themselves.
- `version_number` (PositiveIntegerField, default=1) — version counter
- `is_canonical` (BooleanField, default=True) — True for the canonical (URL-bearing) survey, False for archived versions

**Why move sections instead of cloning?** Cloning questions would require either remapping Answer FKs (risky bulk update) or changing Answer.question to SET_NULL (data loss). Moving the section FK is a single UPDATE query that preserves the entire question → answer chain intact.

### 2. Respondents interact with the canonical survey, sessions track versions

Public URLs always resolve to the canonical survey. When a respondent starts a new session:
- `SurveySession.survey` points to the canonical survey (which has the latest structure)

When a new version is published (old structure moved to archive):
- Active sessions are moved to the archived version: `SurveySession.objects.filter(survey=canonical, end_datetime__isnull=True).update(survey=archived_version)`
- The `survey_section` view checks `session.survey` to determine which version's sections to show
- This is the **grace period**: old respondents continue on old structure, new respondents get new structure

**Session routing in `survey_section`:**
```python
if session exists:
    survey_for_sections = session.survey  # may be archived version
else:
    create session against canonical  # always latest
```

### 3. Published surveys are read-only in the editor (always, not just with active draft)

Once a survey reaches `published` or `closed` status, all structural edits (section CRUD, question CRUD, reorder, choices, translations) are blocked. The only way to modify structure is through the draft-copy workflow.

Settings that don't affect survey structure (name, visibility, redirect_url) can still be changed.

Testing status surveys remain fully editable — they haven't collected real responses yet.

### 4. Draft copy as a separate SurveyHeader with `published_version` FK (unchanged from before)

When the owner clicks "Edit Published Survey", the system clones the published survey's structure into a new `SurveyHeader` with `status='draft'` and `published_version` pointing to the canonical.

**Clone uses the same question codes.** There is no DB-level unique constraint on `Question.code` — it's only enforced at application level during import. For draft copies, we skip collision checks and use identical codes. This makes the compatibility check trivial (match by code).

### 5. Publish draft = archive old + move new (no cloning at publish time)

When publishing a draft copy, in a single `transaction.atomic()`:

1. **Run backward compatibility check** (abort if breaking changes and not force)
2. **Create archived version** — new `SurveyHeader` with `canonical_survey=canonical`, `is_canonical=False`, `version_number=canonical.version_number`, `status='closed'`
3. **Move old sections** — `SurveySection.objects.filter(survey_header=canonical).update(survey_header=archived_version)`
   - This moves questions, translations, and preserves all Answer FKs automatically
4. **Move active sessions** — `SurveySession.objects.filter(survey=canonical, end_datetime__isnull=True).update(survey=archived_version)`
   - Completed sessions (with `end_datetime`) also move — they reference old questions
5. **Move draft's sections to canonical** — `SurveySection.objects.filter(survey_header=draft).update(survey_header=canonical)`
6. **Copy settings** from draft to canonical (languages, visibility, redirect_url, thanks_html)
7. **Increment version** — `canonical.version_number += 1`
8. **Delete draft copy** — just the SurveyHeader (sections already moved out, so no cascade)
9. **Copy collaborators** from draft back to canonical (if any were added)

This is efficient: mostly FK updates, no serialization at publish time.

### 6. Clone function for draft creation

`clone_survey_for_draft(canonical)` in `survey/versioning.py`:
1. Create new `SurveyHeader` with `status='draft'`, `published_version=canonical`
2. For each section in canonical: create a copy with same `name`, `code`, `title`, linked list structure
3. For each question: create a copy with **same code**, same properties, choices, translations
4. Copy collaborators
5. Name: `[draft] <original_name>` (truncated to 45 chars)

Uses direct model operations, not serialization (to preserve codes without collision avoidance).

### 7. Backward compatibility check before publish

`check_draft_compatibility(draft, canonical)` compares question codes between draft and canonical:
- **Deleted question with answers**: code in canonical, not in draft, has `Answer` rows → breaking
- **Changed input_type with answers**: same code, different input_type, has answers → breaking
- **Removed choice codes with answers**: same code, missing choice codes in `Answer.selected_choices` → breaking

Returns list of breaking issues. Publish blocked unless `force=True`.

### 8. SurveySession.survey FK changes from CASCADE to PROTECT

This prevents accidental deletion of archived versions that have sessions. To delete an archived version, sessions must be cleaned up first.

### 9. Version-aware data export

`download_data` accepts `?version=v1|v2|latest|all`:
- `latest` → query canonical's sessions/questions
- `v1` → query archived version with version_number=1
- `all` → query canonical + all archived versions, prefix filenames with `v1_`, `v2_`, etc.

Each archived version is a complete world: its own SurveyHeader with sections, questions, sessions, and answers. Querying is straightforward — just change which SurveyHeader to query.

### 10. Archived versions hidden from dashboard and public

- Archived versions have `is_canonical=False` — dashboard excludes them
- Archived versions have `status='closed'` — access control blocks respondents
- `resolve_survey()` filters for `is_canonical=True` on name lookups (UUID lookup returns canonical via redirect)

### 11. Collaborator access to archived versions goes through canonical

Archived versions don't have their own collaborators. Permission checks for data export etc. check the canonical survey's permissions.

## Risks / Trade-offs

**[Risk] Duplicate question codes in DB** → Draft copies share codes with canonical. This is safe because all queries scope by section FK or survey_header FK. Question codes are never used for cross-survey lookups in the app. The import system (which does global code checks) is not used for draft creation.

**[Risk] Moving sessions changes SurveySession.survey FK** → This is a bulk UPDATE, which is safe in a transaction. Old respondents continue seamlessly because `survey_section` uses `session.survey` for section lookup.

**[Risk] URL resolution for mid-survey respondents** → URL is `/surveys/<canonical-uuid>/<section-name>/`. After publish, section names exist in the archived version (sections were moved there). `survey_section` overrides `survey` from the session's survey, so the section lookup works against the correct version.

**[Risk] Large bulk updates on publish** → Moving sections + sessions is O(N) UPDATE queries. For a survey with 50 sections and 1000 sessions, this is fast (< 1 second). Wrapped in `transaction.atomic()`.

**[Trade-off] Published surveys are always read-only** → Quick fixes require the full create-draft → publish workflow. For truly urgent one-off fixes, the owner can use the draft workflow or close the survey temporarily.

**[Trade-off] SurveySession PROTECT prevents cascade deletion** → Deleting a survey with active sessions requires cleaning up sessions first. This is intentional — protects against accidental data loss.

## Migration Plan

1. **Schema migration**: Add `canonical_survey` (nullable self-FK), `version_number` (IntegerField, default=1), `is_canonical` (BooleanField, default=True) to SurveyHeader. Change `SurveySession.survey` FK to `on_delete=PROTECT`. Add composite index on `(canonical_survey, -version_number)`.
2. **Data migration**: All existing surveys get `is_canonical=True`, `version_number=1` (defaults handle this — no explicit migration needed).

## Open Questions

- Should archived versions be deletable by the owner (after confirming session cleanup)? Or should they be permanent?
- Should the version history be visible to respondents (e.g., "You completed survey v1, a new v2 is available")?
