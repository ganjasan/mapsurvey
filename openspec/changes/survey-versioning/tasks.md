## 1. Model & Migrations

- [ ] 1.1 Add `canonical_survey` ForeignKey to `SurveyHeader` (self-referencing, null=True, blank=True, on_delete=SET_NULL, related_name='versions')
- [ ] 1.2 Add `version_number` PositiveIntegerField to `SurveyHeader` (default=1)
- [ ] 1.3 Add `is_canonical` BooleanField to `SurveyHeader` (default=True, db_index=True)
- [ ] 1.4 Change `SurveySession.survey` FK on_delete from CASCADE to PROTECT
- [ ] 1.5 Add model method `SurveyHeader.has_draft_copy()` → returns True if a draft copy exists (using `published_version` reverse lookup)
- [ ] 1.6 Add model method `SurveyHeader.get_draft_copy()` → returns the draft copy or None
- [ ] 1.7 Add model property `SurveyHeader.is_draft_copy` → returns True if `published_version` is set
- [ ] 1.8 Add model method `SurveyHeader.get_version_history()` → returns all versions ordered by `-version_number`
- [ ] 1.9 Add `published_version` ForeignKey to `SurveyHeader` (self-referencing, null=True, blank=True, on_delete=SET_NULL, related_name='draft_copies') — links draft copy to canonical
- [ ] 1.10 Create schema migration
- [ ] 1.11 Add composite index on `(canonical_survey, -version_number)`

## 2. Clone Logic

- [ ] 2.1 Create `survey/versioning.py` with `clone_survey_for_draft(canonical)` function
- [ ] 2.2 Clone sections with same name, code, title, linked list structure, map position, translations
- [ ] 2.3 Clone questions with **same codes**, same properties, choices, translations, sub-questions
- [ ] 2.4 Clone collaborators from canonical to draft
- [ ] 2.5 Handle draft name: prefix with `[draft] `, truncate to 45 chars
- [ ] 2.6 Copy settings: available_languages, visibility, redirect_url, thanks_html, password_hash

## 3. Compatibility Check

- [ ] 3.1 Create `check_draft_compatibility(draft, canonical)` function in `survey/versioning.py`
- [ ] 3.2 Detect deleted questions with answers: compare question codes between draft and canonical
- [ ] 3.3 Detect input_type changes on questions with answers
- [ ] 3.4 Detect removed choice codes on questions where answers use those codes in `selected_choices`
- [ ] 3.5 Return list of breaking issue dicts with type, question info, and answer count

## 4. Publish Logic

- [ ] 4.1 Create `publish_draft(draft, force=False)` function in `survey/versioning.py`
- [ ] 4.2 Run compatibility check — raise `IncompatibleDraftError` if not force
- [ ] 4.3 Create archived SurveyHeader (`is_canonical=False`, `canonical_survey=canonical`, `version_number=canonical.version_number`, `status='closed'`)
- [ ] 4.4 Move sections from canonical to archived: `SurveySection.objects.filter(survey_header=canonical).update(survey_header=archived)`
- [ ] 4.5 Move sessions from canonical to archived: `SurveySession.objects.filter(survey=canonical).update(survey=archived)`
- [ ] 4.6 Move sections from draft to canonical: `SurveySection.objects.filter(survey_header=draft).update(survey_header=canonical)`
- [ ] 4.7 Copy settings from draft to canonical (languages, visibility, redirect_url, thanks_html)
- [ ] 4.8 Increment `canonical.version_number`
- [ ] 4.9 Delete draft SurveyHeader
- [ ] 4.10 Wrap entire publish in `transaction.atomic()`

## 5. Read-Only Lock on Published Surveys

- [ ] 5.1 Add check to structural editor endpoints (section create/delete/reorder, question create/edit/delete/reorder, subquestion create): if survey `status` in (`published`, `closed`) → return 403
- [ ] 5.2 Allow settings endpoint (`editor_survey_settings`) to work regardless of status
- [ ] 5.3 Allow lifecycle transition and password endpoints to work regardless of status

## 6. Session Routing

- [ ] 6.1 Modify `survey_section` view: if session exists, use `session.survey` for section lookup (may be archived version)
- [ ] 6.2 Modify `survey_section` view: new sessions always created against canonical
- [ ] 6.3 Modify `survey_header` view: redirect to section based on canonical's structure (for new respondents)
- [ ] 6.4 Handle edge case: session references a survey that was deleted → clear session, create new

## 7. Editor Endpoints

- [ ] 7.1 Add `editor_create_draft` view (POST `/editor/surveys/<uuid>/create-draft/`) — owner-only, published-only, checks no existing draft
- [ ] 7.2 Add `editor_publish_draft` view (POST `/editor/surveys/<uuid>/publish-draft/`) — owner-only, draft-copy-only, runs compatibility check, supports `force` param
- [ ] 7.3 Add `editor_discard_draft` view (POST `/editor/surveys/<uuid>/discard-draft/`) — owner-only, draft-copy-only
- [ ] 7.4 Add `editor_check_compatibility` view (GET `/editor/surveys/<uuid>/check-compatibility/`) — returns JSON with breaking issues
- [ ] 7.5 Add URL patterns for the 4 new endpoints

