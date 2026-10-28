## 1. Consent page

- [x] 1.1 `api/oauth/views.py`: order workspaces Pro first then by name; `pro_count` in the context
- [x] 1.2 `api/templates/api/authorize.html`: folded `<details>` with the summary and a name/plan table; the no-workspace sentence unchanged
- [x] 1.3 New strings in the ten offered catalogs
- [x] 1.4 Tests (GIVEN/WHEN/THEN): many workspaces (summary, closed, order), one workspace, none; `./run_tests.sh api`
