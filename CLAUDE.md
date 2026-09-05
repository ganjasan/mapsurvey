# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Docker (recommended)
docker-compose up --build              # Start all services
docker-compose up db                   # Start only PostgreSQL/PostGIS

# Local development (venv in ./env)
source env/bin/activate                # Activate virtual environment
pipenv install                         # Install dependencies (Pipfile — there is no requirements.txt)
python manage.py migrate               # Apply database migrations
python manage.py runserver             # Start development server (port 8000)
python manage.py createsuperuser       # Create admin user
python manage.py collectstatic         # Collect static files

# Testing (requires running PostGIS on port 5434)
./run_tests.sh survey                  # Run all survey app tests
./run_tests.sh survey -v2              # Verbose output
./run_tests.sh survey.tests.SmokeTest  # Run specific test class
```

## Parallel worktrees (port isolation)

`run_dev.sh`, `run_tests.sh`, and `run_e2e.sh` derive every host port from a single
`PORT_OFFSET` so multiple worktrees can run dev + tests at the same time without
colliding. To set up a worktree: `cp .env.ports.example .env.ports` and pick a unique
offset (keep the registry in that file current). Ports = base + offset
(PostGIS `5434`, Redis `6379`, web `8000`). `COMPOSE_PROJECT_NAME` isolates the docker
stack per worktree. Offset `0` reproduces the original ports. `.env.ports` is gitignored.

## Testing

Tests use Django's built-in test framework with PostGIS. Django automatically creates a separate `test_mapsurvey` database.

**Prerequisites**: none — `run_tests.sh` starts the PostGIS and Redis containers itself and waits
for both. Redis is not optional: `settings.py` falls back to `redis://localhost:6379/1` when
`REDIS_URL` is unset, so on a machine running several projects the suite would otherwise connect to
whichever project owns that port and write into its database. `CACHES` sets `IGNORE_EXCEPTIONS`, so
that goes wrong silently rather than failing loudly.

**Test location**: `survey/tests.py`

**Writing tests**: Use `django.test.TestCase` and GIVEN/WHEN/THEN pattern for docstrings.

**Redis**: a few tests (`LastActivityMiddlewareTest`) exercise cache-gated code and need
Redis on `localhost:6379`. `run_tests.sh` does not start it; without it those tests fail
with `UserActivity.DoesNotExist`.

## Load testing

`loadtest/lecture-burst.js` (k6) reproduces a lecture-hall burst — N students opening the
same map survey at once. It does **not** reproduce locally (a dev machine is far faster
than a 0.5 CPU Render Starter instance), so run it against a Render PR preview, never
production. Seed the preview's empty database first with
`python manage.py seed_loadtest_survey`. See `loadtest/README.md`.

## Architecture Overview

This is a Django-based geospatial survey platform using PostGIS for storing geographic data (points, lines, polygons).

### Project Structure

- `mapsurvey/` - Django project settings and root URL configuration
- `survey/` - Main application with all business logic

### Core Data Model Hierarchy

```
Organization
└── SurveyHeader (survey definition)
    ├── SurveySection (logical groupings with map position)
    │   ├── Question (supports 12+ input types including GIS)
    │   └── OptionGroup → OptionChoice (reusable choice sets)
    └── SurveySession (user's survey attempt)
        └── Answer (stores responses with GIS geometry fields)
```

### Key Patterns

**Dynamic Form Generation**: `SurveySectionAnswerForm` in `survey/forms.py` dynamically builds form fields based on question `input_type`. Each type maps to specific Django fields and custom Leaflet widgets for GIS input.

**Question Types**: `text`, `text_line`, `number`, `choice`, `multichoice`, `range`, `rating`, `datetime`, `point`, `line`, `polygon`, `image`, `html`

**Creator rich text (`Question.subtext`, `SurveySection.subheading`, `SurveyHeader.thanks_html`)**:
everything a creator writes in their own words is authored in Quill and rendered to respondents as
markup. All of it is unbounded `TextField` and all of it passes `survey/html_sanitize.py` on the way
in — `QuestionForm.clean()`, `SurveySectionForm.clean_subheading()`, the translation savers in
`editor_views.py`, `serialization._import_rich_text()` (ZIP import, which is also how AI generation
writes), and `editor_question_preview_live` so the preview equals what a save keeps. **A new way to
write these fields must go through the same helper**; the allow-list is what stands between a
creator and stored XSS on every respondent.

