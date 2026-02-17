## ADDED Requirements

### Requirement: Version tracking on surveys
The system SHALL track a `version_number` (PositiveIntegerField, default=1) on `SurveyHeader`. The system SHALL track `canonical_survey` (nullable self-FK) and `is_canonical` (BooleanField, default=True) to distinguish canonical surveys from archived versions. Canonical surveys hold the latest structure and bear the public URL. Archived versions hold old structures with their associated sessions and answers.

#### Scenario: New survey starts at version 1
- **WHEN** a new survey is created
- **THEN** its `version_number` SHALL be 1, `is_canonical` SHALL be True, `canonical_survey` SHALL be NULL

#### Scenario: Archived version linked to canonical
- **WHEN** a new version is published
- **THEN** the archived version SHALL have `canonical_survey` pointing to the canonical survey, `is_canonical=False`, and the `version_number` of the previous version

#### Scenario: Version number increments on publish
- **WHEN** a draft copy is published
- **THEN** the canonical survey's `version_number` SHALL increment by 1

### Requirement: Create draft copy of published survey
The system SHALL allow survey owners to create a draft copy of a published survey via POST to `/editor/surveys/<uuid>/create-draft/`. The draft copy SHALL be a new `SurveyHeader` with `status='draft'` and `published_version` FK pointing to the canonical survey. The draft SHALL contain a clone of the canonical's sections, questions, choices, and translations, **using the same question codes** as the original.

#### Scenario: Create draft copy
- **WHEN** the owner of a published survey clicks "Edit Published Survey"
- **THEN** a new `SurveyHeader` is created with `status='draft'`, `published_version` pointing to the canonical, and a clone of sections/questions/translations with identical question codes
- **AND** the user is redirected to the draft copy's editor page

#### Scenario: Draft copy inherits settings
- **WHEN** a draft copy is created
- **THEN** it SHALL copy `available_languages`, `visibility`, `redirect_url`, `thanks_html`, and `password_hash` from the canonical

#### Scenario: Draft copy inherits collaborators
- **WHEN** a draft copy is created
- **THEN** all `SurveyCollaborator` records from the canonical SHALL be duplicated for the draft copy

#### Scenario: Only one draft at a time
- **WHEN** a draft copy already exists for a published survey and the owner tries to create another
- **THEN** the system SHALL return 409 Conflict

#### Scenario: Only owners can create draft copies
- **WHEN** a non-owner editor tries to create a draft copy
- **THEN** the system SHALL return 403 Forbidden

#### Scenario: Only published surveys can have draft copies
- **WHEN** the owner tries to create a draft copy of a survey not in `published` status
- **THEN** the system SHALL return 400 Bad Request

#### Scenario: Draft copy name
- **WHEN** a draft copy is created for a survey named "my_survey"
- **THEN** the draft copy's name SHALL be "[draft] my_survey" (truncated to 45 chars if needed)

### Requirement: Backward compatibility check before publish
The system SHALL verify backward compatibility between the draft copy and the canonical survey before allowing publish. A change is breaking if it would orphan existing answers.

#### Scenario: Deleted question with answers
- **WHEN** the draft removes a question (by code) that exists in the canonical and has at least one Answer row
- **THEN** the compatibility check SHALL report a breaking issue

#### Scenario: Changed input_type with answers
- **WHEN** the draft changes the `input_type` of a question (by code) that has at least one Answer row
- **THEN** the compatibility check SHALL report a breaking issue

#### Scenario: Removed choice codes with answers
- **WHEN** the draft removes a choice code from a question, and existing answers have that code in `selected_choices`
- **THEN** the compatibility check SHALL report a breaking issue

#### Scenario: Safe changes pass check
- **WHEN** the draft only adds new questions/sections, reorders items, changes display text, or adds new choices
- **THEN** the compatibility check SHALL return an empty list

#### Scenario: No answers means no breaking changes
- **WHEN** the draft deletes or modifies a question that has zero Answer rows
- **THEN** the compatibility check SHALL NOT report it as a breaking issue

### Requirement: Publish draft copy via structure move
The system SHALL allow survey owners to publish a draft copy via POST to `/editor/surveys/<uuid>/publish-draft/`. Publishing SHALL atomically: archive the canonical's current structure by moving sections to a new archived SurveyHeader, move active sessions to the archive, then move the draft's sections into the canonical. The request SHALL fail if breaking compatibility issues are found, unless `force=true` is provided.

#### Scenario: Publish compatible draft
- **WHEN** the owner publishes a draft copy that passes the compatibility check
- **THEN** the system SHALL atomically:
  1. Create an archived SurveyHeader (`is_canonical=False`, `canonical_survey=canonical`, `version_number=canonical.version_number`, `status='closed'`)
  2. Move all sections from canonical to archived version (`SurveySection.survey_header` FK update)
  3. Move all sessions from canonical to archived version (`SurveySession.survey` FK update)
  4. Move all sections from draft to canonical (`SurveySection.survey_header` FK update)
  5. Copy settings from draft to canonical
  6. Increment `canonical.version_number`
  7. Delete the draft copy SurveyHeader
