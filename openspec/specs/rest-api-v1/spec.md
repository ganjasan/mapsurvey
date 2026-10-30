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

### Requirement: Share information
The API SHALL offer `GET /surveys/{uuid}/share` (scope `surveys:read`, role `viewer`) returning the
survey's `status` and `shareable` (true only when published). When shareable it SHALL return the
respondent URL, the embed snippet the Share page shows, the allowed embed hosts, and the public
results URL when that page is published. When the survey is in testing it SHALL return the test link
with its token to callers with the `editor` role or above, and to nobody else. URLs SHALL be built on
`SITE_URL`, the same way the editor builds them.

#### Scenario: Published survey
- **WHEN** a viewer's token asks for a published survey's share information
- **THEN** it gets `shareable: true`, the URL `<SITE_URL>/surveys/<uuid>/`, the embed snippet and the hosts

#### Scenario: Testing survey and the test link
- **WHEN** an editor and then a viewer ask for a testing survey's share information
- **THEN** the editor's answer carries `test_url` with `?token=` and the viewer's has `test_url: null`; both have `shareable: false`

### Requirement: QR code of a survey link
The API SHALL offer `GET /surveys/{uuid}/share/qr.svg` and `qr.png` (scope `surveys:read`) drawing
the respondent URL as a QR code on the server, with `size` (pixels per module, 1–40, default 10)
and optional `link` (a tracked link id of the survey, whose URL is drawn instead). A survey that is
not shareable SHALL answer `409 not_shareable`.

#### Scenario: PNG of the survey link
- **WHEN** `qr.png` is requested for a published survey
- **THEN** the response is `image/png` and decodes to the respondent URL

#### Scenario: Draft
- **WHEN** a QR is requested for a draft survey
- **THEN** the response is `409 not_shareable`

### Requirement: Tracked links over the API
The API SHALL list (`surveys:read`), create and delete (`surveys:write`, role `editor`) a survey's
tracked links on its canonical survey, each with `utm_source` (required), `utm_medium`,
`utm_campaign` (each at most 100 characters), its URL, and the responses `started` and `completed`
through it, counted the way the Responses page's traffic sources count them. A survey SHALL hold at
most 200 tracked links (`409 limit_reached` beyond). Creating and deleting SHALL be audited.

#### Scenario: Create and count
- **WHEN** an editor creates a link `utm_source=flyer` and one response then starts with those parameters
- **THEN** the list shows the link with its URL carrying `utm_source=flyer` and `started: 1`

#### Scenario: Viewer cannot create
- **WHEN** a viewer's token posts a tracked link
- **THEN** the response is `403 forbidden_role`

### Requirement: Embed hosts over the API
The API SHALL offer `PUT /surveys/{uuid}/share/embed-hosts` with `{"hosts": [...]}` (scope
`surveys:write`, role `editor`), validating through the editor's host rules; an invalid entry SHALL
answer `400 validation` naming it, an empty list SHALL mean any site, and the change SHALL be saved
on the canonical survey and audited.

#### Scenario: Invalid host
- **WHEN** the hosts are `["example.org", "not a host!"]`
- **THEN** the response is 400 naming `not a host!` and nothing is saved

### Requirement: Links the editor builds use the public base
The Share page's tracked-link URLs SHALL be built on the same public base as its respondent link,
never on `request.scheme`, so they are `https` behind the proxy; and tracked links SHALL belong to the
canonical survey whichever version the page was opened on.

#### Scenario: Behind the proxy
- **WHEN** the Share page renders behind a proxy that sends `X-Forwarded-Proto: https`
- **THEN** every tracked link starts with `https://`

### Requirement: One response scope for every read
The summary, text-answers, per-question GeoJSON and export-link routes SHALL count exactly the
sessions the export of the same parameters contains: the survey's version family (or one
`version`), no empty sessions, no deleted sessions and no `not_approved` sessions unless
`include_all=true`, and only completed sessions with `completed_only=true`. The set SHALL come from
the export's own helpers, never a second definition.

