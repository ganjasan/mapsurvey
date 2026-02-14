## 1. Model and Migrations

- [x] 1.1 Add `uuid` field to `SurveyHeader` model (`UUIDField`, `default=uuid.uuid4`, `unique=True`, `editable=False`), remove `unique=True` from `name` field
- [x] 1.2 Create migration 0009: add nullable `uuid` UUIDField to SurveyHeader
- [x] 1.3 Create migration 0010: data migration to populate UUID for all existing rows
- [x] 1.4 Create migration 0011: make `uuid` non-null + unique, remove `unique=True` from `name`

## 2. Helper Function

- [x] 2.1 Add `resolve_survey(survey_slug)` helper in `views.py` that tries UUID parse first, then name lookup, returns 404 on ambiguous name or not found

## 3. URL Routing

- [x] 3.1 Update `urls.py`: change all editor routes from `<str:survey_name>` to `<uuid:survey_uuid>`
- [x] 3.2 Update `urls.py`: change export/delete routes from `<str:survey_name>` to `<uuid:survey_uuid>`
- [x] 3.3 Update `urls.py`: change public routes from `<str:survey_name>` to `<str:survey_slug>`

## 4. Editor Views

- [x] 4.1 Update all `editor_views.py` functions: change parameter from `survey_name` to `survey_uuid`, change lookup from `get_object_or_404(SurveyHeader, name=...)` to `get_object_or_404(SurveyHeader, uuid=...)`
- [x] 4.2 Update `editor_survey_create` view: redirect to UUID-based URL after creation
- [x] 4.3 Update `editor_survey_settings` view: redirect to UUID-based URL after save

## 5. Public Views

- [x] 5.1 Update `survey_header`, `survey_section`, `survey_language_select`, `survey_thanks`, `download_data` views: change parameter to `survey_slug`, use `resolve_survey()` helper
- [x] 5.2 Update redirect calls in public views to pass UUID/slug correctly

## 6. Export/Delete/Import Views

- [x] 6.1 Update `export_survey` view: change parameter to `survey_uuid`, lookup by UUID
- [x] 6.2 Update `delete_survey` view: change parameter to `survey_uuid`, lookup by UUID
- [x] 6.3 Update `serialization.py` `create_survey_header()`: remove name uniqueness check
- [x] 6.4 Update `serialization.py` data-only import: add ambiguity check when multiple surveys share the name

## 7. Management Command

- [x] 7.1 Update `export_survey` management command: try UUID parse first, then name lookup, error on ambiguous name

## 8. Templates

- [x] 8.1 Update `editor.html` dashboard: change all `survey.name` URL references to `survey.uuid` (edit, export, delete, download links)
- [x] 8.2 Update `editor/survey_detail.html` and all editor partials: change `survey.name` to `survey.uuid` in URL-building references
- [x] 8.3 Update `landing.html`: change survey card links to use `survey.uuid`
- [x] 8.4 Update `survey_list.html`: change survey links to use `survey.uuid`
- [x] 8.5 Update `survey_thanks.html`: change URL reference to use UUID
- [x] 8.6 Update `story_detail.html`: change related survey link to use `survey.uuid`

## 9. Editor Forms

- [x] 9.1 Remove global name uniqueness validation from `SurveyHeaderForm` (if any `clean_name` checks exist)

## 10. Tests

- [x] 10.1 Update existing tests: change all URL constructions from name-based to UUID-based for editor routes
- [x] 10.2 Update existing tests: change public URL constructions to use UUID or slug
- [x] 10.3 Add test: two surveys with same name can coexist
- [x] 10.4 Add test: public URL with unique name resolves correctly
- [x] 10.5 Add test: public URL with ambiguous name returns 404
- [x] 10.6 Add test: public URL with UUID resolves correctly
- [x] 10.7 Add test: import survey with duplicate name succeeds
- [x] 10.8 Run full test suite and fix any remaining failures