- **AND** redirect to the canonical survey's editor page

#### Scenario: Old answers preserved after publish
- **WHEN** a draft is published and sections are moved to the archived version
- **THEN** all `Answer` rows SHALL retain their original `question` FK (pointing to the moved Question objects, now under the archived version)

#### Scenario: Grace period for active sessions
- **WHEN** a draft is published and there are respondents mid-survey (sessions without `end_datetime`)
- **THEN** those sessions SHALL be moved to the archived version and SHALL continue to see the old version's sections/questions

#### Scenario: New sessions see new version
- **WHEN** a new respondent starts the survey after a version is published
- **THEN** their session SHALL be created against the canonical survey (latest structure)

#### Scenario: Publish with breaking changes blocked
- **WHEN** the owner publishes a draft that has breaking compatibility issues and `force` is not set
- **THEN** the system SHALL return 409 Conflict with the list of issues

#### Scenario: Force publish with breaking changes
- **WHEN** the owner publishes with `force=true` despite breaking issues
- **THEN** the system SHALL proceed with publish
- **AND** the old questions with their answers SHALL be preserved in the archived version

#### Scenario: Only draft copies can be published
- **WHEN** the owner tries to publish a survey that has no `published_version` FK
- **THEN** the system SHALL return 400 Bad Request

#### Scenario: Only owners can publish
- **WHEN** a non-owner editor tries to publish a draft copy
- **THEN** the system SHALL return 403 Forbidden

### Requirement: Discard draft copy
The system SHALL allow survey owners to discard a draft copy via POST to `/editor/surveys/<uuid>/discard-draft/`. Discarding SHALL delete the draft copy without affecting the canonical survey.

#### Scenario: Discard draft copy
- **WHEN** the owner discards a draft copy
- **THEN** the draft copy SurveyHeader and all its sections/questions/translations are deleted
- **AND** the canonical survey is unchanged
- **AND** the user is redirected to the canonical survey's editor page

#### Scenario: Only owners can discard
- **WHEN** a non-owner editor tries to discard a draft copy
- **THEN** the system SHALL return 403 Forbidden

### Requirement: Session routing by version
The `survey_section` view SHALL route respondents to the correct version's sections based on their session. If the session references an archived version, the view SHALL use that version's sections for lookup, form rendering, and navigation.

#### Scenario: Existing session uses archived version
- **WHEN** a respondent with an active session (pointing to an archived version) submits a section form
- **THEN** the section SHALL be resolved from the archived version's sections (by `session.survey`)
- **AND** navigation (next_section/prev_section) SHALL follow the archived version's linked list

#### Scenario: New session uses canonical
- **WHEN** a new respondent starts the survey (no session in browser)
- **THEN** a session SHALL be created against the canonical survey
- **AND** sections SHALL be resolved from the canonical's sections

### Requirement: Draft copy visibility
Draft copies SHALL have `status='draft'` and SHALL be invisible to respondents. Archived versions SHALL have `status='closed'` and SHALL be blocked by access control.

#### Scenario: Respondents cannot access draft copies
- **WHEN** a respondent navigates to a draft copy's public URL
- **THEN** the system SHALL return 404

#### Scenario: Respondents cannot access archived versions directly
- **WHEN** a respondent navigates to an archived version's UUID
- **THEN** the system SHALL show "Survey Closed" page

#### Scenario: Draft copies excluded from dashboard
- **WHEN** the editor dashboard lists surveys
- **THEN** draft copies (surveys with `published_version` set) SHALL NOT appear

#### Scenario: Archived versions excluded from dashboard
- **WHEN** the editor dashboard lists surveys
- **THEN** archived versions (`is_canonical=False`) SHALL NOT appear

### Requirement: Version-aware data export
The `download_data` view SHALL support a `version` query parameter to filter exported data by version.

#### Scenario: Export latest version
- **WHEN** `download_data` is called with `?version=latest` or no version parameter
- **THEN** only sessions/answers from the canonical survey SHALL be exported

#### Scenario: Export specific version
- **WHEN** `download_data` is called with `?version=v1`
- **THEN** only sessions/answers from the archived version with `version_number=1` SHALL be exported

#### Scenario: Export all versions
- **WHEN** `download_data` is called with `?version=all`
- **THEN** sessions/answers from all versions SHALL be exported, with filenames prefixed by version (`v1_`, `v2_`, etc.)

#### Scenario: Version dropdown in editor
- **WHEN** the download data UI is shown for a survey with multiple versions
- **THEN** a version selector SHALL appear with options: "Latest", "v1", "v2", ..., "All Versions"

### Requirement: SurveySession FK protection
`SurveySession.survey` FK SHALL use `on_delete=PROTECT` instead of `CASCADE`. This prevents accidental deletion of SurveyHeaders that have session data.

#### Scenario: Cannot delete survey with sessions
- **WHEN** an owner tries to delete a SurveyHeader that has SurveySession records
- **THEN** the system SHALL raise a ProtectedError (deletion blocked)

#### Scenario: Can delete survey without sessions
- **WHEN** an owner tries to delete a SurveyHeader with zero sessions
- **THEN** the deletion SHALL proceed normally
