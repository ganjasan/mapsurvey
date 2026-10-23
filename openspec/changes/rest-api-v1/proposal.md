## Why

Every programmatic path into a survey today is a hand-made one — ZIP import, `download_data`, a
management command. A planner's GIS pipeline, a consultancy's reporting script, a QGIS plug-in or
an AI agent need a documented HTTP contract. The authorization layer (#379) and the OAuth 2.1
server (#313) are merged and issue tokens that nothing but `/api/v1/me` accepts yet; the REST API
is the first real resource server on them, and the place where survey editing gets ONE
implementation that the MCP server (#306) can reuse instead of re-implementing the editor's rules.

Issue #380, item 3 of epic #378. Pro feature (`api`).

## What Changes

Delivered in two PRs under this one change.

**PR 1 — service layer (editor only, no behaviour change).**
- New package `survey/services/` (`surveys.py`, `sections.py`, `questions.py`, `publishing.py`)
  holding every write the editor makes to a survey, section, question, choice list, order and the
  publish / close / unpublished-changes lifecycle, with every rule applied once: `coerce_creator_html`,
  `clean_redirect_url`, `normalize_style`, `normalise_choice_extras`, visibility-rule validation,
  the live-survey content/structure split (`is_live`, `structural_*`), `screen_survey` /
  `_rescreen_if_live`, `AuditLog`, group order bookkeeping.
- The editor views call the services and keep only request parsing, role checks and rendering.
  Services take plain values and a user, never a `request`, and raise typed service errors the
  editor maps to its current responses (403 / 409 / form errors) unchanged.
- Full `survey` suite green with no test edited for behaviour; new service-level tests.

**PR 2 — REST API v1.**
- `django-ninja` mounted at `/api/v1/`, OpenAPI at `/api/v1/openapi.json`, an auth class over
  `api.auth.authenticate(request, 'api')`; scopes, `require_pro_api`, `limits` and the existing
  error envelope on every route. `/api/v1/me` re-homed onto the router, contract unchanged.
- Resources: surveys (list/create/get/patch/delete, publish, close, draft, draft/publish),
  sections and questions (CRUD, order, choices), layers (metadata; GeoJSON with gzip passthrough),
  ZIP import as a job, responses (paginated, non-empty by default) and export in every
  `download_data` format.
- Allow-list input schemas (unknown field ⇒ `422` naming it), cursor pagination (`limit ≤ 200`),
  new error codes `validation`, `draft_required`, `structure_locked`, `bad_cursor`.
- CORS `*` without credentials on `/api/`; `/.well-known/oauth-protected-resource` for the API
  resource and `WWW-Authenticate … resource_metadata=` on 401.
- Help centre: generated API reference + "Getting started with the API" guide; changelog entry;
  PostHog `api_token_first_use` once per token (no per-call event).

## Capabilities

### New Capabilities
- `survey-service-layer`: the one write path for surveys, sections, questions and the publish
  lifecycle, shared by the editor and every programmatic client; which rules it owns and its
  typed errors.
- `rest-api-v1`: the HTTP contract under `/api/v1/` — resources, schemas as allow-lists, error
  codes, pagination, CORS, Pro/scope/role checks per route, OpenAPI document, protected-resource
  metadata, responses and export over the API, PostHog first-use event.

### Modified Capabilities
- `creator-distribution-events`: `data_exported` also fires for API exports, with `surface="api"`.
- `api-authentication`: the v1 `401` challenge names the RFC 9728 metadata; a wrong method without a
  valid bearer is still `401` first (`405 method_not_allowed` with one).

## Impact

- **Code:** new `survey/services/`; `survey/editor_views.py`, `survey/editor_group_views.py`,
  `survey/views.py` (create/transition paths) slimmed onto it; new `api/v1/` (router, schemas,
  pagination, per-resource modules); `api/urls.py`; `mapsurvey/urls.py`.
- **Dependencies:** `django-ninja ~=1.7` (pydantic 2 is already in the lock).
- **Tests:** `survey` suite unchanged and green after PR 1; new `survey/tests/test_services_*`;
  `api/tests/test_v1_*` covering the issue's security checklist; `LayerMemoryDietTest` extended to
  the API list path.
- **Docs:** `api/README.md`, `help/` reference + guide, `survey/changelog/` entry, `CLAUDE.md`.
- **Ops:** no new env var, no migration. The Cloudflare skip rule from #313 covers
  `/.well-known/*` and `/oauth/*`; `/api/*` must be added to it so scripted clients and agents are
  not challenged.
