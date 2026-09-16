# Tasks: python312-django52-upgrade

## 1. Toolchain

- [ ] 1.1 `Dockerfile`: `FROM python:3.12-slim`; confirm the apt geo packages resolve on the same Debian release
- [ ] 1.2 `Pipfile`: `python_version = "3.12"`, `django = "~=5.2"`, `posthog` per D4; `pipenv lock` under 3.12
- [ ] 1.3 3.12 venv for local work (D5); old venv kept as `env39` until the last pre-upgrade branch merges
- [ ] 1.4 Remove the six tracked `.pyc` files (`__pycache__/` is ignored since #188)

## 2. Code

- [ ] 2.1 `settings.py`: drop `USE_L10N`; add `FORM_RENDERER` → `mapsurvey.forms_renderer.TableFormRenderer` (D2)
- [ ] 2.2 `survey/models.py`: `CheckConstraint(condition=…)`; `makemigrations --check` clean or a no-op migration
- [ ] 2.3 `survey/serialization.py`: `datetime.now(timezone.utc)` for `exported_at`
- [ ] 2.4 Everything the suite and the deprecation run (D3) surface

## 3. Verification

- [ ] 3.1 Full suite green on 3.12 / 5.2
- [ ] 3.2 Suite green with `RemovedInDjango60Warning` and our modules' `DeprecationWarning` as errors
- [ ] 3.3 Section render snapshot test: `<tr>` per field, widget templates present, field order (D2)
- [ ] 3.4 `PostHogErrorTrackingTest` on the resolved posthog version (D4)
- [ ] 3.5 Third-party support check recorded in design.md (package, version, 5.2 support source)
- [ ] 3.6 PR preview: `run_e2e.sh` respondent flow; k6 lecture-burst p95 and memory vs current; `scripts/gunicorn_recycle_check.py` locally

## 4. Docs and rollout

- [ ] 4.1 CLAUDE.md: versions, venv switch, deprecation gate command
- [ ] 4.2 `.env.ports.example` registry (offset 300 for this worktree)
- [ ] 4.3 Merge; memory and PostHog errors watched for a day; `env39` deleted when unused
