## Context

The authorization layer (`api/`, #379) and the OAuth 2.1 server (#313) are merged. They authenticate
a bearer, compute rights (scope ∩ organisation role ∩ survey role), gate Pro per owning
organisation and rate-limit per token — but the only resource is `/api/v1/me`.

Survey editing lives in `survey/editor_views.py` (3 258 lines) and `editor_group_views.py`.
Validation sits in Django forms (`SurveyHeaderForm`, `SurveySectionForm`, `QuestionForm`), the
rules around it (`_guard_choice_codes`, `_edit_locks`, `_check_*_allowed`, `_parse_visibility_rule`,
`_save_*_translations`, `_rescreen_if_live`, `_refuse_if_answers_at_risk`) are module-private
functions of the views, and most of them read `request`. Lifecycle logic is half in
`versioning.py` (`clone_survey_for_draft`, `publish_draft`, `structural_*`), half inline in the
views (transition, discard). `audit()` reads actor and IP from the request. The extraction map is
the subagent report kept in the PR 1 description; its §8 quirks are addressed in D4.

Constraints: the repo is public; Pro is checked at the resource; the editor must not change
behaviour in PR 1 (the 55 k-line `survey/tests.py` is the regression net); a gunicorn worker keeps
its largest request's RSS (layer memory rules); MCP (#306) will be the second caller of the same
services.

## Goals / Non-Goals

**Goals:**
- One write path — `survey/services/` — for surveys, sections, questions, choices, order and the
  publish / close / unpublished-changes lifecycle, used by the editor and the API.
- A documented, versioned HTTP contract under `/api/v1/` with OpenAPI generated from the code.
- Every item of the issue's security checklist is a test.

**Non-Goals:**
- Question groups, duplicate, paste and move over the API (editor-only in v1; their views stay as
  they are). Layers are read-only over the API; the object editor stays the only writer of layer
  objects.
- Public results, webhooks, answer submission, API on Free.
- Rewriting the editor's templates or HTMX flow.

## Decisions

### D1. Services take an `Actor`, never a `request`

`survey/services/context.py`:

```python
@dataclass(frozen=True)
class Actor:
    user: User
    ip: str | None = None
    surface: str = 'editor'          # 'editor' | 'api' | 'mcp'

    @classmethod
    def from_request(cls, request, surface='editor'): ...
```

`audit.record(actor, action, survey=None, **metadata)` is the new writer; `audit(request, …)`
becomes a one-line wrapper so the 30-odd existing call sites stay. Services never read
`request.POST`, `request.active_org` or `request.session`; what those carried becomes an explicit
argument (`organization`, `group_id`, `acknowledge_answer_loss`, `acknowledge_translation_gaps`,
`force`).

*Alternative:* pass `request` into services. Rejected — the MCP server has no Django request of
the editor's shape, and a service that can read `POST` will.

### D2. The existing forms ARE the validators

A service validates by binding the same form the editor uses to a plain `data` dict
(`QuestionForm(data, files, instance=…, section=…, lock_structure=…)`) and raises
`ValidationFailed(fields)` from `form.errors`. That is the only way to guarantee the checklist item
"the editor and the API store the same bytes for the same input": `coerce_creator_html`,
`clean_redirect_url`, `allowed_display_styles`, the `layer_objects` one-layer rule, the
marker-icon validator, basemap rules all already live in `clean()`. The API layer converts its
pydantic body to the form's field names (`api/v1/forms_bridge.py`), including JSON
fields (`choices`, `validation_settings`, `visibility_rule`) which the form receives in the shape
the editor posts.

*Alternative:* pydantic validators duplicating the forms. Rejected — two validators drift, and
drift here is stored XSS.

### D3. Typed service errors, mapped per surface

`survey/services/errors.py`:

| Error | Carries | Editor maps to (unchanged) | API maps to |
|---|---|---|---|
| `ValidationFailed` | `fields: {name: [msg]}`, `form` | re-render / 422 JSON as today | `422 validation` + `fields` |
| `ContentLocked` | — | 403 | `409 draft_required` + `draft` uuid |
| `StructureLocked` | `reasons`, `draft` | 403 / `_structural_refusal` 422 | `409 draft_required` + `draft` uuid|null + `reasons` |
| `AnswersAtRisk` | `count` | 409 `answers_at_risk` | `409 answers_at_risk` + `count` |
| `DeleteBlocked` | `blockers` | 409 | `409 delete_blocked` |
| `TransitionRefused` | `message` | 400 text | `409 transition_refused` |
| `TranslationGaps` | `gaps` | 409 `translation_gaps` | `409 translation_gaps` |
| `IncompatibleDraft` | `issues` | 409 `issues` | `409 incompatible_draft` |
| `Conflict` | `message` | 400/409 as today | `409 conflict` |

The editor keeps an `_editor_response(err)` per view family so every status, body and header it
returns today is byte-identical (the regression suite is the proof).

### D4. Quirks: fixed only where the fix is invisible or is the API's contract

From the extraction map §8:
- **Atomicity** (create/edit/delete without `transaction.atomic`): every service runs in
  `transaction.atomic()`. Invisible to a passing request; removes half-written rows on failure.
- **Layer created before form validation** (`_resolve_layer_choice`): it now runs inside the
  service's transaction, so a refused save takes the new layer with it.
- **Section saved before the visibility error** is NOT a quirk: `LiveSurveyEditingTest` pins it
  (an autosave with a half-filled rule keeps the title). The editor keeps it by calling the
  service without the rule and answering 422 afterwards; the service itself, called with a rule
  (the API), validates the rule before writing anything.
- **Validation settings differ between create, edit and sub-question create**: one parser
  `questions.parse_validation_settings(input_type, data)` used by all three. A creator posting the
  create form with min/max now keeps them (the create modal does not post them today, so the editor
  is unaffected).
- **Status-only structural guard** (`_check_structural_edit_allowed`) stays exactly as is for the
  editor (it relies on the client routing structural edits to the draft). The service exposes
  `locks(survey) -> (content_locked, structure_locked)` (`_edit_locks` moved) and a
  `structural=True` flag on each operation; the API answers `409 draft_required` from it.
- **Unguarded `json.loads` / `int()` → 500**: services raise `ValidationFailed`; the editor maps it
  to the 400/422 it already uses for that endpoint. A 500 becoming a 400 is the one visible change,
  listed in the PR.
- **Audit written before the transition save**, **no draft-copy guard on transition**: kept for
  the editor (out of scope); the API refuses `publish`/`close` on a draft copy with
  `409 conflict` (use `/draft/publish`).

### D5. Strict visibility rules on the API only

`visibility.validate_rule(host_kind, host, rule)` (new, pure) checks that the controller exists,
comes earlier, is `choice`/`multichoice` (same pop-up for sub-questions) and that every
`choice_code` exists. The service takes `strict: bool` (it also refuses a posted change of a field the form locks on a live survey, which the editor silently ignores); the editor passes `False` (keeps
"broken rules fail open and are badged"), the API passes `True` and gets `422 validation` with
`fields.visibility_rule`. An agent learns the contract from the error; a creator's editor never
loses an in-progress rule.

### D6. django-ninja wiring, reusing the auth layer as is

```
api/v1/
  __init__.py      NinjaAPI(urls_namespace='api_v1', csrf=False, auth=BearerAuth(), docs_url=None)
  auth.py          BearerAuth(HttpBearer): authenticate(request,'api') → principal; limits.check_request
  deps.py          need(request, *scopes) / survey(request, uuid, role) / pro(...)
  errors.py        exception handlers: ApiError, ServiceError, ninja ValidationError, Exception
  pagination.py    signed cursor
  schemas/         pydantic In/Out per resource, ConfigDict(extra='forbid') on every In
  surveys.py sections.py questions.py layers.py imports.py responses.py me.py
```

- Auth class: ninja's `HttpBearer.authenticate()` is replaced by an override of `__call__` that
  calls `api.auth.authenticate(request, 'api')`, so personal and OAuth tokens, audiences, revocation,
  the per-IP failed-bearer budget and `last_used_at` are the existing code. Failure raises
  `api.errors.invalid_token()` so the envelope and `WWW-Authenticate` are the existing ones.
- Scopes are declared per route through a small decorator `@scoped(SURVEYS_WRITE)` that runs
  `rights.require_scope` before the body is parsed (the checklist: "a `surveys:read` token on POST
  → 403", even with an invalid body).
- `@api_endpoint` stays for non-ninja views (the protected-resource document is plain Django).
  `/api/v1/me` moves onto the router; `api.views.me` becomes the router function, same body.
- `Cache-Control: no-store` and CORS are set by `api.middleware.ApiResponseHeadersMiddleware` for
  every `/api/` response, so error paths ninja produces itself (405, 404 of an unknown route) carry
  them too. Unknown `/api/v1/…` routes answer the envelope `404 not_found`.
- OpenAPI: `/api/v1/openapi.json`, public (no auth; it is the contract), `security` on every
  operation via the global auth; the interactive docs page is not mounted (the help centre renders
  the reference). Error responses are declared per operation from one table so the reference lists
  every code.

*Alternative:* DRF. Rejected in the issue (serializer layer to keep in sync); ninja gives OpenAPI
from the same types we validate with.

### D7. Rights per route

Every route resolves the survey through `rights.survey_for(principal, uuid, min_role)` then
`gates.require_pro_api(principal, survey.organization)`, then nested ids through
`section_for` / `question_for` / a new `layer_for` (all filter by the survey). Roles mirror the
editor: reads `viewer`; section/question writes, thanks text and `POST /draft` `editor`; survey
settings, publish, close, draft publish/discard, delete `owner`. Scopes: reads `surveys:read`;
writes `surveys:write`; publish/close/draft-publish `surveys:publish`; delete `surveys:delete`;
responses/export `responses:read`. A role shortfall on an object the caller can see answers
`403 forbidden_role` (the survey is visible, so 404 hides nothing); invisible → 404.

Survey create and import name a workspace: `workspace` (slug) in the body, defaulting to the
token's bound workspace, else the user's only membership, else `422 validation`. The caller needs
org role `editor` there and the workspace must hold `api`.

### D8. Live surveys over the API

`PATCH` on a live survey's content (names, subtext, help text, translations, added options) is
applied in place exactly as the editor does — `_rescreen_if_live`, `LIVE_EDIT_SAVED` with
`surface='api'`. A structural change (type, add/delete/reorder, removing an answered option,
visibility rule, section code) answers `409 draft_required` with the existing draft's uuid or
`null`; the caller then `POST /surveys/{uuid}/draft` and edits that uuid. While a draft exists,
live content edits answer `409 draft_required` too (the editor refuses them for the same reason:
publishing the draft would overwrite them). The API never creates a draft on its own.

### D9. Pagination: signed cursor bound to its list

`cursor = signing.dumps({'l': list_key, 'k': last_pk}, salt='api.v1.cursor')`, where `list_key` is
`"surveys:<user>"` or `"responses:<survey uuid>"`. A cursor whose `l` differs or whose signature
fails → `400 bad_cursor`. `limit` defaults to 50, is clamped to `1..200` (never an error). Order is
by primary key, newest first, stable under inserts.

### D10. Export, layers and responses reuse the browser code paths

- Export: the body of `download_data` after the role check becomes
  `export.export_response(survey, fmt, version, include_all, completed_only, files)`; the view and
  the API both return it (`FileResponse` streaming, temp dir cleaned on close). The API emits
  `data_exported` with `surface='api'` and hits `limits.hit(p, 'export')`.
- Layer GeoJSON: the collaborator branch of `survey_layer_geojson` (cached text, ETag, gzip
  passthrough when `Accept-Encoding: gzip`) becomes `layers.cached_geojson_response(layer, request)`;
  the API is always a collaborator. The list path uses `layers_for(survey)` (defers
  `GEOMETRY_TEXT_FIELDS`) — extend `LayerMemoryDietTest` with the API URL.
- Responses: `analytics.nonempty_sessions` (or all with `include_empty=1`), `service.sequence_numbers()`
  for `#N`, answers serialised per session with top-level answers and their sub-answers nested
  under the geo feature they belong to; geometry as GeoJSON; never IP / user agent /
  `SurveyEvent` data. `limits` per token apply as for any read.

### D11. Protected-resource metadata and first-use event

`/.well-known/oauth-protected-resource/api/` (RFC 9728 path form for the resource
`API_RESOURCE_URLS['api']`) lists `resource`, `authorization_servers=[OAUTH_ISSUER]`,
`scopes_supported` from the registry, `bearer_methods_supported=["header"]`. The API's 401 adds
`resource_metadata="<that URL>"` to `WWW-Authenticate` (`invalid_token(resource_metadata=…)`; MCP
passes its own in #306). `api.auth.authenticate` already knows `first_use = last_used_at is None`;
it emits `api_token_first_use` (`token_id`, `kind`, `surface`) exactly then.

## Risks / Trade-offs

- [Refactor of the largest view file breaks a corner the suite misses] → PR 1 is editor-only,
  one service family per commit, full `survey` suite + `test_question_groups` after each, plus
  `tests_e2e` lifecycle/section/question CRUD once before the PR; HTMX headers are asserted by
  existing tests.
- [Forms as validators carry editor-only assumptions (`section=` querysets, flags filtering types)]
  → the bridge always passes `section`; a type the editor would hide (e.g. `FILE_UPLOAD_QUESTIONS`
  off) is refused the same way over the API, which is the right answer.
- [`extra='forbid'` makes adding a field a breaking change for strict clients] → it only
  affects INPUT; output may grow. Documented in the reference ("responses may gain fields").
- [Export over the API is heavy (ogr2ogr, temp files)] → `cap.export` 100/day per token already
  exists; same code path as the browser, same memory profile.
- [ninja + pydantic add import time to every worker] → measured once in PR 2 (worker boot), no
  lazy-loading heroics unless it is > 200 ms.
- [The API's strict visibility check refuses something the editor accepts] → intended (D5);
  the error names the field and reason.

## Migration Plan

PR 1 (services) merges and deploys alone; rollback = revert, no data change. PR 2 adds a
dependency and routes only; rollback = revert. No migrations in either. After PR 2 deploys: run a curl smoke against production with a personal token
on a Pro workspace (`/me`, list, create in a test workspace, delete), publish the help pages.

## Open Questions

- None blocking. Deferred to #306: whether MCP calls services directly or the REST routes
  (default: services directly, with `Actor(surface='mcp')`).
