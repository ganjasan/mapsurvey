# Tasks: db-plan-basic-1gb

## 1. Blueprint

- [x] 1.1 `render.yaml`: `mapsurvey-db` `plan: basic-1gb`, `previewPlan: basic-256mb`, with the incident and the "Blueprint, not dashboard" rule in a comment

## 2. Verification (after merge)

- [ ] 2.1 Render shows `mapsurvey-db` on `basic_1gb` and the `memory_limit` metric reads 1 GB
- [ ] 2.2 The web service reconnects after the database restart (no lasting 500s)
- [ ] 2.3 The next PR preview still provisions its database on `basic-256mb`
