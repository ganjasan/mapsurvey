## Context

Group, duplicate, paste and move writes live in views:

- `editor_group_views` holds `editor_group_create|edit|delete` and `editor_question_move`.
- `editor_views` holds `editor_question_duplicate|paste` and `editor_section_duplicate|paste`.

None of these writes an audit row. The service layer already has `questions.reorder`, which applies
the nested order with group membership and backs `PUT …/questions/order`. It also has
`publishing.restore_version`, which is unaudited and which no API calls.

`cloning.py` copies sections, questions and groups field by field from the model's field list, so
nothing is lost. A cross-survey copy keeps the source's `FieldFile` names, though. A survey has no
whole-survey copy and no cross-section move. `versioning.clone_survey_for_draft` copies a survey only
into its own family. Layers belong to the canonical survey and nothing copies them.
`trash.purge` deletes the cover, question image and layer asset files of the purged family.

## Goals / Non-Goals

**Goals.** An agent can:

- group questions;
- copy a question, a section or a whole survey;
- move a question anywhere in its survey;
- list versions and restore one as unpublished changes;
- find an icon by meaning in its user's language.

The editor and the API run the same code. A copy never shares a stored file with its source.

**Non-Goals:**

- copying a survey into another workspace;
- copying responses, versions, tracked links, collaborators, comments or the public results page;
- moving a question to another survey (use copy, then delete);
- group nesting.

## Decisions

### D1 · Two services; views become thin
`survey/services/groups.py` provides:

- `create(actor, section, *, parent=None, data, question_ids=None)` — binds `QuestionGroupForm`.
  The rule goes through `common.parse_visibility`/`check_rule` and translations through
  `save_translations`. `question_ids` makes those questions members at the place of the first one,
  through `apply_nested_order`.
- `update(actor, group, data, *, partial)`.
- `delete(actor, group, *, with_questions, acknowledged)`.

`survey/services/structure.py` provides:

- `duplicate_question`, `duplicate_section`;
- `paste_question(actor, target_section, source_question, *, parent=None)` and `paste_section`;
- `move_question` (D3);
- `duplicate_survey` (D4).

**Locks.** Groups follow the editor's split. Title, description, style and translations are
content: `assert_content_editable`, then `rescreen_if_live`. Create, delete, membership and a rule
change are structural: `assert_structure_editable`. Every structure operation is structural.

**Errors and audit.** Refusals are the existing `services.errors` types: `ValidationFailed`,
`StructureLocked`, `AnswersAtRisk`, `DeleteBlocked`, `TransitionRefused` and `Conflict`. The editor
views map them to exactly what they return today (statuses, JSON keys, messages), and their tests
stay green. Every write is audited with one of these actions:

- `group_create`, `group_update`, `group_delete`;
- `question_duplicate`, `section_duplicate`, `question_paste`, `section_paste`, `question_move`;
- `survey_duplicate`, `version_restore`.

`AuditLog.ACTION_CHOICES` gains them in a choices-only migration.

### D2 · A copy owns its files
`cloning.copy_file(field_file, upload_to_instance)` reads the stored object and saves it under a
fresh key from the field's own `upload_to`, so a `layer_assets/<uuid>` asset gets a new random key.
It runs for:

- `SurveyHeader.cover_image`;
- `Question.image` on every cross-survey copy (paste question, paste section, duplicate survey);
- `LayerObjectAsset.file` in a survey copy.

Same-survey duplicates and the draft family keep sharing, because they are purged together. A file
that is missing from storage is logged and the copy goes on without it. Embeds copy their URL.

### D3 · One move service
`move_question(actor, question, *, section=None, parent=None, position=None, acknowledged=False)`
covers three cases. In every case the move is structural, so a live survey answers
`StructureLocked`, and the rules it breaks are dropped and named.

1. **Into or out of a pop-up, same section.** This is today's `editor_question_move`: the same
   refusals and the answer-loss acknowledgement, because answers of a pop-up question are rows per
   feature and do not survive the change of level. Sub-questions block it.
2. **To another section of the same survey, at top level.** The question and its descendants change
   `survey_section`. Answers stay: they belong to the question and the session, not to the section,
   so no acknowledgement is asked. The question leaves its group. It takes `position` among the
   target section's top-level items, at the end by default, and both sections are renumbered
   through `apply_nested_order`.
3. **To a pop-up of another section.** This is (2) followed by (1).

Every rule left `broken` — its own, those naming it, and those in either section — is cleared.
`_drop_rules_broken_by_move` moves into the service and widens from one section to the whole
survey. The result carries `removed_rules` (labels), as today. `editor_question_move` calls the
service.

**Editor UI.** The question row gains "Move to section…", a dropdown of the other sections. It posts
`section_id` and reloads the Build panel, and it uses the `data-gate="move"` structure gate on a
live survey.

