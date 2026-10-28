## 1. Shared pieces (PR 1)

- [x] 1.1 segno in Pipfile/Pipfile.lock (`pipenv upgrade` only that package)
- [x] 1.2 `embedding.survey_url_for(survey, base)`, `snippet_html(..., base=)`; `TrackedLink.build_url(base)`; editor passes `public_base_url(request)`
- [x] 1.3 Share page and link delete use the canonical survey; remove or fix `SurveyHeader.get_test_url`
- [x] 1.4 `survey/share.py`: share info, QR (segno SVG/PNG), tracked link create/delete/list with counts, embed hosts — request-free, used by REST and MCP

## 2. REST routes (PR 1)

- [x] 2.1 `api/v1/share.py`: share info, `qr.svg`/`qr.png`, tracked links CRUD, embed hosts; schemas; audit
- [x] 2.2 Tests per scenario (incl. the editor's https links and canonical links); `scripts/build_api_reference.py`
- [x] 2.3 Strings in the ten offered catalogs (none: API messages are English, like every API error); `./run_tests.sh api survey`

## 3. MCP (PR 2)

- [x] 3.1 `mcp/protocol.py` image content; `mcp/tools/share.py` six tools
- [x] 3.2 Tests; `scripts/build_mcp_reference.py`; help page (what to ask to share a survey); no new changelog entry -- the MCP entry gains one sentence
- [x] 3.3 `./run_tests.sh api mcp survey`; `npm run build` in `help/`
