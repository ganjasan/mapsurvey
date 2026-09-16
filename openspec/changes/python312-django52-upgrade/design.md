# Design: python312-django52-upgrade

## Context

- Production: Python 3.9.25, Django 4.2.27, gunicorn 23 (gthread, draining worker since
  #188), psycopg2-binary, PostGIS on Render Postgres 16, `python:3.9-slim` (Debian
  bookworm) with GDAL/PROJ from apt.
- `Pipfile`: `django = "*"`, `[requires] python_version = "3.9"` — the resolver caps Django
  at 4.2 because 5.0+ requires 3.10. `posthog = "~=6.9"` for the same reason.
- Django 5.2 requires Python 3.10–3.13, PostgreSQL 14+, GEOS 3.9+, GDAL 3.2+ (bookworm ships
  GDAL 3.6). Render's database is 16.
- Respondent templates `survey_section_block.html` and `answer.html` render `{{ form }}`;
  widgets carry their own `template_name`s (Leaflet draw buttons, dropdowns, file upload).
- Local machine has `/usr/bin/python3.12` and `uv`.

## Goals / Non-Goals

Goals: a Python and a Django that receive security fixes for the next two years; no
respondent-visible change; every known deprecation in our code cleared so the next upgrade
(6.x) is a version bump, not an archaeology dig.

Non-goals: new framework features, driver changes, markup modernisation, performance work.

## Decisions

### D1. Python 3.12, not 3.13; Django 5.2 LTS, not 6.0
3.12 is the version every wheel we depend on has shipped for the longest (psycopg2-binary,
numpy 2, pandas 2.3, Pillow 11); 3.13 would work but buys nothing today. 5.2 is the LTS
(April 2028); 6.0 removes `CheckConstraint(check=)` and other things we still carry, and its
support window is shorter. The pin is `django = "~=5.2"`: `*` is exactly how 4.2 stuck.

### D2. Respondent form markup is frozen through a project renderer
Django 5.0 switched `Form.template_name` from `django/forms/table.html` to `div.html`.
`mapsurvey/forms_renderer.py::TableFormRenderer(DjangoTemplates)` sets
`form_template_name = "django/forms/table.html"` and `FORM_RENDERER` points at it, so
`{{ form }}` renders the same `<tr>`/`<th>`/`<td>` structure the section page's CSS and JS
expect. A render test snapshots the structure of one section (field order, `<tr>` per
field, widget templates present) so the freeze is enforced, not assumed. The admin's
`{{ form.as_p }}` is unaffected.

### D3. Deprecations are cleared, not silenced
The suite runs once with `-W error::django.utils.deprecation.RemovedInDjango60Warning`
and `-W error::DeprecationWarning:survey -W error::DeprecationWarning:mapsurvey` (our
modules only; third-party warnings are theirs). Known items: `USE_L10N = True` (a no-op
setting since 5.0 — removed), `CheckConstraint(check=…)` → `condition=` (the autodetector
must stay clean: `makemigrations --check`; if it wants the constraint re-stated, a no-op
migration is added), `datetime.utcnow()` → `datetime.now(timezone.utc)`.

### D4. Third-party packages: resolve, then verify support, then run the canaries
`pipenv lock` under 3.12 with the new pins; for each Django-integrating package the
resolved version's changelog is checked for 5.2 support (django-registration 5.x,
django-leaflet 0.32, django-ratelimit 4.1, django-storages 1.14, django-redis,
django-debug-toolbar). `posthog` moves to `~=7` only if `PostHogErrorTrackingTest` (the
canaries for the 6.7.5–6.7.13 breakage) pass on it; otherwise it stays on 6.9, which runs
on 3.12.

### D5. Developer venv switch
`env/` is a 3.9 venv shared by every worktree through a symlink. The upgrade creates
`env` as a 3.12 venv in the main checkout (`uv venv --python 3.12 env && uv pip install
--python env/bin/python -r <(pipenv requirements --dev)`) and keeps the old one as `env39`
until the last pre-upgrade branch is merged; worktrees created from post-upgrade master
symlink `env` as before. `run_*.sh` are unchanged. CLAUDE.md and the worktree bootstrap
note say which venv a branch needs.

### D6. Rollout
One PR. Its preview runs the full suite (CI), `run_e2e.sh` against the preview, the k6
lecture-burst (`loadtest/lecture-burst.js`) against the preview seeded with
`seed_loadtest_survey` — p95 and memory compared with the current Standard-plan numbers —
and `scripts/gunicorn_recycle_check.py` locally under 3.12. Merge deploys web, worker and
cron from the same image; pre-deploy runs no schema change unless D3 adds the no-op
constraint migration (additive, safe in the pre-deploy window — see
lesson_predeploy_destructive_migration_window).

## Risks / Trade-offs

- A package without Django 5.2 support surfaces only at import or at runtime: the suite
  and the e2e flow are the net; `django-registration` is the one with the most surface
  (registration views, activation) and has explicit tests (`registration-abuse-defenses`).
- GIS: same Debian release, same apt GDAL — low risk, but `LayerValidationTest`,
  `LayerStreamingRebuildTest` and the export tests exercise GEOS/GDAL end to end.
- Memory: Python 3.12 objects are slightly smaller and the allocator differs; expect the
  idle baseline to move a little either way — the post-#187 numbers (260–320 MB) are the
  comparison.
- Timing: two independent version jumps in one PR is deliberate — 3.12 alone cannot be
  locked without also moving Django, because the resolver would then pick 6.0.

## Migration Plan

1. Toolchain (Dockerfile, Pipfile, lock, venv) → suite red, fix until green.
2. Deprecation run (D3) → fix until green.
3. Renderer freeze (D2) + snapshot test.
4. Package verification (D4), posthog decision.
5. Preview: e2e, k6, recycle check; compare numbers.
6. Merge; watch memory and PostHog errors for a day; delete `env39` once no branch needs it.
