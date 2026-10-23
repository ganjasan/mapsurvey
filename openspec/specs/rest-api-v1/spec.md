# rest-api-v1 Specification

## Purpose
The HTTP contract under `/api/v1/` (django-ninja): resources, allow-list schemas, the error envelope and its codes, cursor pagination, CORS without credentials, Pro/scope/role checks per route, the public OpenAPI document and RFC 9728 metadata, responses and export over the API.
## Requirements
### Requirement: Versioned API under `/api/v1/` with a generated contract
The system SHALL serve the REST API under `/api/v1/` with `django-ninja`, and SHALL publish the
OpenAPI document at `/api/v1/openapi.json` without authentication. Every operation in it SHALL
carry a bearer `security` requirement (except the document itself), and the document SHALL list,
per operation, the error codes it can return. `GET /api/v1/me` SHALL be served by the same router
with the body defined in `api-access-rights`.

#### Scenario: OpenAPI validates
- **WHEN** `/api/v1/openapi.json` is fetched and validated as OpenAPI 3.1
- **THEN** it is valid and every operation has a bearer `security` entry

#### Scenario: Reference lists the codes
- **WHEN** the document is read
- **THEN** the union of declared error codes includes `invalid_token`, `scope_missing`,
  `pro_required`, `forbidden_role`, `not_found`, `validation`, `draft_required`,
  `answers_at_risk`, `translation_gaps`, `incompatible_draft`, `conflict`, `bad_cursor`,
  `rate_limited`, `server_error`

### Requirement: Every route authenticates, scopes, gates and limits through the auth layer
Every route SHALL obtain the principal from `api.auth.authenticate(request, 'api')` (bearer only,
audience `api`), check its declared scope before reading the body, resolve the survey with
`rights.survey_for` at the route's minimum role, check `gates.require_pro_api` on the survey's
organisation, and apply `limits.check_request`. Scopes: reads `surveys:read`; writes
`surveys:write`; publish, close and draft publish `surveys:publish`; delete `surveys:delete`;
responses and export `responses:read`. Roles: reads `viewer`; section, question, thanks text and
draft creation `editor`; survey settings, publish, close, draft publish/discard and delete
`owner`. A survey the caller cannot see SHALL be `404 not_found`; a visible survey with too low a
role SHALL be `403 forbidden_role`.

#### Scenario: Read-only token on a write
- **WHEN** a token with only `surveys:read` sends `POST /api/v1/surveys/{uuid}/sections` with any
  body
- **THEN** the response is `403 scope_missing` with `scope="surveys:write"`

#### Scenario: Missing responses scope
- **WHEN** a token without `responses:read` requests `/api/v1/surveys/{uuid}/responses`
- **THEN** the response is `403 scope_missing`

#### Scenario: Survey of another workspace
- **WHEN** a valid token requests a survey uuid in a workspace its user is not a member of
- **THEN** the response is `404 not_found`

#### Scenario: Viewer writes
- **WHEN** a `surveys:write` token whose user is a viewer on the survey patches a question
- **THEN** the response is `403 forbidden_role` and nothing is stored

#### Scenario: Free workspace
- **WHEN** a valid token reads a survey of a workspace without the `api` feature
- **THEN** the response is `403 pro_required` with that workspace's `upgrade_url`

### Requirement: Nested ids are resolved through their survey
Every section, question and layer id in a path SHALL be looked up filtered by the survey named in
the same path. An id that belongs to another survey SHALL be `404 not_found`.

#### Scenario: Question of another survey
- **WHEN** `PATCH /api/v1/surveys/{A}/questions/{q}` names a question of survey B the caller owns
- **THEN** the response is `404` and question q is unchanged

### Requirement: Resources of v1
The API SHALL offer:
- `GET /surveys` (paginated, the caller's surveys across workspaces holding `api`, with
  `hidden_by_plan`), `POST /surveys`, `GET/PATCH/DELETE /surveys/{uuid}`;
  `POST /surveys/{uuid}/publish`, `/close`, `/draft`, `/draft/publish`, `DELETE /surveys/{uuid}/draft`;
- `GET/POST /surveys/{uuid}/sections`, `GET/PATCH/DELETE /surveys/{uuid}/sections/{id}`,
  `PUT /surveys/{uuid}/sections/order`;
- `GET/POST /surveys/{uuid}/sections/{id}/questions`, `PUT /surveys/{uuid}/sections/{id}/questions/order`,
  `GET/PATCH/DELETE /surveys/{uuid}/questions/{id}`, `PUT /surveys/{uuid}/questions/{id}/choices`,
  `POST /surveys/{uuid}/questions/{id}/subquestions`;