Use `coerce_creator_html`, not `sanitize_creator_html`, anywhere a value might not be from an
editor. These fields hold plain text from before the editors existed (old rows, old ZIPs, AI
drafts), and `nh3` would read "takes <5 minutes" as an unknown tag and delete it; `coerce_` escapes
what carries no creator markup and sanitizes what does. Migration `0056` did the same one-off pass
over the rows already in the database.

The **Formatted Text block (`html`)** is the extreme case: it collects nothing and its `subtext` IS
the whole body, rendered `|safe` in `html_text.html`. `Question.name` for `html` and `image` is an
editor-only label that never reaches the respondent (see the `question-subtext` spec).

**Reference overlay layers (`SurveyMapLayer`, kill switch `MAP_REFERENCE_LAYERS`)**: creator-uploaded
GeoJSON rendered read-only beneath answer geometry on four surfaces — the respondent map, the editor
preview, the Responses **Map pane**, its **Overview thumbnail** and the per-response **map modal**
(the 200-px drawer thumbnail stays bare). One styling source: `partials/ref_layer_factory.html` (`window.RefLayerFactory.build`)
is included before any consumer; `partials/reference_layers.html` (respondent) and
`editor/partials/analytics_geo_map.html` (Responses) only fetch and place what it builds. Metadata
comes from `survey/layers.py::build_map_layers_metadata`, geometry only from the gated endpoint
`survey_layer_geojson` — never inlined. That endpoint admits any collaborator with the `viewer`
role or above in every survey status (a closed survey is where responses get read); outsiders
still go through `check_survey_access`, which is deliberately untouched. On Responses, layers are
non-interactive whatever `show_popups` says, ignore per-section `hidden_layers` (the map
aggregates all sections), and make the Map pane render even with zero geo answers. On the Map
pane they are `reference` slots of the `LayerManager`, listed in a titled group beneath the
answer layers in the Layers panel (own pane each, so stacking = panel order, never fetch order);
order, visibility and opacity persist in `localStorage['rv2RefLayers:<uuid>']` — browser-only,
never the model. Cap: `MAX_LAYERS_PER_SURVEY = 10`.

**Layer objects (`LayerObject`, `LayerObjectAsset`; change `overlay-features`)**: a layer is a
container of objects — key, title, category, rich-text description, link, one-part geometry,
raw imported properties, ordered attachments (image/audio/document/video files on the PUBLIC
media tier under random `layer_assets/<uuid>` keys, or YouTube/Vimeo embeds). `SurveyMapLayer.geojson`
is a CACHE derived from them (`survey/layers.py::rebuild_layer`, reserved `_key/_title/_category/
_has_content/_cover` properties) — never edit it as a source; `geojson_legacy` holds the FD-1 text
until one release after migration `0068` and then goes. Layers are owned by the CANONICAL survey
and borrowed by draft copies and archived versions through `layers_for()`/`layer_owner()`; nothing
copies them, so an object edit on a published survey is live for respondents (the object editor
says so in a banner). The object editor is a full page, `/editor/surveys/<uuid>/layers/<id>/edit/`
(`survey/layer_object_views.py`, `js/layer_editor.js`), with three ways in — draw, import GeoJSON,
import CSV — plus content CSV and photo batches matched by key, then title. Per-object cards for
respondents come from `survey_layer_object` under the same gate as the layer endpoint.

**Objects on the map (`layer_objects`) and `thumbs`**: `layer_objects` is a question type bound to
one layer (`Question.layer`, PROTECT — the settings card refuses to delete a bound layer and names
the question); `min_objects` replaces `required`. **Sub-questions are the one mechanism** for "ask
about an object on the map", shared by geo questions and `layer_objects` (`PARENT_TYPES`), with two
entry points into the same modal: the *Sub-questions* section inside the question modal and the
"+ Add Sub-question" button under the question. A geo question with no sub-questions is a normal
state — hint, never block. Respondent side = variant A: the panel list (`partials/layer_objects_block.html`)
is navigation; a row or a feature opens the SAME Leaflet popup respondent-placed features use, with
the object card + the sub-question form + ✓, and nothing opens while a draw/crosshair mode is
active. Answers about objects are rows on the sub-questions with `Answer.layer_object` set (partial
unique per session/sub-question/object) and NEVER `parent_answer_id`; they post as `obj__<key>__<code>`
fields. `thumbs` (👍/👎) is a choice type with the fixed `THUMBS_CHOICES` (`1=up`, `0=down`), so
every choice consumer works unchanged. Aggregates on every read surface come from one place,
`survey/object_stats.py`. Variant B (object card in the panel, geo popups moved there too) is
deferred as a future alternative view — do not reintroduce it ad hoc.

