# Tasks: python312-django52-upgrade

## 1. Toolchain

- [x] 1.1 `Dockerfile`: `FROM python:3.12-slim`; confirm the apt geo packages resolve on the same Debian release
- [x] 1.2 `Pipfile`: `python_version = "3.12"`, `django = "~=5.2"`, `posthog` per D4; `pipenv lock` under 3.12
- [x] 1.3 3.12 venv for local work (D5): `uv venv --python 3.12 env` in this worktree; the main checkout keeps its 3.9 venv for pre-upgrade branches (rename to `env39` when master moves)
- [x] 1.4 Remove the six tracked `.pyc` files (`__pycache__/` is ignored since #188)

## 2. Code

- [x] 2.1 `settings.py`: drop `USE_L10N` (the `FORM_RENDERER` pin was tried and dropped — D2)
- [x] 2.1a `Question.collects_objects` guards the unsaved live-preview question (D2a); `python-dotenv` added to dev-packages (D2b)
- [x] 2.2 `survey/models.py`: `CheckConstraint(condition=…)`; `makemigrations --check` clean or a no-op migration
- [x] 2.3 `survey/serialization.py`: `datetime.now(timezone.utc)` for `exported_at`
- [ ] 2.4 Everything the suite and the deprecation run (D3) surface

## 3. Verification

- [x] 3.1 Full suite green on 3.12 / 5.2
- [x] 3.2 Suite green with `RemovedInDjango60Warning` and our modules' `DeprecationWarning` as errors
- [x] 3.3 `SectionFormMarkupTest`: a section renders its question cards, labels and widgets; no respondent template renders a whole form (D2)
- [x] 3.4 `PostHogErrorTrackingTest` on the resolved posthog version (D4)
- [x] 3.5 Third-party support check recorded in design.md (package, version, 5.2 support source)
- [x] 3.6 PR preview #190: image builds `FROM python:3.12-slim` (Debian trixie, newer GDAL/PROJ than bookworm — see design Risks), web live in 3 min, Celery 5.6.3 worker ready, migrations applied from zero through `survey.0086`, public pages render (`/`, `/accounts/register/`, `/trust/`, `/sitemap.xml`)
- [x] 3.7 Local 3.12 dev server: respondent section renders its question cards, a GeoJSON Feature point answer round-trips into `Answer.point`; `run_e2e.sh` (Playwright) against it
- [ ] 3.8 k6 lecture-burst against the preview: needs the preview database seeded (`seed_loadtest_survey` via a Render one-off job — no shell, see lesson_preview_seeding_paths), so it needs the owner or an API key

## 4. Docs and rollout

- [x] 4.1 CLAUDE.md: versions, venv switch, deprecation gate command
- [x] 4.2 `.env.ports.example` registry (offset 300 for this worktree)
- [ ] 4.3 Merge; memory and PostHog errors watched for a day; `env39` deleted when unused
