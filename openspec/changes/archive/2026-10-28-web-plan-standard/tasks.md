# Tasks: web-plan-standard

## 1. Blueprint

- [x] 1.1 `render.yaml`: web service `plan: standard`, `previewPlan: starter`, with the incident and the "Blueprint, not dashboard" rule in a comment
- [x] 1.2 Replace the gunicorn sizing comment with the measured numbers (425–480 MB idle with two workers on Starter)

## 2. Docs

- [x] 2.1 `CLAUDE.md` load-testing note: previews run on Starter, production on Standard

## 3. Verification (after merge)

- [ ] 3.1 Render dashboard shows `mapsurvey` on Standard and the `memory_limit` metric reads 2 GB
- [ ] 3.2 The next PR preview still provisions its web service on Starter