**Hierarchical Questions/Answers**: Both Question and Answer models support self-referential parent relationships via `parent_question_id` and `parent_answer_id` for conditional sub-questions.

**Conditional visibility (`CONDITIONAL_VISIBILITY` kill switch, default ON)**: a
`visibility_rule` JSONField on `Question` and `SurveySection` (`{"question_code", "choice_codes"}`,
any-of match on an earlier `choice`/`multichoice` answer) drives who sees what. One engine —
`survey/visibility.py` — feeds the respondent form, POST discard/purge, section navigation,
progress, and the editor badges/lint, so runtime and editor can never disagree. Hidden ⇒ never
required, submitted answers discarded, abandoned branches purged server-side. Broken rules fail
OPEN (shown to everyone) and are badged in the editor. Rules ride ZIP export/import
(`_apply_visibility_rules` drops unresolvable ones with a report line) and duplication
(`cloning.py` remaps intra-section controllers; cross-survey paste drops the rule). Do NOT reuse
`parent_question_id` for visibility — that relation means "geo popup sub-question". Env var off ⇒
rules stored but inert, editor hides the Visibility block.

**Shared map (`question`-sourced reference layers)**: a `SurveyMapLayer` with
`source='question'` holds no creator objects — its `LayerObject`s are MATERIALISED from
respondents' answers to the geo question named by `source_question_code` (a code, not a FK:
layers belong to the canonical survey, question rows are copied per version). Materialisation
runs at the end of the section POST (`layers.sync_question_layers_for_session`) and keys
objects `s<session>-<n>`, never by answer id, because the POST deletes and re-inserts a
session's answers on every submit and a re-keyed object would lose the reactions other
respondents left on it. Respondents get `build_question_layer_geojson` per request
(`no-store`, own marks omitted, only `status='visible'` from clean sessions); creator
surfaces read the cached `layer.geojson` (every status, clean sessions) rebuilt on
materialisation, moderation and session-status changes. Reactions are ordinary answers to
the sub-questions of an "Objects on the map" question bound to that layer; `show_tallies`,
`show_comments`, `approve_first` on the layer decide what other respondents see, and
`LayerObject.status` / `Answer.hidden` are the creator's per-item moderation. The object
editor is read-only for such layers; deleting the source geo question is refused.

**Session Management**: Survey sessions are created on first section view and tracked via `request.session['survey_session_id']`.

**Data Export** (`download_data` view): Exports survey responses as ZIP containing:
- GeoJSON files for each geo-question (point/line/polygon)
- CSV file for non-geographic data

**Public results page**: Creators expose aggregated results at `/r/<slug>/` via `PublicResultsPage` (1:1 with `SurveyHeader`) + ordered `PublicResultsBlock`s. Config tab at `/editor/surveys/<uuid>/public-results/`. Rendering logic in `survey/public_results.py` (`PublicResultsService`, `render_page_data`, `freeze_page`/`unfreeze_page`); editor views in `survey/public_results_editor.py`. Aggregates run over CLEAN sessions only (not deleted, excludes `not_approved`/`on_hold`) across the canonical survey + all versions. Privacy: k-anonymity masks buckets `<K` (default 3); geo popups expose only creator-selected `geo_label_fields`; individual free-text answers are never published. Hybrid `live` (60s cache) vs `frozen` (snapshot) mode. Visibility `public` (indexed, in sitemap) vs `unlisted` (noindex). The page config is intentionally NOT included in survey ZIP export/import.

**Mobile-adaptive layouts (two kill switches)**: `MOBILE_EDITOR_NAV` gives the editor
two-level contextual navigation below 768px: top strip = page tabs, bottom bar = panes of
the active page — Survey and Public results share the Structure/Edit/Preview vocabulary,
Responses gets Overview/Map/Responses/Perf under `RESPONSES_V2` (legacy switch-off:
Table/Map/Charts/Perf) (chrome in `editor/partials/_mobile_nav.html` +
`css/editor-mobile.css` + `js/editor_mobile_nav.js`; double-gated by the
`mobile-nav-enabled` body class AND the media query, so desktop is untouched; the Preview
pane is a full-screen overlay with a back button). `EDITOR_AUTOSAVE` replaces Save/Apply on
question EDIT forms with debounced autosave + a loud saved/saving/error indicator on ALL
viewports (autosave POSTs carry `autosave=1`, validation errors return 422 JSON so the
typed-in form is never re-rendered); new-question forms keep an explicit Create button.
Both default ON since PR #108 (owner decision); setting the env var to
False serves the pre-change layout, which is the rollback story. The RESPONDENT
survey page was deliberately left as-is: a bottom-sheet variant was built, reviewed and
REMOVED (2026-08-23) — the owner kept the legacy panel/crosshair flow; do not reintroduce
a sheet without an explicitly approved respondent-flow mockup. Touch reorder uses
SortableJS `delay:300 + delayOnTouchOnly` (long-press) — do not add ▲▼ reorder buttons.
Leaflet.draw tooltips pick tap-phrased strings via `pointer: coarse`
(`survey/templatetags/i18n_extras.py`).

