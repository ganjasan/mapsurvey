## 1. Fix

- [x] 1.1 `api/oauth/dcr.py`: `SUPPORTED_GRANT_TYPES`; `normalise_metadata` drops other grant types when a supported one remains
- [x] 1.2 Tests (GIVEN/WHEN/THEN): claude.ai's real document through CIMD creates the application and renders consent; DCR with jwt-bearer answers 201 with the two supported grants; an unsupported-only document still fails
- [x] 1.3 Run `./run_tests.sh api mcp` (261 tests, OK)

## 2. Production

- [ ] 2.1 After deploy: connect claude.ai on production and see the Allow page
