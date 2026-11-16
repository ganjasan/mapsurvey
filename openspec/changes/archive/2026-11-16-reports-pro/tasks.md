## 1. The gate

- [x] 1.1 feature `reports` + uncapped trial allowance + labels (`billing/features.py`, `billing/trial.py`)
- [x] 1.2 `reports/gate.py`: `covered`, `may_write`, `use`, `freeze_if_lapsed`, `lapsed_reports`
- [x] 1.3 writes: `on_survey` / `on_report` wrappers, `report_create`, `report_start`, `report_import`; event `report_paywall_shown`
- [x] 1.4 reading: read-only banner in the editor and on the Reports list; public views freeze a lapsed report
- [x] 1.5 `manage.py freeze_reports_without_pro [--dry-run]`

## 2. Ship

- [x] 2.1 tests `survey/tests/test_reports_pro.py`; existing tests of the tab moved to Pro workspaces where they edit
- [x] 2.2 help, CLAUDE.md
- [x] 2.3 ops: count on production (read-only) and a draft of the letter to owners of affected pages, for the owner to send
- [x] 2.4 validate, archive, full suite, PR into `epic/reports`
