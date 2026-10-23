## ADDED Requirements

### Requirement: One write path for survey structure and lifecycle
The system SHALL provide `survey/services/` (`surveys`, `sections`, `questions`, `publishing`) as
the only code that creates, updates, deletes or reorders a `SurveyHeader`, `SurveySection`,
`Question` (including its choices, validation settings, visibility rule and translations) on
behalf of a creator, and the only code that changes a survey's lifecycle status, creates,
publishes or discards unpublished changes. The editor views and every API route SHALL call these
services; neither SHALL write those models directly. Question groups, duplicate, paste and move
are outside this requirement in v1 and keep their editor implementation.

#### Scenario: Editor question edit goes through the service
- **WHEN** a creator saves the question modal
- **THEN** the view calls `services.questions.update(...)` and the stored row, the response status,
  body and `HX-Trigger` header are the same as before the extraction

#### Scenario: Reviewer can confirm no direct writes
- **WHEN** `api/v1/` is searched for `.save(`, `.objects.create(`, `.update(` or `.delete(` on
  `SurveyHeader`, `SurveySection` or `Question`
- **THEN** nothing is found

### Requirement: Services take an actor, never a request
Every service function SHALL take an `Actor(user, ip, surface)` and plain values; it SHALL NOT read
`request`, `request.POST`, `request.session` or `request.active_org`. Values the editor read from
the request (`organization`, `group_id`, `acknowledge_answer_loss`,
`acknowledge_translation_gaps`, `force`) SHALL be explicit arguments. `audit.record(actor, action,
survey, **metadata)` SHALL write the `AuditLog` row; `audit(request, ...)` SHALL delegate to it.

#### Scenario: Audit from the API carries the actor
- **WHEN** a survey is published through the API by user U from IP X
- **THEN** an `AuditLog` row `status_transition` exists with `actor=U`, `ip=X` and the old and new
  status

#### Scenario: Audit failure never breaks the operation
- **WHEN** writing the audit row raises
- **THEN** the service operation still completes and the error is logged

### Requirement: Validation runs through the editor's forms
A service SHALL validate input by binding the same Django form the editor uses
(`SurveyHeaderForm`, `SurveySectionForm`, `QuestionForm`) to a plain data dict, and SHALL raise
`ValidationFailed(fields)` from its errors before writing anything. Rich-text fields SHALL reach
the database only through `coerce_creator_html` (form `clean()` or the translation savers);
`redirect_url` only through the form's `clean_redirect_url`; choice lists only through
`normalise_choice_extras`, the answered-code guard and `clamp_single_other`.

#### Scenario: Same bytes from editor and service
- **WHEN** the same `subtext` containing `<script>alert(1)</script><b>ok</b>` is saved once through
  the editor's question form and once through `services.questions.update`
- **THEN** both rows hold identical sanitised `subtext`

#### Scenario: Invalid input writes nothing
- **WHEN** a section update carries a valid `name` and an invalid visibility rule
- **THEN** `ValidationFailed` is raised and the section's `name` is unchanged in the database

#### Scenario: Layer is not created by a refused question
- **WHEN** a question create names `layer=answers:<code>` and the form is invalid
- **THEN** no `SurveyMapLayer` row is created

### Requirement: Every service operation is atomic
Each service operation SHALL run inside one database transaction, so a failure leaves no partial
rows (sections half re-linked, a question without its translations, a layer without its question).

#### Scenario: Failure mid-delete rolls back
- **WHEN** deleting a section fails after its neighbours were re-linked
- **THEN** the section list is exactly as before the call

### Requirement: Live-survey edits follow one rule set
Services SHALL classify each change with `versioning.is_live`, `structural_question_changes`,
`structural_section_changes` and `removed_answered_choices`, and SHALL expose
`locks(survey) -> (content_locked, structure_locked)`. A structural change on a live survey SHALL
raise `StructureLocked(reasons, draft)`; any change to a live survey that has unpublished changes
SHALL raise `ContentLocked(draft)`; a content change on a live survey SHALL be applied, emit
`live_edit_saved` with the actor's surface, and re-screen the survey (`_rescreen_if_live`).

#### Scenario: Wording change on a published survey
- **WHEN** a service updates only a question's `name` on a published survey without a draft
- **THEN** the change is stored, `screen_survey(trigger='live_edit')` runs, and `live_edit_saved`
  is emitted

#### Scenario: Type change on a published survey
- **WHEN** a service update changes `input_type` on a published survey
- **THEN** `StructureLocked` is raised naming the draft uuid or none, and nothing is stored

### Requirement: Validation settings parsed once
`questions.parse_validation_settings(input_type, data)` SHALL be the one parser of
`validation_settings` (number/range bounds and outlier sigma, text min length, polygon area
factor, spray max dots, file limits clamped to the platform maxima, multi-feature min ≤ max), used
by question create, edit and sub-question create.

#### Scenario: Create keeps bounds
- **WHEN** a number question is created with `min=1`, `max=10`
- **THEN** its `validation_settings` holds both

#### Scenario: Inverted multi-feature bounds refused
- **WHEN** a polygon question is saved with `min_features=5`, `max_features=2`
- **THEN** `ValidationFailed` names `max_features`

### Requirement: Lifecycle operations
The lifecycle logic SHALL live in the publishing service: `publishing.transition(actor, survey, status, acknowledge_translation_gaps, clear_test_data)`,
`create_draft`, `publish_draft(force)`, `discard_draft` and `restore_version` SHALL hold the
lifecycle logic now in the views: `can_transition_to`, translation gaps (`TranslationGaps`),
clearing test data with its audit, `survey_published` with the creator as before,
`public_results.scaffold_page`, `screen_survey(trigger='publish' | 'draft_publish')`, the
`draft_publish` / `draft_discard` audits and the unpublished-changes events. Publishing SHALL
return whether the survey is held for content review.

#### Scenario: Publish of a lure-scoring survey
- **WHEN** `transition(..., 'published')` runs on a survey whose content scores at or above the
  hold threshold
- **THEN** the status is `published`, a pending `ContentReview` exists, and the result reports
  `review='pending'`

#### Scenario: Translation gaps refused without acknowledgement
- **WHEN** a survey with untranslated questions is published with
  `acknowledge_translation_gaps=False`
- **THEN** `TranslationGaps(gaps)` is raised and the status is unchanged

### Requirement: Editor behaviour unchanged by the extraction
After the extraction the editor SHALL return the same statuses, bodies, redirects and HTMX headers
for every request the existing suite exercises, with one listed exception: malformed JSON or
non-numeric ids posted to a choices, reorder or map endpoint answer `400` instead of `500`.

#### Scenario: Regression suite
- **WHEN** `./run_tests.sh survey` runs after PR 1
- **THEN** it passes with no test changed except those asserting the former 500 and `mock.patch`
  targets that name a function now called from `survey/services/`

#### Scenario: Malformed reorder body
- **WHEN** `editor_sections_reorder` receives `section_ids=["abc"]`
- **THEN** the response is `400` and no section is changed
