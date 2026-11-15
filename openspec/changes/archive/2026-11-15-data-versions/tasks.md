## 1. Model

- [x] 1.1 `DatasetVersion`; `DataImportJob.target`, `note`; statuses `preview`, `applying`; migration
- [x] 1.2 upload records version 1

## 2. Diff and apply

- [x] 2.1 `data/versions.py`: incoming objects by key, diff, apply in place, dictionary merge, caps
- [x] 2.2 `data.tasks.run_data_version` (preview / apply)

## 3. Page

- [x] 3.1 upload, preview card with note, apply, discard, history

## 4. Ship

- [x] 4.1 tests `survey/tests/test_data_versions.py`
- [x] 4.2 translations, help, CLAUDE.md
- [x] 4.3 full suite, /verify, PR into epic/data
