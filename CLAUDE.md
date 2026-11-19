# CLAUDE.md

Guidance for Claude Code in this repository. This file holds commands and the one-line rules;
the detail of every subsystem lives in `.claude/architecture/<area>.md` — **read the area file before
changing code in that area**, and update it in the same PR when behaviour changes.

## Development Commands

```bash
docker-compose up --build              # All services (docker-compose up db = PostGIS only)
source env/bin/activate                # venv in ./env — Python 3.12, Django 5.2 LTS (image python:3.12-slim)
pipenv install                         # Pipfile; no requirements.txt
# Fresh venv, faster: uv venv --python 3.12 env && pipenv requirements --dev > /tmp/r.txt
#                     && uv pip install --python env/bin/python -r /tmp/r.txt
# Branches older than change python312-django52-upgrade need a 3.9 venv (../Mapsurvey/env39).
# Deprecation gate (once per Django bump): python -W error::django.utils.deprecation.RemovedInDjango60Warning
#   -W error::DeprecationWarning:survey -W error::DeprecationWarning:mapsurvey manage.py test survey
python manage.py migrate | runserver | createsuperuser | collectstatic
./run_tests.sh survey billing api mcp newsletter          # full suite
./run_tests.sh survey.tests.test_public_stories           # one capability / class / label
```

## Parallel worktrees (port isolation)

`run_dev.sh`, `run_tests.sh`, `run_e2e.sh` derive every host port from `PORT_OFFSET`
(PostGIS `5434`, Redis `6379`, web `8000` + offset); `COMPOSE_PROJECT_NAME` isolates the stack.
Set up: `cp .env.ports.example .env.ports`, pick a unique offset, keep the registry in that file
current. Offset `0` = original ports. `.env.ports` is gitignored.

## Testing

- `run_tests.sh` starts PostGIS **and Redis** itself. Redis is not optional: without `REDIS_URL`
  settings fall back to `localhost:6379/1` and, with `IGNORE_EXCEPTIONS`, silently write into
  whichever project owns that port.
- Defaults: `--noinput`, `--parallel auto`; `TEST_PARALLEL=1` for pdb; `KEEPDB=1` opt-in (kept
  parallel clones are not re-migrated). `mapsurvey/test_runner.py`: MD5 hasher, temp `MEDIA_ROOT`,
  one Redis DB per worker, language reset before every test. Dev packages `tblib`, `pypdf`,
  `reportlab` are required. A test that passes only serially is a broken test — never pin to one process.
- **One module per capability**: `survey/tests/test_<capability>.py` for each `openspec/specs/<capability>/`
  (`-` → `_`), fixtures in `survey/tests/helpers.py`. A change adds tests to its capability's module; a
  new capability adds a module. `SpecTestLineageTest` enforces it (`UNMAPPED_MODULES`,
  `SPECS_WITHOUT_SURVEY_TESTS` may only shrink). `api/`, `billing/`, `mcp/` follow the same rule.
- `django.test.TestCase`, docstrings in GIVEN/WHEN/THEN. Full notes: [`.claude/architecture/testing.md`](.claude/architecture/testing.md).

## Load testing

`loadtest/lecture-burst.js` (k6) — only against a Render PR preview (`[render preview]` in the PR
title; previews are manual and die after a day without commits), never production; seed with
`python manage.py seed_loadtest_survey`. See `loadtest/README.md`.

## Architecture

Django + PostGIS geospatial survey platform. `mapsurvey/` = settings/root URLs, `survey/` = main app,
plus `api/`, `mcp/`, `billing/`, `data/`, `reports/`, `help/` (Starlight site).

```
Organization
└── SurveyHeader ── SurveySection ── Question (12+ input types incl. GIS) ── OptionGroup → OptionChoice
                └── SurveySession ── Answer (GIS geometry fields)
```

Question types: `text`, `text_line`, `number`, `choice`, `multichoice`, `range`, `rating`, `datetime`,
`point`, `line`, `polygon`, `spraycan`, `layer_objects`, `thumbs`, `budget`, `image`, `html`.
`SurveySectionAnswerForm` (`survey/forms.py`) builds fields dynamically per `input_type`.