- `GET /surveys/{uuid}/layers`, `GET /surveys/{uuid}/layers/{id}/geojson`;
- `POST /surveys/import`, `GET /import-jobs/{id}`;
- `GET /surveys/{uuid}/responses`, `GET /surveys/{uuid}/export`;
- `GET /me`.
Every write SHALL call `survey/services/` (or the import job / export code), never a model.

#### Scenario: Create, fill, publish
- **WHEN** a Pro token with `surveys:write` and `surveys:publish` creates a survey, adds a section
  and a choice question with two options, then publishes
- **THEN** each call succeeds, `GET /surveys/{uuid}` shows `status="published"`, and the survey is
  answerable at its public URL

#### Scenario: Delete moves to trash
- **WHEN** a `surveys:delete` owner token deletes a survey
- **THEN** the survey is trashed (restorable in the editor), an `AuditLog` `survey_trash` row
  exists, and `GET` on it answers `404`

### Requirement: Input schemas are allow-lists
Every input schema SHALL name each writable field and refuse any other with `422 validation`
listing the unknown names in `fields`. `organization`, `status`, `owner`, `created_by`,
`geojson`, `geojson_gz`, ids and timestamps SHALL never be writable. Rich-text fields
(`subtext`, `subheading`, `thanks_html`) SHALL be stored only after the service's
`coerce_creator_html`; `redirect_url` SHALL be `"#"` or an absolute http(s) URL; `input_type` SHALL
be a known type; `icon_class` SHALL pass the marker-icon validator; `visibility_rule` SHALL pass
the strict rule check (controller exists, is earlier, is a choice type, every choice code exists).

#### Scenario: Forbidden fields
- **WHEN** `PATCH /surveys/{uuid}` carries `{"name": "x", "organization": 5, "status": "published"}`
- **THEN** the response is `422 validation` with `fields` naming `organization` and `status`, and
  the survey is unchanged

#### Scenario: Script in subtext
- **WHEN** a question is patched with `subtext="<script>alert(1)</script><b>ok</b>"`
- **THEN** the stored value equals what the editor's `QuestionForm.clean()` stores for the same input

#### Scenario: Bad redirect URLs
- **WHEN** `redirect_url` is `"#https://example.org"`, `"javascript:alert(1)"` or `"#thanks"`
- **THEN** each answers `422 validation` with `fields.redirect_url`

#### Scenario: Rule naming a later question
- **WHEN** a question's `visibility_rule` names a controller that comes after it
- **THEN** the response is `422 validation` with `fields.visibility_rule`

### Requirement: Live surveys answer `draft_required` for structure
On a published or closed survey the API SHALL apply content changes in place (re-screening the
survey) and SHALL answer a structural change — type, layer binding, add, delete or reorder of
sections/questions, removing an answered option, visibility rule, section code — with
`409 draft_required` carrying `draft` (the unpublished-changes uuid or `null`) and `reasons`.
While unpublished changes exist, any change to the live survey SHALL answer `409 draft_required`.
The API SHALL never create a draft unasked.

#### Scenario: Structural edit on a published survey
- **WHEN** `POST /surveys/{uuid}/sections` targets a published survey without a draft
- **THEN** the response is `409 draft_required` with `draft=null` and no section exists

#### Scenario: Content edit on a published survey
- **WHEN** a question's `name` is patched on a published survey without a draft
- **THEN** it is stored and content screening runs

#### Scenario: Work on the draft
- **WHEN** the caller `POST /surveys/{uuid}/draft`, adds a section to the returned uuid and
  `POST /surveys/{uuid}/draft/publish`
- **THEN** the live survey has the new section and a new version number

### Requirement: Publishing reports content review
`POST /surveys/{uuid}/publish` SHALL answer the survey with `status` and `review`
(`"pending"` when content screening held it, else `null`). It SHALL answer
`409 translation_gaps` with the gaps unless the body has `"acknowledge_translation_gaps": true`.
Publishing or closing a draft copy SHALL answer `409 conflict`.

#### Scenario: Held survey
- **WHEN** a survey whose text scores above the hold threshold is published through the API
- **THEN** the response has `status="published"` and `review="pending"`, a `ContentReview` is
  pending, and the respondent URL serves the unavailable page

### Requirement: One error envelope
Every error SHALL be `{"error": "<code>", "detail": "<text>", ...}` with optional `fields`, using
the stable codes of this spec and `api-authentication`, with `Cache-Control: no-store`. An
unexpected exception SHALL answer `500 server_error` with no traceback and no model name, and
SHALL be captured in PostHog without the bearer value. An unknown route under `/api/v1/` SHALL
answer `404 not_found` in the envelope.