#### Scenario: Rejected response leaves the numbers
- **WHEN** a survey has three answered sessions and one is `not_approved`
- **THEN** the summary reports `responses: 2`, and `responses: 3` with `include_all=true`

#### Scenario: Summary equals the file
- **WHEN** the summary reports 12 answers to a choice question and the export of the same parameters is opened
- **THEN** the file holds 12 non-empty cells in that question's column

### Requirement: Response summary
`GET /surveys/{uuid}/responses/summary` (scope `responses:read`, survey role `viewer`) SHALL return
`responses`, `completed`, `completion_rate` and, for every question in section order except `html`
and `image` blocks, `id`, `code`, `section_id`, `name`, `type` and `answered`, plus: for choice,
multichoice, rating and thumbs questions every option with `code`, `label`, `count` and whether it is
still offered, and for questions with an "other" option the 50 most frequent write-in texts with
counts; for number and range `count`, `mean`, `median`, `min`, `max`; for rating also `mean`; for geo
questions `features` and the same statistics for each sub-question under `subquestions`; for
`layer_objects` one entry per object with its answer count and sub-question aggregates. It SHALL
accept `version`, `include_all` and `completed_only`.

#### Scenario: Choice with write-ins
- **WHEN** a choice question with an "other" option has answers `A`, `A`, `other: "bike lane"`, `other: "Bike lane "`
- **THEN** its entry lists `A` with count 2, the other option with count 2 and `other_texts: [{"text": "bike lane", "count": 2}]`

#### Scenario: Sub-questions of a point question
- **WHEN** a point question has 5 features and a multichoice sub-question answered on 4 of them
- **THEN** its entry has `features: 5` and a `subquestions` entry for the multichoice with `answered: 4` and its option counts

#### Scenario: Viewer can read, outsider cannot
- **WHEN** a survey viewer's token with `responses:read` asks, and then a token of a user without access asks
- **THEN** the first gets 200 and the second 404

### Requirement: Text answers of one question
`GET /surveys/{uuid}/questions/{id}/answers` (scope `responses:read`) SHALL list the non-blank text
answers of a text, text_line or sub-question over the response scope, newest first, each with the
response's ordinal `#N` and session id, cursor-paginated (default 50, max 200). For any other type
it SHALL answer `400 validation`.

#### Scenario: Paging texts
- **WHEN** a text question has 120 answers and the client asks with `limit=50`
- **THEN** it gets 50 items and a `next_cursor`, and three pages cover all 120

### Requirement: GeoJSON of one geo question
`GET /surveys/{uuid}/questions/{id}/geojson` (scope `responses:read`) SHALL return a CRS84
FeatureCollection of that geo question's answers across the version family over the response scope,
built by the export's collector: sub-question values as properties keyed by sub-question name, plus
`session`, `validation_status`, and for spray answers `dot_count` and `area_m2`. It SHALL stop at
5 000 features and then carry `truncated: true`. A non-geo question SHALL answer `400 validation`.

#### Scenario: Same properties as the export
- **WHEN** a polygon question with a sub-question "What is needed" is fetched
- **THEN** each feature has a `What is needed` property with the value the export's GeoJSON layer has

### Requirement: Signed export link
The API SHALL offer `POST /surveys/{uuid}/export-link` (scope `responses:read`, role `viewer`) with
`format`, `version`, `include_all`, `completed_only`, `files`, validate the format as the export does and return
`{url, expires_at}` for a link valid 15 minutes. `GET` on the link SHALL need no bearer, SHALL
re-check that the user still has the `viewer` role, that the survey's workspace has the API (Pro),
and that the token that created it is not revoked, SHALL count against `cap.export`, and SHALL
return exactly the file `download_data` returns for the same parameters. A tampered or expired link
SHALL answer `404`. Nothing about the link SHALL be stored.

#### Scenario: Link after revocation
- **WHEN** a link is created and the token that created it is revoked before the link is opened
- **THEN** opening the link answers 404 and no file is built

#### Scenario: Expired link
- **WHEN** the link is opened 16 minutes after it was created
- **THEN** the response is 404