### Rules by area

Each block: the rules you must not break. Detail → the linked file.

**Survey structure** → [`.claude/architecture/survey-structure.md`](.claude/architecture/survey-structure.md)
- Creator rich text (`subtext`, `subheading`, `thanks_html`, group descriptions) passes
  `survey/html_sanitize.py` on EVERY write path; use `coerce_creator_html` (not `sanitize_`) where
  input may be plain text. A new write path for these fields must go through it (stored-XSS guard).
- Icons: never hand-build markup — `{% marker_icon %}` / `MarkerIcon.element()`. Catalog is generated
  by `scripts/build_icon_catalog.py`; search misses are fixed in `scripts/icon_terms/`.
- Allowed `display_style` per type = ONE table `question_types.DISPLAY_STYLES_BY_TYPE`.
- Geo columns: `question_types.geo_column()` / `Answer.geometry` / `GEO_TYPES`; never
  `getattr(answer, input_type)`. Spray = one `MultiPoint` answer, normalised by `survey/spray.py`.
- Budget is ONE non-geo type `budget` plus `QuestionGroup.budget` with prices on geo questions —
  never a geo budget type. Budget POSTs have no error path (`parse_submission`, `_enforce_group_budgets`).
- Visibility: one engine `survey/visibility.py`; broken rules fail OPEN; never reuse
  `parent_question_id` (that is geo pop-up sub-questions). Pop-up rules go through `popup_visibility`.
- Groups share one continuous `order_number` sequence with questions (`survey/groups.py`); anything
  that draws questions goes through `group_runs`.
- Translations are written only in the Translations tab; occurrences addressed by CODES;
  `translation_table.apply()` is the one writer; `translation_gaps` the one gap engine.
- Map-less stages = `models.MAPLESS_LAYOUTS` (`section.has_map`), never `layout == 'form'`.
  Placement paths use `hidePanelForPlacement()` + `visibleMapArea()`.
- Live surveys: safe edits in place, structural edits go to "Unpublished changes" (never "draft" in
  UI). New editor control gates on `structure_locked` or `is_read_only`, never `survey.status`.
  Copies take fields from `cloning.plain_field_values`; exclusions are explicit.
- `redirect_url` is `"#"` or an absolute http(s) URL; read via `redirects.completion_url`.

