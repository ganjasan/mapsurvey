## ADDED Requirements

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