**Registration abuse prevention**: `/accounts/register/` is served by `AbuseProtectedRegistrationView` (subclass of `AsyncEmailRegistrationView`). Three layered defenses run in order: honeypot field `website` (silent fake-success redirect), per-IP rate limit (`django-ratelimit`, fail-open on Redis outage), Cloudflare Turnstile siteverify (fail-closed on network error, dev-bypass when `TURNSTILE_SECRET_KEY=""`). Helpers in `survey/abuse.py`. Audit log in `AbuseEvent` model. Real client IP via `survey.middleware.CloudflareIPMiddleware` reading `CF-Connecting-IP` only when `CLOUDFLARE_TRUSTED=True`.

**Acquisition metrics (top of the funnel)**: the staff funnel dashboard at
`/admin/survey/funnelreport/` shows Google impressions → landing visits → registrations → demo
opens above the registration-onward stages. External numbers are never fetched during a request:
`python manage.py sync_acquisition_metrics [--days N] [--source gsc|plausible]` pulls Search Console
and Plausible into `AcquisitionDaily` (keyed by source/date/segment, re-runnable — a rerun overwrites
the window, which is how GSC's retroactive revisions land). Run daily by the
`mapsurvey-acquisition-sync` cron service; the provider keys live only on that service. Clients in
`survey/acquisition.py`, dashboard aggregation in `survey/funnel.py` (`AcquisitionService`).
Per-source state in `AcquisitionSyncState` surfaces "not configured" / "failing" / stale on the
dashboard itself, so a stalled sync is visible where the numbers are read. GSC's "marketing pages"
segment is defined by *excluding* `ACQUISITION_NON_MARKETING_PREFIXES` (`/surveys/` above all — those
impressions are customers' respondents finding their own survey). **GSC aggregation gotcha**: Search
Console counts impressions property-level when no page filter is present and page-level when one is,
and the totals differ (1329 vs 1717 over the same 14 days). Both segments therefore query *with* a
page filter — the whole-property one uses a match-everything expression solely to stay in page-level
mode. Never drop that filter: mixing modes makes the marketing segment exceed the whole property. Our
stored whole-property number reads higher than the GSC UI's total for the same window, by design. Demo opens: total from
`SurveySession` on the `DEMO_SURVEY_URL` survey (retroactive), anonymous/signed-in split from
`DemoOpen` (forward-only; the user FK lives there and never on `SurveySession`, which must not link
customers' respondents to platform accounts).

**Internal product analytics (PostHog)**: client-side snippet in
`survey/templates/partials/_analytics.html`, gated by `POSTHOG_PROJECT_KEY` (empty default = nothing
renders, which is what keeps tests, local dev and PR previews out of the production project) and
`POSTHOG_API_HOST` (Cloud EU). It measures **us**: which creator-facing screens get used, where
activation leaks. Plausible still runs alongside it and is not being replaced yet.

**Two hosts, on purpose.** The browser initialises against `POSTHOG_CLIENT_HOST` — a first-party
hostname CNAME'd to PostHog's managed reverse proxy, because `eu.i.posthog.com` is on every
mainstream blocklist and our creator audience runs blockers more than most. The server-side client
(`survey/apps.py`, and through it the middleware and the Celery receiver) keeps using
`POSTHOG_API_HOST` directly: no ad blocker runs inside our containers, so proxying error capture
would only add a DNS record and a CDN edge to the subsystem that must survive an outage. Empty
`POSTHOG_CLIENT_HOST` falls back to `POSTHOG_API_HOST`, and that fallback lives in the context
processor rather than in `settings.py` — resolving it at import time would freeze the value and
leave the browser on a stale host whenever the API host is overridden. `ui_host` is pinned to
`https://eu.posthog.com` because a custom `api_host` leaves the SDK unable to find the PostHog app.
Note the snippet derives its asset host by string-replacing `.i.posthog.com`, which is a no-op
against a proxy domain — so `array.js` correctly loads from the proxy too.

Two rules that are easy to get wrong:

- **PostHog never loads on respondent surfaces.** Two settings enforce one rule, both read in
  `survey.context_processors.analytics` — *not* by omitting the include from
  `base_survey_template.html`, since an omission would be invisible in review and a new base
  template would inherit whatever its author happened to copy.
  `POSTHOG_EXCLUDED_PREFIXES` (`/surveys/`, `/r/`) covers respondent URLs.
  `POSTHOG_EXCLUDED_VIEW_NAMES` (`editor_section_preview`, `editor_survey_thanks_preview`) covers
  the ones no prefix can express: the editor's Live preview frames a real respondent page served
  from under `/editor/`, where the surrounding page *is* tracked. That iframe used to run a
  second PostHog client in the creator's tab — one session with two recorders, so session replay
  alternated between the iframe's ~470px viewport and the editor's ~1600px one, and 1169 of 1799
  editor `$pageview`s over seven days were iframe loads rather than people. `_analytics.html` also
  refuses to `posthog.init()` when `window.top !== window.self`, which catches framed surfaces
  added after the view-name list. `editor_question_preview_live` and `public_results_preview`
  render standalone templates that include no analytics partial, which is why they are absent
  from the list — a new preview view that extends a base template must be added to it.
- **`SurveyEvent`/`TrackedLink`/`survey/events.py`/`PerformanceAnalyticsService` are a different
  system and must never be folded into PostHog.** They measure our *customers'* respondents on the
  customer's behalf (section funnel, referrer buckets, UTM campaigns, page load) and are a feature we
  sell. That data stays in our database. The two answer superficially similar questions about
  entirely different people.

**Error tracking (PostHog, same key)**: three capture paths — Django view exceptions via
`posthog.integrations.django.PosthogContextMiddleware` (in `MIDDLEWARE` after auth), Celery task
failures via the `task_failure` receiver in `mapsurvey/celery.py`, and client-side JS exception
autocapture (a PostHog project setting, not a template change). Unset key = the client is explicitly
disabled in `survey.apps.SurveyConfig`. Errors on `/surveys/`/`/r/` ARE captured (they are our
defects) but scrubbed by `_posthog_scrub_tags` in `settings.py` — no respondent IP/user-agent, URL
truncated to the prefix; `/admin/` and `/__debug__/` are not captured at all. The `posthog` package
is pinned `~=6.9`: 7.x needs Python ≥3.10, and 6.7.5–6.7.13 shipped with silently broken Django
exception capture — canary tests in `PostHogErrorTrackingTest` guard both directions.

### URL Structure

- `/` - Redirects to login or editor
- `/editor/` - Dashboard for authenticated users
- `/surveys/` - Public survey list
- `/surveys/<name>/` - Survey entry (redirects to first section)
- `/surveys/<name>/<section>/` - Survey section form
- `/surveys/<name>/download` - Export data as ZIP
- `/r/<slug>/` - Public survey results page (aggregated, read-only)
- `/admin/` - Django admin (surveys configured entirely here)

### Environment Variables

Required in `.env`:
- `SECRET_KEY`, `DEBUG`, `DJANGO_ALLOWED_HOSTS`
- Database: `SQL_ENGINE`, `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD`, `SQL_HOST`, `SQL_PORT`
- Optional S3: `USE_S3=TRUE`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`
- Acquisition metrics (optional; unset = "not configured" on the dashboard, never a zero):
  `GSC_SITE`, `GSC_SERVICE_ACCOUNT_JSON` (key contents; production) or `GSC_KEY` (key file path;
  local dev), `PLAUSIBLE_API_KEY`, `PLAUSIBLE_SITE_ID`. See `.env.example`. **This repo is public**
  — no key path is defaulted in `settings.py`; keep the path in your gitignored `.env`

### GeoDjango Notes

- Database engine must be `django.contrib.gis.db.backends.postgis`
- Models use `PointField`, `LineStringField`, `PolygonField` from `django.contrib.gis.db.models`
- Admin uses `LeafletGeoAdmin` for map-based editing
- Custom Leaflet draw widgets in `survey/forms.py` for frontend geometry input

## Workflow: Spec Driven Development (OpenSpec)

This project uses **Spec Driven Development** via the `openspec` CLI. All changes go through the artifact pipeline:

```
/opsx:new → /opsx:ff or /opsx:continue → /opsx:apply → /opsx:archive
```

**Key rule**: When asked to make changes or fix bugs, **always work through OpenSpec first**:
- If there is an active change related to the request — update its specs/design/tasks before editing code
- If no relevant change exists — create a new one (`/opsx:new`) before implementing

Never jump straight to code without a corresponding change in `openspec/changes/`.

## Project Management

**Task list**: See `TODO.md` for planned features and tasks
