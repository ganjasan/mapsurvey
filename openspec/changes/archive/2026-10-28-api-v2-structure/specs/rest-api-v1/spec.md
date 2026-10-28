## ADDED Requirements

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