### Requirement: Moderating a response
The API SHALL offer `PATCH /surveys/{uuid}/responses/{id}` with `{"validation_status": "approved" |
"not_approved" | "on_hold" | ""}`, requiring scope `responses:moderate` and survey role `editor`; a session outside
the survey's version family SHALL answer 404. It SHALL set the status through the editor's service
(which rebuilds shared-map layers), write an audit row with the session id and the old and new
status, and return the response as `list_responses` shows it.

#### Scenario: Reject a response
- **WHEN** an editor's token with `responses:moderate` sets `not_approved`
- **THEN** the session's status changes, an audit row records it, and the next summary no longer counts it

#### Scenario: Read-only token
- **WHEN** a token with only `responses:read` sends the PATCH
- **THEN** the response is `403 scope_missing` naming `responses:moderate`

### Requirement: Layers are memory-safe
`GET /surveys/{uuid}/layers` SHALL return layer metadata without selecting `geojson_gz`.
`GET /surveys/{uuid}/layers/{id}/geojson` SHALL serve the cached collection, passing the stored
gzip bytes through with `Content-Encoding: gzip` when the client accepts gzip. Layer and object
writes SHALL defer the geometry text the same way and SHALL never load a layer's `geojson` to change
its metadata.

#### Scenario: List path never loads geometry
- **WHEN** the layers list is requested under `LayerMemoryDietTest`'s query capture
- **THEN** no captured query selects `geojson_gz`

#### Scenario: Renaming a layer does not load its geometry
- **WHEN** a layer is renamed through the API under query capture
- **THEN** no captured query selects `geojson_gz`

### Requirement: Creating layers over the API
The API SHALL offer `POST /surveys/{uuid}/layers` (scope `surveys:write`, survey role `owner`)
taking a JSON body `{"name", "geojson"}`, and `POST /surveys/{uuid}/layers/upload` taking a multipart
`file` and `name`, validating either with
the editor's upload rules (at most 10 MB and 5 000 features, WGS84 coordinates only, Z dropped,
multi-part geometries split into one object per part) and creating the layer and its objects on the
canonical survey; without `geojson` or `file` it SHALL create an empty layer. A survey SHALL hold at
most 10 layers (`409 limit_reached`). The response SHALL be the layer with `live` saying whether
respondents see it now. The write SHALL be audited.

#### Scenario: Layer from inline GeoJSON
- **WHEN** an owner posts `{"name": "Benches", "geojson": <FeatureCollection of 3 points with a "name" property>}`
- **THEN** the response is 201 with `feature_count: 3` and the layer's objects are titled from `name`

#### Scenario: Projected coordinates
- **WHEN** the GeoJSON has coordinates in metres (e.g. `[392000, 5820000]`)
- **THEN** the response is `422 validation` saying to re-export as WGS84 and no layer exists

#### Scenario: Editor role is not enough
- **WHEN** a survey editor (not owner) posts a layer
- **THEN** the response is `403 forbidden_role`

### Requirement: Editing, ordering and deleting layers
`PATCH /surveys/{uuid}/layers/{id}` (owner) SHALL accept `name`, `color` (`#rrggbb`), `label_field`
and `key_field` (each a property of the layer or empty), `show_popups` and `style`, the style passing
`normalize_style`; a shared-map layer SHALL accept only name, color and style without a rule.
`PUT /surveys/{uuid}/layers/order` SHALL set the layers' order from a complete list of their ids.
`DELETE /surveys/{uuid}/layers/{id}` SHALL refuse a layer a question uses with `409 conflict` naming
the questions. Each write SHALL be audited.

#### Scenario: Style by category
- **WHEN** an owner patches `style.by = {"field": "kind", "mode": "categories", "classes": [...]}`
- **THEN** the stored style is the normalised one and the layer's `legend` lists the classes

#### Scenario: Layer in use
- **WHEN** an owner deletes a layer bound to the question "Rate these benches"
- **THEN** the response is 409 naming "Rate these benches" and the layer still exists