### D4 · Duplicate a survey
`duplicate_survey(actor, survey)` reads the structure of the row it is given. That is the canonical
survey, or the unpublished-changes copy when its uuid is passed. The new survey is:

- canonical, `draft`, in the same workspace, created by the actor;
- named `"<name> (copy)"`, truncated to 45 characters;
- given the actor as owner collaborator, as `create` does.

The header comes from `cloning.plain_field_values` with an explicit exclusion list:

- `uuid`, `test_token`, `status`;
- the version fields, `published_version`, `canonical_survey`;
- `created_by`, `is_archived`, the trash and timestamp fields, and `cover_image` (copied by D2).

Everything else travels, the password and embed hosts included, so the copy behaves like its source.

The structure travels as follows:

- sections through `copy_section` and relinked as a list;
- groups and questions through `clone_groups`, `clone_top_level_questions` and `clone_question`;
- codes are kept, so every visibility rule stays valid with nothing to remap.

Layers travel as follows:

- every `layers_for(source)` row is copied onto the new survey with geometry, style and order;
- creator layers keep their `LayerObject`s and assets (files by D2);
- shared-map (`source='question'`) layers copy their settings and no objects, because their objects
  are other people's answers;
- `Question.layer` is remapped to the copies;
- `rebuild_layer` runs per copied layer.

Not copied:

- sessions and answers;
- versions;
- tracked links;
- collaborators other than the actor;
- comments;
- `PublicResultsPage`;
- `ContentReview`.

**Rights and checks.** REST and MCP need `surveys:write`, survey role `viewer` or above on the
source, the workspace role that creates surveys (`editor`), Pro on the workspace, and the
`survey_create` named limit. Screening does not run, because a draft is never screened.
`DuplicateSurveyKeepsFieldsTest` compares every concrete field of source and copy and fails on a
field that is neither copied nor listed as excluded.

**Editor UI.** The dashboard's ⋯ menu gains "Duplicate" for the workspace roles that may create. It
is a POST to `editor_survey_duplicate`, which redirects to the copy's Build page.

**Size.** The copy is synchronous. Layer assets are bounded by the object caps, and a copy with more
than `DUPLICATE_ASSET_BYTES_MAX` (200 MB) of files is refused with `limit_reached` rather than tie
up a worker; ZIP export/import is the route for those.

### D5 · Versions
`GET /surveys/{uuid}/versions` lists the canonical survey first (`current: true`), then the archived
rows newest first. Each entry is `{version, current, status, published_at, sections, questions,
responses}`:

- `published_at` comes from the `status_transition` and `draft_publish` audit rows, never from the
  current status;
- `responses` counts non-empty sessions.

`POST /surveys/{uuid}/versions/{n}/restore` is owner-only, like the editor. It calls
`publishing.restore_version` and answers:

- 201 with the unpublished-changes uuid;
- `409 conflict` when unpublished changes already exist;
- `409 transition_refused` when the survey is not published;
- 404 for an unknown version.

MCP `restore_version` needs no `confirm`, because nothing live changes until
`publish_unpublished_changes`.

### D6 · Icon search
`survey/icon_search.py::search(q, *, lang='en', sets=None, limit=20)` loads the catalog once through
`marker_icons.catalog()`. It returns only values `marker_icons.is_drawable` accepts.

Matching is the picker's rule: every whitespace token must be a substring of the `lang` haystack or
the English one. The haystack is the name without its prefix (`-`/`_` → space), the lowercased
label and the terms.

Ranking, which the picker does not need, puts first an exact name or label word, then a token that
starts a word, then catalog order.

**Route.** `GET /icons?q=&lang=&set=maki|temaki|fa&limit=` needs scope `surveys:read` and no Pro
gate: the data is the catalog every editor page already ships. It returns
`[{value, label, set, categories}]`. `lang` defaults to the user's UI language.

A miss is counted as the editor's `icon_search_miss` event with `surface: api|mcp`. Only the query
is sent, at most 64 characters, as the picker already does.

### D7 · Output shapes
- **Group:** `{id, code, title, description, display_style, visibility_rule, parent_id, order,
  question_ids, translations}`.
- **Question:** gains `group_id`.
- **Section** (detail and `get_survey`): gains `groups`.
- **Structure writes** answer with the moved or new object, plus:
  - `removed_rules` for a move;
  - for a duplicated survey, `{uuid, name, sections, questions, layers}`.

## Risks / Trade-offs

- **Moving view logic changes editor behaviour.** Editor tests for groups, duplicate, paste and move
  stay green; statuses and messages are asserted unchanged.
- **A survey copy is slow on S3 with many assets.** The copy is capped at 200 MB of files and the
  files are copied before the transaction commits. On failure the copied keys are deleted.
- **A cross-section move breaks a rule silently.** The rule is cleared and named in `removed_rules`,
  and the editor shows the same toast as today.
- **Paste now copies files.** The slower paste with an image is accepted, because the alternative is
  data loss on purge.