## 8. Version-Aware Data Export

- [ ] 8.1 Modify `download_data` view: accept `?version=latest|v1|v2|all` query param
- [ ] 8.2 Resolve target version(s): `latest` → canonical, `vN` → archived with version_number=N, `all` → all versions
- [ ] 8.3 Prefix filenames with `vN_` when exporting multiple versions
- [ ] 8.4 Handle `answer.question` null safety in download_data (skip orphaned answers)

## 9. Editor UI

- [ ] 9.1 Add version badge (`vN`) to editor header bar in `survey_detail.html`
- [ ] 9.2 Add "Draft of <original name>" indicator when editing a draft copy
- [ ] 9.3 Add "Edit Published Survey" button to header actions (published surveys without active draft, owner-only)
- [ ] 9.4 Add "Publish Version" and "Discard Draft" buttons when editing a draft copy (owner-only)
- [ ] 9.5 Add link banner on published survey with active draft: link to draft editor
- [ ] 9.6 Add read-only banner and hide structural edit controls when survey is published/closed
- [ ] 9.7 Create publish confirmation modal (compatible: simple confirm; incompatible: show issues + force option)
- [ ] 9.8 Create discard confirmation modal
- [ ] 9.9 Add JS: on "Publish Version" click, GET check-compatibility first, show appropriate modal
- [ ] 9.10 Add version history section with version list (number, date, session count)
- [ ] 9.11 Add version selector to download UI (Latest, v1, v2, ..., All)

## 10. Dashboard UI

- [ ] 10.1 Exclude draft copies (`published_version__isnull=False`) and archived versions (`is_canonical=False`) from dashboard queryset
- [ ] 10.2 Add version number display (`vN`) to survey rows in dashboard table

## 11. Public View Integration

- [ ] 11.1 Modify `resolve_survey()`: name lookups filter for `is_canonical=True`; UUID lookups redirect to canonical if hitting archived version
- [ ] 11.2 Ensure `check_survey_access` works correctly with archived versions (status='closed' → shows closed page)

## 12. Serialization

- [ ] 12.1 Add `version_number` field to `serialize_survey_to_dict()` output (as `version`)
- [ ] 12.2 Update `create_survey_header()` to read `version` from data (default 1), always create as `is_canonical=True`
- [ ] 12.3 Ensure archived versions are not included in export

## 13. Tests

- [ ] 13.1 Test model fields: `canonical_survey`, `version_number`, `is_canonical`, `published_version`
- [ ] 13.2 Test `has_draft_copy()` / `get_draft_copy()` / `is_draft_copy` / `get_version_history()`
- [ ] 13.3 Test `clone_survey_for_draft()`: sections, questions, choices, translations cloned with same codes
- [ ] 13.4 Test clone name truncation: `[draft] ` prefix + 45 char limit
- [ ] 13.5 Test compatibility check: deleted question with answers → breaking
- [ ] 13.6 Test compatibility check: input_type changed with answers → breaking
- [ ] 13.7 Test compatibility check: choice code removed with answers → breaking
- [ ] 13.8 Test compatibility check: safe changes pass (add question, reorder, change text)
- [ ] 13.9 Test `publish_draft()`: sections moved to archive, sessions moved, draft sections moved to canonical, version incremented, draft deleted
- [ ] 13.10 Test `publish_draft()`: old answers keep valid question FK after publish
- [ ] 13.11 Test `publish_draft()`: incompatible without force → raises error
- [ ] 13.12 Test `publish_draft()`: force=True → succeeds despite breaking changes
- [ ] 13.13 Test grace period: old session continues on archived version after new version published
- [ ] 13.14 Test grace period: new session created against canonical after publish
- [ ] 13.15 Test `editor_create_draft`: 302 for owner of published, 409 if draft exists, 400 if not published, 403 for non-owner
- [ ] 13.16 Test `editor_publish_draft`: compatible → 302 redirect, structure swapped, draft deleted
- [ ] 13.17 Test `editor_publish_draft`: incompatible → 409 with issues
- [ ] 13.18 Test `editor_discard_draft`: 302 redirect, draft deleted, canonical unchanged
- [ ] 13.19 Test read-only lock: structural edits on published survey → 403, settings edits → 200
- [ ] 13.20 Test dashboard excludes draft copies and archived versions
- [ ] 13.21 Test download_data with version filter: latest, specific version, all
- [ ] 13.22 Test serialization: export includes version, import reads version, default 1
- [ ] 13.23 Test draft copies invisible to respondents (404)
- [ ] 13.24 Test archived versions show "closed" page to respondents
- [ ] 13.25 Test SurveySession PROTECT: cannot delete SurveyHeader with sessions
