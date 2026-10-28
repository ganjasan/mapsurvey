## 1. Fix

- [x] 1.1 `api/oauth/cimd.py`: `prefer_public_auth` before `normalise_metadata` in `MetadataFetcher.fetch`
- [x] 1.2 Tests (GIVEN/WHEN/THEN): ChatGPT's real document through CIMD creates a public application, renders consent and exchanges the code; a key-only document is still refused
- [x] 1.3 ChatGPT step "press [[Add]]" in `survey/agent_clients.py`, the ten catalogs (`.po` + `.mo`) and `help/.../use-the-mcp-server.md`
- [x] 1.4 `connections.html`: two-line `{# #}` → `{% comment %}`; test that no comment reaches the page
- [x] 1.5 Run `./run_tests.sh api mcp` + catalog, agent-client and help-link tests (343 tests, OK)

## 2. Production

- [ ] 2.1 After deploy: connect ChatGPT on production and see the Allow page
