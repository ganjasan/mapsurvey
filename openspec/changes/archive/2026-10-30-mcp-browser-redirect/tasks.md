## 1. Endpoint

- [x] 1.1 `mcp/views.py`: browser-shaped GET (no `Authorization`, `text/html` in `Accept`) → `302` to `editor_survey_start_agent?from=connections`, before the Origin and bearer checks

## 2. Tests

- [x] 2.1 `mcp/tests/test_auth.py`: browser GET to `/mcp` and `/mcp/` → 302 to the agent page; signed-out visitor lands on login with `next` to it; signed-in owner gets the page
- [x] 2.2 Client-shaped requests unchanged: GET with `Accept: application/json, text/event-stream` → 401 + `WWW-Authenticate`; GET `text/html` with a bearer → 405; POST without bearer → 401

## 3. Verify

- [x] 3.1 Run `mcp` tests
