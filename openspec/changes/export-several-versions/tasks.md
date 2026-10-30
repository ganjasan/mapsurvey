## 1. Resolver

- [x] 1.1 `versioning.resolve_version_scope`: comma-separated list → the named family members in family order; drop unknown, ignore `draft`, `all` widens, nothing left → family, one left → `vN`
- [x] 1.2 Tests in `survey/tests/test_version_filter_scope.py` (order, duplicates, unknown, empty, draft, single, `all` inside)

## 2. Export

- [x] 2.1 Export tests in `survey/tests/test_responses_export_formats.py`: `version=v2,v3` of a three-version survey contains only those sessions in xlsx and the legacy zip, with `vN_` prefixes; `all` / single / none unchanged

## 3. Dialog

- [x] 3.1 `_export_modal.html`: check-box list in place of the select, "All versions" master, hint when nothing ticked
- [x] 3.2 `export_dialog.js`: render check-boxes, master toggle, draft exclusive, join with comma, all ticked → no param, none ticked → Export disabled, preselect a list
- [x] 3.3 New strings into every offered catalog (`TranslationCatalogHygieneTest`)
- [x] 3.4 Template test: dialog renders the check-box container

## 4. API / MCP

- [x] 4.1 `ExportLinkIn.version` and MCP `VERSION` descriptions name the list form
- [x] 4.2 Regenerate `reference/api.md` and `reference/mcp-tools.md`; REST/MCP test for a list

## 5. Verify

- [x] 5.1 Run touched modules (`test_version_filter_scope`, `test_responses_export_formats`, api/mcp reference + responses tests, i18n hygiene)
- [x] 5.2 Check the dialog in the browser on a multi-version survey
- [x] 5.3 Help page `how-to` export mentions picking several versions