### Requirement: Layer objects over the API
The API SHALL list a layer's objects (`surveys:read`, cursor-paginated) and create, update and delete
them (`surveys:write`, owner) with `key` (unique in the layer, immutable after create), `title`,
`category`, `description` (through `coerce_creator_html`), `link` (http/https only), one-part
`geometry` and `properties`, within the layer's caps, rebuilding the layer after each write. Objects
of a shared-map layer SHALL be read-only (`409 conflict`). Each write SHALL be audited.

#### Scenario: Object with a script link
- **WHEN** an owner creates an object with `link: "javascript:alert(1)"`
- **THEN** the response is `422 validation` naming `link` and no object exists

#### Scenario: Duplicate key
- **WHEN** an object is created with a key the layer already has
- **THEN** the response is `409 conflict` and the existing object is unchanged

### Requirement: Shared maps and their moderation over the API
Question create and update SHALL accept `layer_from_answers: <code of a top-level geo question>`
instead of `layer_id`, creating or reusing that question's shared-map layer exactly as the editor
does (and refusing past 10 layers). `PATCH /surveys/{uuid}/layers/{id}/objects/{key}/status` with
`visible`, `pending` or `hidden` (scope `surveys:write`, role `editor`) SHALL moderate a mark of a
shared-map layer and rebuild it; on any other layer it SHALL answer `409 conflict`.

#### Scenario: Turn answers into a shared map
- **WHEN** an "Objects on the map" question is created with `layer_from_answers: "BENCH"` where BENCH is a point question
- **THEN** the question is bound to a layer with `source: "question"` and `source_question_code: "BENCH"`

#### Scenario: Hide a mark
- **WHEN** an editor sets a mark to `hidden`
- **THEN** the mark leaves the respondents' shared map at once

### Requirement: Question groups over the API
The API SHALL offer the following, with scope `surveys:read` for reads and `surveys:write` plus
survey role `editor` for writes:

- `GET /surveys/{uuid}/sections/{id}/groups` — top-level groups, and pop-up groups with `parent_id`.
- `POST /surveys/{uuid}/sections/{id}/groups` — takes `title`, `description`, `display_style`,
  `visibility_rule`, `translations`, an optional `parent_id` (a question with a pop-up) and an
  optional `question_ids`.
- `GET`, `PATCH` and `DELETE /surveys/{uuid}/groups/{id}`.

All writes SHALL go through the group service the editor uses.

- The description SHALL pass `coerce_creator_html`.
- `question_ids` SHALL become contiguous members at the place of the first listed question.
- Membership SHALL also be set through `PUT …/questions/order` items `{"g": id, "q": [ids]}`.
- `DELETE` SHALL keep the members in place, unless `with_questions=true`. That deletes them too and
  answers `409 answers_at_risk` while their answers exist without `acknowledge_answer_loss=true`.
- Questions SHALL carry `group_id`, and sections SHALL list their groups.

#### Scenario: Group three questions
- **WHEN** an editor posts `{"title": "About you", "display_style": "card", "question_ids": [q2, q3, q4]}` to a draft survey's section
- **THEN** the response is 201 with `question_ids: [q2, q3, q4]` and `GET` of the section shows the group in the position q2 had

#### Scenario: Live survey wording edit applies in place
- **WHEN** an editor patches a group's `title` on a published survey
- **THEN** the title changes on the live survey and an audit row `group_update` is written

#### Scenario: Live survey structural edit needs unpublished changes
- **WHEN** an editor creates a group or changes a group's `visibility_rule` on a published survey
- **THEN** the response is `409 draft_required` and nothing changes

#### Scenario: Delete with questions guards answers
- **WHEN** a group whose members have answers is deleted with `with_questions=true` and no acknowledgement
- **THEN** the response is `409 answers_at_risk` with the answer count and nothing is deleted

### Requirement: Duplicating and copying structure over the API
The API SHALL offer the following, with scope `surveys:write` and survey role `editor` on the
target:

- `POST /surveys/{uuid}/questions/{id}/duplicate` — the copy goes right after the source, in the
  source's group, with fresh codes and name suffix " (copy)", and with its sub-questions.
- `POST /surveys/{uuid}/sections/{id}/duplicate` — the copy goes right after the source.
- `POST /surveys/{uuid}/sections/{id}/questions/copy` with `{source_question_id, parent_id?}` —
  appends a copy of a question from any survey the caller can read.
- `POST /surveys/{uuid}/sections/copy` with `{source_section_id}` — appends a copy of a section.

Each copy SHALL carry every field the editor's copy carries. A copy into another survey SHALL get
its own stored files. Each SHALL be structural (`409 draft_required` on a live survey) and audited.

#### Scenario: Duplicate a question
- **WHEN** an editor duplicates a choice question with two sub-questions in a draft survey
- **THEN** the response is 201 with a new question right after the source, same options, two copied sub-questions and new codes

#### Scenario: Copy from another survey owns its image
- **WHEN** a question with an image is copied from survey A into survey B and survey A is then purged from the trash
- **THEN** the copy's image in survey B still opens

#### Scenario: Unreadable source
- **WHEN** the source question belongs to a survey the caller cannot read
- **THEN** the response is 404

### Requirement: Duplicating a whole survey over the API
`POST /surveys/{uuid}/duplicate` SHALL create a new draft survey in the same workspace, owned by the
caller. It SHALL need scope `surveys:write`, survey role `viewer` on the source, the workspace
`editor` role, Pro on the workspace, and the `survey_create` limit. The new survey SHALL be named
"<name> (copy)" and hold:

- every section, question, group, option, translation, visibility rule and setting of the source;
- copies of its layers: creator layers with their objects and attachments, shared-map layers
  without objects;
- question layer bindings remapped to the copied layers;
- stored files of its own.

It SHALL NOT copy sessions, answers, versions, tracked links, other collaborators, comments or the
public results page. More than 200 MB of files SHALL be refused with `409 limit_reached`.

#### Scenario: Copy a published survey with a layer
- **WHEN** an editor duplicates a published survey whose "Objects on the map" question is bound to a 30-object layer
- **THEN** the response is 201 with a new draft survey whose question is bound to its own 30-object layer, and the source is unchanged

#### Scenario: Responses stay behind
- **WHEN** a survey with 50 responses is duplicated
- **THEN** the copy has no sessions and no versions

#### Scenario: Every field travels
- **WHEN** `DuplicateSurveyKeepsFieldsTest` compares every concrete field of a fully populated source with its copy
- **THEN** every field is equal except the listed exclusions

### Requirement: Moving a question over the API
`POST /surveys/{uuid}/questions/{id}/move` SHALL take `section_id`, `parent_id` and `position` (all
optional) and `acknowledge_answer_loss`. It SHALL need scope `surveys:write` and survey role
`editor`. It SHALL move the question:

- to another section of the same survey, with its sub-questions and answers;
- between a section's top level and a pop-up, with the editor's refusals and answer-loss
  acknowledgement;
- or both.

The question SHALL leave its group. Visibility rules the move breaks SHALL be cleared and named in
`removed_rules`. The move SHALL be structural and audited.

#### Scenario: Move to another section keeps answers
- **WHEN** an answered top-level question is moved to the start of another section with `position: 0`
- **THEN** it is the first question of that section, its answers are still in `GET …/responses`, and no acknowledgement was asked

#### Scenario: Move breaks a rule
- **WHEN** a question that controls a later question's visibility is moved below that question
- **THEN** the rule is cleared and `removed_rules` names the later question

#### Scenario: Into a pop-up needs acknowledgement
- **WHEN** an answered question is moved into a pop-up without `acknowledge_answer_loss`
- **THEN** the response is `409 answers_at_risk` and nothing moves

### Requirement: Versions over the API
`GET /surveys/{uuid}/versions` (scope `surveys:read`) SHALL list the current survey first, then the
archived versions newest first. Each entry SHALL carry its number, status, publish date from the
audit log, section and question counts and non-empty response count.

