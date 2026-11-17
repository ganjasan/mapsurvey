## 1. Checks and publishing

- [x] 1.1 `reports/checks.py`: privacy and other items, `needs_ack`
- [x] 1.2 `services.set_published(ack, visibility, mode)`; event `report_published`
- [x] 1.3 `_checks` view (both routes), `pr_checks.html`, the publish modal in the editor

## 2. The page and the editor

- [x] 2.1 map description: editor field, `aria-label` and note on the page
- [x] 2.2 preview pane: phone / computer; event `report_previewed`

## 3. Ship

- [x] 3.1 tests `survey/tests/test_reports_review.py`
- [x] 3.2 help, CLAUDE.md
- [x] 3.3 validate, archive, touched modules, full suite, screenshot, PR into `epic/reports`
