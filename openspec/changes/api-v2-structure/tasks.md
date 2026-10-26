## 1. Services (PR 1)

- [x] 1.1 `cloning.copy_file`; cross-survey paste of question/section copies `Question.image`; test purge-after-paste
- [x] 1.2 `survey/services/groups.py` (create with `question_ids`, update, delete with/without questions); `editor_group_views` call it, responses unchanged; audit
- [x] 1.3 `survey/services/structure.py`: duplicate/paste question and section (logic out of `editor_views`), `move_question` (pop-up + cross-section, survey-wide rule cleanup); editor views call it; audit
- [x] 1.4 `duplicate_survey` (`cloning.clone_survey`: header with exclusion list, structure with codes kept, layers + objects + assets, layer bindings remapped, 200 MB cap); `DuplicateSurveyKeepsFieldsTest`
- [x] 1.5 `publishing.restore_version` audited; `AuditLog.ACTION_CHOICES` + choices-only migration
- [x] 1.6 `survey/icon_search.py` (picker's matching + ranking)

## 2. Editor (PR 1)

- [x] 2.1 "Duplicate" in `_survey_more_menu.html` → `editor_survey_duplicate` (POST, redirect to Build)
- [x] 2.2 "Move to section…" in `question_list_item.html` (dropdown, gate on live survey, toast with removed rules)
- [x] 2.3 Strings in all offered catalogs (`TranslationCatalogHygieneTest`)

## 3. REST (PR 1)

- [x] 3.1 `api/v1/structure.py`: groups CRUD, duplicate/copy, move, duplicate survey, versions + restore, `GET /icons`; schemas; `out` gains `group_id`, `groups`
- [x] 3.2 Tests per scenario; `scripts/build_api_reference.py` (and `build_mcp_reference.py` if `QuestionOut`/inputs feed MCP)
- [x] 3.3 `./run_tests.sh api mcp survey billing --noinput`

## 4. MCP (PR 2)

- [ ] 4.1 `mcp/tools/structure.py`: 13 tools; confirm on `delete_group` with questions
- [ ] 4.2 Tests; `scripts/build_mcp_reference.py`; help (grouping, copying, rolling back, icons); no changelog entry
- [ ] 4.3 `./run_tests.sh api mcp survey --noinput`; `npm run build` in `help/`
