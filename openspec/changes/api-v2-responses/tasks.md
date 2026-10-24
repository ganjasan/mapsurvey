## 1. Shared building blocks (PR 1)

- [x] 1.1 `survey/response_scope.py::responses_scope(survey, version, include_all, completed_only)` over `export.version_parts` + `excluded_sessions`; tests that it equals the export's session set
- [x] 1.2 `SurveyAnalyticsService(..., sessions=None)`: every `_stats_*` handler filters by it when given; editor callers unchanged (existing analytics tests stay green)
- [x] 1.3 Write-in counting for "other" options (`other_option` helpers) and sub-question stats for geo / Objects parents
- [x] 1.4 `export.collect_question(survey, question, sessions)` — one geo question's FeatureCollection across the family, 5 000-feature cap

## 2. REST routes (PR 1)

- [x] 2.1 `api/v1/responses.py`: summary route and its JSON shape (no ORM, no `*_json`); schemas
- [x] 2.2 Text answers route (cursor pagination, ordinal `#N`, 400 for non-text)
- [x] 2.3 Per-question GeoJSON route (400 for non-geo, `truncated`)
- [x] 2.4 Export link: create route, signed token (salt, 900 s), public download route re-checking role, Pro, token revocation; `cap.export`; `data_exported` with `surface='api_link'`; path added to the PostHog scrub prefixes
- [x] 2.5 Scope `responses:moderate` in `api/scopes.py` (label, not default), `SWITCH_SCOPES` + `SWITCH_NOTES` for the consent page and the token form; `OAUTH2_PROVIDER["SCOPES"]` follows
- [x] 2.6 Moderation route over `SessionValidationService.set_status` with `audit.record`; the editor's status views write the same audit row
- [x] 2.7 Tests (GIVEN/WHEN/THEN) per spec scenario; `scripts/build_api_reference.py` regenerated; `./run_tests.sh api survey`
- [x] 2.8 New strings in the ten offered catalogs

## 3. MCP tools (PR 2)

- [x] 3.1 `mcp/tools/responses.py`: the six tools over the PR-1 helpers; `{note, data}`; scopes
- [x] 3.2 Tests per scenario in `mcp/tests/`; `scripts/build_mcp_reference.py`
- [x] 3.3 `help/.../use-the-mcp-server.md`: what the agent can do with responses (replace "does not read responses"); no new changelog entry -- the 2026-10-24 MCP entry mentions reports (owner, 2026-10-25)
- [x] 3.4 `./run_tests.sh api mcp survey`; `npm run build` in `help/`
