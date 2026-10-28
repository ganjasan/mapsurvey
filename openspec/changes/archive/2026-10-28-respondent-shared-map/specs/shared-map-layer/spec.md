## ADDED Requirements

### Requirement: A reference layer can be sourced from a geo question's answers
`SurveyMapLayer` SHALL carry `source` ∈ {`upload`, `question`} (default `upload`) and, for
`question` layers, `source_question_code` naming a point, line or polygon question of the
same survey family by code. A `question` layer SHALL keep every other layer property and
behaviour (color, label field, per-section visibility, render order, kill switch, binding
to an "Objects on the map" question). Its object editor SHALL open read-only. Saving a
`question` layer whose code matches no geo question in the canonical survey SHALL fail
validation.

#### Scenario: Layer sourced from a point question
- **WHEN** the creator creates a layer with source "answers to a question" and picks the point question `Q1`
- **THEN** the layer stores `source='question'`, `source_question_code='Q1'`, renders in the Reference layers card with a "source: answers" badge and no upload/draw actions

#### Scenario: Unknown code is rejected
- **WHEN** a layer is saved with `source='question'` and a code that names no geo question
- **THEN** the save fails with a validation error naming the field

### Requirement: Objects are materialised from answers with stable keys
After a section POST stores a session's answers to a source geo question, the system SHALL
synchronise the layer's objects for that session: the n-th stored feature becomes the object
with key `s<session_id>-<n>`, geometry from the answer, title from the sub-answer named by
`label_field` (truncated to 255) or empty, `source_answer` and `source_session` set.
Existing objects with the same key SHALL be updated in place; keys of that session with no
matching feature SHALL be deleted. Reactions on an updated object SHALL be preserved. The
source question SHALL be resolved by code within the session's own survey version.
Materialisation failure SHALL be logged and SHALL NOT fail the answer submit.

#### Scenario: Re-submit keeps reactions
- **WHEN** session A submits one point, session B reacts 👍 to it, and A presses Back then Next re-submitting the same section
- **THEN** the object `sA-1` still exists with B's reaction attached and its geometry reflects A's latest submit

#### Scenario: Removed mark drops its object
- **WHEN** session A re-submits with one feature fewer than before
- **THEN** the surplus object of A is deleted together with the reactions that referenced it

#### Scenario: Older version feeds the canonical layer
- **WHEN** a respondent on an archived version submits a mark for the question with code `Q1`
- **THEN** the object appears in the canonical survey's `question` layer for `Q1`

### Requirement: Only other people's clean, visible marks are served to a respondent
For a `question` layer the gated layer endpoint SHALL return only objects with
`status='visible'` whose source session is not deleted, not `not_approved`, not `on_hold`,
and is not the requesting session. The response SHALL carry `Cache-Control: private,
no-store` and an ETag that includes the requesting session id. The object card endpoint
SHALL apply the same filter and return 404 for objects outside it. The respondent list
block SHALL state that the respondent's own marks are not listed.

#### Scenario: Own mark is absent
- **WHEN** session A has one mark on the source question and loads the section
- **THEN** the layer collection A receives contains every other clean visible mark and none with `source_session=A`

#### Scenario: Session put on hold disappears
- **WHEN** the creator sets session A to `on_hold`
- **THEN** A's marks are omitted from every respondent's layer collection and A's reactions are excluded from tallies, without changing any object's `status`

### Requirement: Tallies and comments reach respondents only when the layer allows it
When `show_tallies` is on, features of a `question` layer SHALL carry `tally_up`,
`tally_down` and `comment_count` computed over clean sessions and non-hidden answers, and
the list block, map badge and popup SHALL render them; when off the properties SHALL be
absent and nothing rendered. When `show_comments` is on, the object card SHALL include the
newest 10 non-hidden comments (text sub-answers) without author identity; when off no
comments SHALL be included. Tallies SHALL be current as of the last reaction submit.

#### Scenario: Tallies on, comments off (defaults)
- **WHEN** a mark has 4 👍, 1 👎 and 2 comments and the layer has default settings
- **THEN** the row shows "👍 4 · 👎 1", the card shows the tallies line and no comment text

#### Scenario: Tallies off
- **WHEN** the creator switches `show_tallies` off
- **THEN** rows, badges and cards show no counts, and the feature properties carry no tally keys

#### Scenario: Comments on
- **WHEN** `show_comments` is on and a mark has three comments, one hidden by the creator
- **THEN** the card lists the two non-hidden comments as quotes with no author

### Requirement: The source question's export carries the verdict
The GeoJSON export of a source geo question SHALL add to each feature `mark_key`,
`votes_up`, `votes_down` and `comments` (count), computed from the bound "Objects on the
map" question over clean sessions. The per-object CSV of the bound question SHALL include a
`status` column. Export SHALL include marks regardless of status.

#### Scenario: Ten residents, one corner
- **WHEN** one mark received 9 👍 and the survey is exported
- **THEN** its feature in the geo question's GeoJSON has `votes_up=9`, and the per-object CSV has one row for it

### Requirement: Question layers round-trip as configuration
ZIP export SHALL write `source`, `source_question_code`, `show_tallies`, `show_comments`
and `approve_first` for every layer and SHALL write no objects for `question` layers.
Import SHALL create `question` layers empty. An imported `question` layer whose code
matches no geo question SHALL be imported as an empty `upload` layer with a report line.

#### Scenario: Export and re-import
- **WHEN** a survey with a `question` layer and its pair question is exported and imported
- **THEN** the imported survey has the layer with the same source code and settings, no objects, and the pair question bound to it

#### Scenario: Dangling source code
- **WHEN** the archive's geo question was removed before export
- **THEN** the layer imports as `upload`, empty, and the import report says why