**Respondent side and sessions** → [`.claude/architecture/respondent-and-sessions.md`](.claude/architecture/respondent-and-sessions.md)
- Embedding: access control marks, middleware sets `frame-ancestors`. Never turn
  `CROSS_SITE_COOKIES` back on for embeds (#388); framed sessions use the cookie-less carrier. A new
  full-page respondent form needs `{% embed_session_field %}`.
- Empty session = no top-level `Answer`; one definition `analytics.nonempty_sessions`. Exports never
  contain empty sessions.
- Required/completed state is STORED on the session (`survey/required_state.py`); every new path that
  writes answers or changes the required set must call `refresh()` / `schedule_survey_refresh()`.
  No per-session "issues" engine — removed on purpose.

**Paper forms** → [`.claude/architecture/paper.md`](.claude/architecture/paper.md)
- Numbered copies: layout once + Form XObject stamping; never re-run layout or merge pages per copy.
  Bump `LAYOUT_VERSION` when page chrome changes.
- Photos: the CODE decides placement, never arrival order. No model reads a code (zxing-cpp
  locally). The web process never decodes; ingest/recognition run in Celery (restart the worker after
  edits). Mark geometry comes from the ink, the model only names marks.

**Map layers** → [`.claude/architecture/map-layers.md`](.claude/architecture/map-layers.md)
- One styling source `RefLayerFactory` / `styleFor()`; one validator `layers.normalize_style`.
  Geometry only from the gated endpoint, never inlined.
- Memory: `geojson` is gzip in `geojson_gz`; layer querysets DEFER `GEOMETRY_TEXT_FIELDS`; use
  `layers.layer_lite(question)` on respondent/Responses paths. Gunicorn worker is
  `DrainingThreadWorker`, not stock gthread.
- `SurveyMapLayer.geojson` is a cache of `LayerObject`s (`rebuild_layer`) — never edit it as a source.
  Layers belong to the CANONICAL survey (`layers_for`/`layer_owner`), never copied.
- Sub-questions are the one "ask about an object" mechanism; object answers use `Answer.layer_object`,
  never `parent_answer_id`. Shared-map objects keyed `s<session>-<n>`, never by answer id.
- One density renderer: `L.SprayAgreementLayer` (spray, coverage).

**API, MCP, OAuth, services** → [`.claude/architecture/api-mcp-services.md`](.claude/architecture/api-mcp-services.md)
- One `api.auth.authenticate(request, audience)`; bearer only, use `request.principal`, never
  `request.user`. Pro checked at the resource per request (`require_pro_api`), never at minting.
  `survey_for` answers 404; `section_for`/`question_for` always filter by survey.
- New endpoint = `@api_endpoint` + `rights` + `gates` + service layer — never a model directly.
- REST: register literal path segments before parameterised routes; regenerate
  `help/.../reference/api.md` (`scripts/build_api_reference.py`).
- MCP: stateless, one POST → one JSON response, NEVER SSE. Regenerate `reference/mcp-tools.md`.
  Vocabulary "unpublished changes", never "draft".
- OAuth redirect URIs: ONE rule `api/oauth/redirects.py` — never widen or bypass.
- Service layer `survey/services/` is the ONE write path for surveys/sections/questions/lifecycle;
  takes an `Actor`, never a `request`; validates by binding the editor forms.

**Sites** → [`.claude/architecture/sites.md`](.claude/architecture/sites.md) — closed set of blocks; every write
through `survey/services/sites.py`; never name a context variable `block` in an extending template.

**Billing and trial** → [`.claude/architecture/billing.md`](.claude/architecture/billing.md)
- PayPro URLs built only in `billing/checkout.py`; only the webhook writes `Subscription` state.
- Gate with `require_feature` / `{% has_feature %}` / `billing.trial.may|use`, never a column or
  `consume` directly. `has` / `may` / `covers` mean different things. Every Pro control carries
  `{% pro_badge %}`; sidebar items `{% pro_nav_mark %}`.

**Data module** → [`.claude/architecture/data.md`](.claude/architecture/data.md)
- `data/services.py` is the one write path; datasets are LINKED, never copied; write paths keep
  `owner.map_layers`, never `layers_for`. A private field never leaves via any output (`data.fields`).
- Versions update `LayerObject` rows in place — never delete + create (answers hang on rows).
- View kinds = one table `dataviews.kinds_for`; there is no unmasked reading of a view.
- Session scope = `data.scope.SessionScope`; never filter `is_deleted`/`validation_status`/emptiness
  by hand outside `data/` (`SessionFilterGuardTest`).
- Export: one collector, many writers; no `format` = legacy archive byte-for-byte. ZIP import is a
  Celery job (`SurveyImportJob`).

**Reports** → [`.claude/architecture/reports.md`](.claude/architecture/reports.md)
- Blocks name a dataset + question CODE, never a question row. `SurveyHeader.report`, never
  `Report.objects.get(survey=…)`. Reports computes nothing: counts come from Data.
- Editor views written once, exported via `on_survey`/`on_report`; templates take URLs from `u`.
- One builder script shared with Sites (`site_builder.js`) — never fork. Autosave answers only the
  touched block's fragments. Readers' markup = `reports/_block.html` + `css/report_public.css`.
- PDF/ZIP never rendered in a web request (`ReportPdf` + Celery). CSV/PNG made from the payload.
- Pro: writes gated (`reports/gate.py`), reading never; public routes never 404 for the plan.
- No "choose a survey" step before the editor; no token list back in the Key numbers panel.

**Creator UI** → [`.claude/architecture/creator-ui.md`](.claude/architecture/creator-ui.md)
- Colours are tokens (`survey/assets/css/tokens.css`), never literals (`TokenisedModulesTest`,
  `ColourRatchetTest`). A new module gets no look of its own — plain Bootstrap + existing partials.
- One confirmation dialog `#editorDialog` (`Dialog.confirm`, `data-confirm`) — never `confirm()`.
- Start page cards act in one click — no "choose, then confirm". Map start = one chain
  `map_start.suggest_start_position`.
- Changelog entries are files in `survey/changelog/`; comments anchor by codes; product → help
  links via `survey/help_links.py` (renamed help page needs a redirect + registry update).
- Respondent page stays the panel/crosshair flow — no bottom sheet without an approved mockup;
  no ▲▼ reorder buttons. New creator strings go into all catalogs by hand.

**Marketing site** → [`.claude/architecture/marketing-site.md`](.claude/architecture/marketing-site.md)
- Every competitor claim is a sourced `Fact` in `survey/vendors.py`; no competitor price figures;
  Pro price only in `partials/_landing_pricing.html`. No EU-hosting claims (hosted in the US).
- Blog articles are files in `survey/blog/`; stories come from `survey/story_data/` via
  `seed_story` — an unapproved story is never committed. Topics from `survey/topics.py` only.
- A new `{% trans %}` on the homepage needs its Russian in the same PR.

**Accounts and abuse** → [`.claude/architecture/accounts-abuse.md`](.claude/architecture/accounts-abuse.md)
- `is_active=False` means only a ban; confirmation rule lives in `survey/email_verification.py`.
  No CAPTCHA, no confirm-email banner back without the owner.
- Invitations accepted only through `survey/invitations.py`.
- Content screening runs only at go-live moments, fails open, never bans automatically.
- `/terms/` section ids and `/trust/#ownership` must not be renamed; bump `TERMS_UPDATED`.

**Analytics** → [`.claude/architecture/analytics.md`](.claude/architecture/analytics.md)
- PostHog never loads on respondent surfaces (`POSTHOG_EXCLUDED_PREFIXES`/`_VIEW_NAMES`); a new
  preview view extending a base template must be added. `SurveyEvent` & co. are a customer feature,
  never folded into PostHog. Events carry ids, never content/URLs. `posthog` pinned `~=6.9`.

### URL Structure

`/` → login or editor · `/editor/` dashboard · `/surveys/<name>/[<section>/]` respondent ·
`/surveys/<name>/download` export · `/r/<slug>/` report · `/p/<slug>/` site · `/api/v1/`, `/mcp` ·
`/admin/`.

### Environment Variables

`.env`: `SECRET_KEY`, `DEBUG`, `DJANGO_ALLOWED_HOSTS`; `SQL_ENGINE`, `SQL_DATABASE`, `SQL_USER`,
`SQL_PASSWORD`, `SQL_HOST`, `SQL_PORT`; optional S3 (`USE_S3=TRUE`, `AWS_*`);
`POSTHOG_AARRR_DASHBOARD_URL` (optional).

### GeoDjango

Engine `django.contrib.gis.db.backends.postgis`; `PointField`/`LineStringField`/`PolygonField`;
admin `LeafletGeoAdmin`; custom Leaflet draw widgets in `survey/forms.py`.

## Workflow: Spec Driven Development (OpenSpec)

`/opsx:new → /opsx:ff or /opsx:continue → /opsx:apply → /opsx:archive`. Every change or bug fix goes
through OpenSpec first: update the active related change, or create one. Never jump straight to code.

## Public repo vs. private ops repo

This repo is **public**. Business material (outreach, stories, cohorts, GTM, competitors,
requirements, raw notes, DPA) lives in private `ganjasan/mapsurvey-ops` at `../Mapsurvey-ops`; code
reads it only via `settings.OPS_DIR` from tooling, tests skip without it.
- People appear here only as `lead-NNN` (key in the ops repo). Never put a name, email, username or
  dossier excerpt into `openspec/`, a commit or a PR. `RepoHygieneTest` fails on real emails.
- Story data, respondent exports and ZIPs never enter git — not even the ops repo.

Planned work: `TODO.md`.
