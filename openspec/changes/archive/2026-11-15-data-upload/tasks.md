## 1. Models

- [x] 1.1 `survey` migration: `SurveyMapLayer.survey` nullable, `organization` FK + backfill (D1)
- [x] 1.2 `data` migration: `Dataset.fields`, `DataImportJob` (D4)

## 2. Import

- [x] 2.1 `data/imports.py`: read GPKG/SHP-zip/KML/GeoJSON via GDAL, CSV via `csv`; reprojection; BNG guess; refusal messages (D2)
- [x] 2.2 Field types, key candidate, private columns (D3)
- [x] 2.3 `data/tasks.py` `run_data_import`: once per job, limits, objects, rebuild, report, file deleted (D4)

## 3. Catalogue

- [x] 3.1 Upload view (size limit by plan), job card partial (poll), dismiss; routes
- [x] 3.2 Catalogue: one-click upload control, job cards, workspace datasets visible to every member, source "Uploaded" (D5)
- [x] 3.3 New strings in every offered catalog

## 4. Tests and docs

- [x] 4.1 `survey/tests/test_data_upload.py`: spec scenarios
- [x] 4.2 Help page and `CLAUDE.md`
- [x] 4.3 Full suite once; `/verify` with a screenshot; `openspec validate --strict`