`POST /surveys/{uuid}/versions/{n}/restore` (scope `surveys:write`, survey role `owner`) SHALL create
unpublished changes holding version n's questionnaire and answer 201 with their uuid. It SHALL
answer:

- `409 conflict` when unpublished changes exist;
- `409 transition_refused` when the survey is not published;
- 404 for an unknown version.

The restore SHALL be audited.

#### Scenario: Roll back a bad publish
- **WHEN** an owner restores version 2 of a published survey at version 3
- **THEN** the response is 201 with an unpublished-changes uuid whose sections are version 2's, and the live survey is unchanged

### Requirement: Icon search over the API
`GET /icons?q=&lang=&set=&limit=` (scope `surveys:read`, no Pro gate) SHALL return at most `limit`
(default 20, at most 100) drawable marker icon values as `{value, label, set, categories}`. Every
query token SHALL match a substring of the icon's name, label or search terms in `lang` or English.
Exact name and label-word matches SHALL rank first.

#### Scenario: Find by meaning in Russian
- **WHEN** a client asks `GET /icons?q=скамейка&lang=ru`
- **THEN** the results include `temaki:bench` and every value is accepted as `icon_class`

#### Scenario: Nothing found
- **WHEN** no icon matches
- **THEN** the response is 200 with an empty list

### Requirement: Structure schemas carry the audience
Section, group and question input and output schemas SHALL carry `audience`
(`everyone` | `respondents` | `operators`), optional on input, always present on output; the MCP
tools built over the same schemas SHALL accept and return it. The generated references
(`reference/api.md`, `reference/mcp-tools.md`) SHALL be regenerated in the same change.

#### Scenario: Set over the API
- **WHEN** a client PATCHes a question with `{"audience": "operators"}`
- **THEN** the response body has `"audience": "operators"` and the respondent page no longer shows the question

#### Scenario: Unknown value
- **WHEN** a client PATCHes `{"audience": "staff"}`
- **THEN** the response is `422 validation` naming `audience`

#### Scenario: Live survey
- **WHEN** a client PATCHes the audience on a published survey without unpublished changes
- **THEN** the response is `409 draft_required`

### Requirement: Survey period over the API
`GET /surveys` and `GET /surveys/{uuid}` SHALL include `opens_at`, `closes_at` (ISO 8601, UTC,
`null` when unset) and `schedule_timezone`. `PATCH /surveys/{uuid}` (scope `surveys:write`, role
`owner`) SHALL accept the three fields, a `null` clearing an instant, and SHALL validate them
through `SurveyHeaderForm` like every other Settings field, so a closing time before the opening
time or a changed closing time in the past answers `422 validation` naming `closes_at`. The
period SHALL be written on the canonical survey even when the uuid names unpublished changes.
`POST /surveys/{uuid}/publish` on a `closed` survey SHALL clear a past `closes_at` (capability
`survey-schedule`).

#### Scenario: Read and set
- **WHEN** an owner token PATCHes `{"opens_at": "2026-11-03T09:00:00+06:00",
  "closes_at": "2026-11-30T23:59:00+06:00", "schedule_timezone": "Asia/Bishkek"}`
- **THEN** the response is `200` with `opens_at: "2026-11-03T03:00:00Z"`,
  `closes_at: "2026-11-30T17:59:00Z"` and `schedule_timezone: "Asia/Bishkek"`

#### Scenario: Clear the end
- **WHEN** the same token PATCHes `{"closes_at": null}`
- **THEN** the response shows `closes_at: null` and `opens_at` unchanged

#### Scenario: Invalid order
- **WHEN** a PATCH sets `closes_at` earlier than the stored `opens_at`
- **THEN** the response is `422 validation` with `closes_at` among the named fields

#### Scenario: Unpublished changes write to the live survey
- **GIVEN** a published survey with unpublished changes
- **WHEN** a PATCH on the draft's uuid sets `closes_at`
- **THEN** the canonical survey holds it and the draft row holds nothing

