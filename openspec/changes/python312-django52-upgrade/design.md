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

### D2. Respondent form markup: verified untouched, no renderer pin
Django 5.0 switched `Form.template_name` from `django/forms/table.html` to `div.html`. The
first draft of this change pinned `table.html` through a project `FORM_RENDERER`; the
suite showed it changes nothing: the respondent section is rendered by
`partials/survey_section_partial.html`, which walks `form.visible_fields` and emits a
`question-card` per field through the project's widget templates, and Django's form-level
template is never involved. The two templates that do render `{{ form }}`
(`survey_section_block.html`, `answer.html`) are rendered by no view. The renderer pin was
dropped; `SectionFormMarkupTest` keeps both facts true — a section renders its cards,
labels and widgets, and no respondent-facing template reaches for `{{ form }}` or
`as_p`/`as_table`/`as_div`/`as_ul`. The admin's `{{ form.as_p }}` is unaffected either way.

### D2a. Django 5 refuses unsaved instances in related filters
`ValueError: Model instances passed to related filters must be saved` surfaced in one
place: `Question.collects_objects` ran `Question.objects.filter(parent_question_id=self)`
on the transient question the editor's live preview builds. Guarded with `self.pk is not
None` (an unsaved question has no sub-questions). No other site matched in the suite.

### D2b. A dev dependency the old venv carried by hand
`python-dotenv` was installed in the 3.9 venv but listed nowhere; `settings.py` tolerates
its absence, so the fresh 3.12 venv silently stopped loading `.env`, the AI key vanished
and the create-page wizard tests failed. It is now a `[dev-packages]` entry (production
reads Render's environment). The old venv held 25 other unlisted packages (matplotlib,
lxml, polib, pytrends, testcontainers…) that no test needs.

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

**Resolved (2026-09-16, `pipenv lock` under 3.12):** Django 5.2.17, django-registration
5.2.1, django-leaflet 0.34.0, django-ratelimit 4.1.0, django-storages 1.14.6, django-redis
7.0.0, django-debug-toolbar 8.0.0, celery 5.6.3, redis 6.4.0, numpy 2.5.3, psycopg2-binary
2.9.13, whitenoise 6.12.0, posthog 6.9.3. Four unforced major jumps the first lock produced
were pinned back to the current majors, each with its own follow-up change: pandas 3.0 →
`~=2.3` (export value tests), gunicorn 26 → `~=23.0` (`DrainingThreadWorker` subclasses
gthread internals; `scripts/gunicorn_recycle_check.py` is the gate), Pillow 12 → `~=11.3`,
anthropic 1.x → `~=0.122` (SDK API change; the Anthropic provider path is test-only today).
django-redis 7 and django-debug-toolbar 8 are Django-adjacent majors that track Django
support and stay.

**Declared support (installed dist-info metadata, task 3.5):** django-registration 5.2.1
classifiers 4.2 / 5.1 / 5.2, `Django>=4.2,!=5.0.*`; django-redis 7.0.0 `Django>=5.2,<7.0`;
django-debug-toolbar 8.0.0 `django>=5.2`; whitenoise 6.12.0 classifiers 4.2–6.0;
django-storages 1.14.6 classifiers up to 5.1 (no 5.2 classifier yet; it uses the stable
`STORAGES` API and the media tests exercise the S3 backend class); django-leaflet 0.34.0
requires Python ≥3.10 (a 2025 release; Django 5 supported since 0.30); django-ratelimit
4.1.0 declares no framework classifier (decorator-only, works on 4.2–5.2); celery 5.6.3
`Django>=2.2.28`; posthog 6.9.3 Django-agnostic (canaries cover the middleware).

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