#### Scenario: Server error
- **WHEN** a service raises an unexpected exception during a request
- **THEN** the body is `{"error": "server_error", "detail": ...}` without a traceback, and the
  PostHog `$exception` carries no `Authorization` header value

### Requirement: Cursor pagination
List endpoints SHALL page with `?cursor=` and `?limit=` (default 50, clamped to 1..200) and return
`{"items": [...], "next_cursor": <string|null>}`. Cursors SHALL be signed and bound to their list;
a cursor from another list or survey, or a tampered one, SHALL answer `400 bad_cursor`.

#### Scenario: Limit clamped
- **WHEN** `?limit=10000` is requested
- **THEN** at most 200 items are returned and no error is raised

#### Scenario: Cursor from another survey
- **WHEN** a `next_cursor` from survey A's responses is sent to survey B's responses
- **THEN** the response is `400 bad_cursor`

### Requirement: Responses and export over the API
`GET /surveys/{uuid}/responses` SHALL list non-empty sessions (all with `?include_empty=1`) of the
survey's version family, each with its Responses ordinal `#N`, timestamps, language, validation
status and answers keyed by question code (geometry as GeoJSON, sub-answers nested under their
feature), never sessions of another survey, never respondent IP or user agent, never `SurveyEvent`
data. `GET /surveys/{uuid}/export?format=` SHALL stream exactly what `download_data` streams for the
same parameters, count against `cap.export`, and emit `data_exported` with `surface="api"`.

#### Scenario: Export parity
- **WHEN** the API exports `format=xlsx` and the browser downloads `?format=xlsx` for the same survey
- **THEN** the two files have identical sheets and rows

#### Scenario: Empty sessions hidden by default
- **WHEN** a survey has one empty and one answered session
- **THEN** `/responses` lists one item, and two with `include_empty=1`

### Requirement: Layers are read-only and memory-safe
`GET /surveys/{uuid}/layers` SHALL return layer metadata without selecting `geojson_gz`.
`GET /surveys/{uuid}/layers/{id}/geojson` SHALL serve the cached collection, passing the stored
gzip bytes through with `Content-Encoding: gzip` when the client accepts gzip.

#### Scenario: List path never loads geometry
- **WHEN** the layers list is requested under `LayerMemoryDietTest`'s query capture
- **THEN** no captured query selects `geojson_gz`

### Requirement: Import as a job
`POST /surveys/import` (multipart `file`, optional `workspace`) SHALL store the archive as a
`SurveyImportJob`, enqueue `run_survey_import`, count against `cap.survey_import`, and answer
`202` with the job. `GET /import-jobs/{id}` SHALL show only the caller's own jobs (`404` otherwise)
with status, survey uuid when done, warnings or the error.

#### Scenario: Someone else's job
- **WHEN** user B requests user A's import job id
- **THEN** the response is `404`

### Requirement: CORS without credentials
Responses under `/api/` SHALL carry `Access-Control-Allow-Origin: *` and SHALL never carry
`Access-Control-Allow-Credentials`. An `OPTIONS` preflight SHALL answer `204` with the allowed
methods and the `Authorization, Content-Type` headers, without authentication.

#### Scenario: Preflight from another origin
- **WHEN** `OPTIONS /api/v1/surveys` arrives with `Origin: https://evil.example`
- **THEN** the response has `Access-Control-Allow-Origin: *` and no
  `Access-Control-Allow-Credentials` header

### Requirement: Protected-resource metadata
The system SHALL serve `/.well-known/oauth-protected-resource/api/` (RFC 9728) with `resource`
equal to `API_RESOURCE_URLS['api']`, `authorization_servers` `[OAUTH_ISSUER]`,
`scopes_supported` from the scopes registry and `bearer_methods_supported` `["header"]`, and every
`401` from `/api/v1/` SHALL add `resource_metadata="<that URL>"` to `WWW-Authenticate`.

#### Scenario: Unauthenticated call
- **WHEN** `/api/v1/surveys` is requested without a bearer
- **THEN** the response is `401 invalid_token` whose `WWW-Authenticate` names the metadata URL

### Requirement: Product analytics stays coarse
The API SHALL NOT emit a PostHog event per call. It SHALL emit `api_token_first_use`
(`token_id`, `kind`) once, on the first successful authentication of a token.

#### Scenario: Second call
- **WHEN** a token is used twice
- **THEN** exactly one `api_token_first_use` event exists for it
