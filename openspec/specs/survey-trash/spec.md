## Purpose

Give deleted surveys a 30-day recoverable trash lifecycle: hidden from respondents and dashboards, restorable by the owner, permanently purged (with media cleanup) manually or on schedule.
## Requirements
### Requirement: Trashed surveys are hidden but recoverable
A survey with `deleted_at` set SHALL be excluded from the editor dashboard, public survey list, public survey URLs (404), and all regular editor endpoints, while its sections, questions, sessions, and answers remain intact in the database.

#### Scenario: Trashed survey hidden from dashboard
- **WHEN** an owner trashes a survey and returns to the dashboard
- **THEN** the survey SHALL NOT appear in the survey list

#### Scenario: Public URL of trashed survey returns 404
- **WHEN** a respondent opens `/surveys/<slug>/` of a trashed survey
- **THEN** the system SHALL respond with 404

#### Scenario: Data preserved while in trash
- **WHEN** a survey with sessions and answers is trashed
- **THEN** all its `SurveySession` and `Answer` rows SHALL still exist

### Requirement: Trash view lists trashed surveys
The editor SHALL provide a Trash view listing the owner's trashed surveys with their deletion date and days remaining until auto-purge, each offering Restore and Delete-forever actions. When a trashed survey owns reference layers, the Delete-forever confirmation SHALL name how many layers and how many objects will be destroyed with it.

#### Scenario: Trash view shows trashed survey
- **WHEN** an owner opens the Trash view after trashing a survey
- **THEN** the survey SHALL be listed with its trash date and days until purge

#### Scenario: Delete-forever dialog names the layers it will destroy
- **WHEN** an owner opens Delete forever on a trashed survey owning reference layers
- **THEN** the dialog SHALL state the number of layers and the number of objects on them

#### Scenario: A survey without layers gains no extra text
- **WHEN** an owner opens Delete forever on a trashed survey owning no reference layers
- **THEN** the dialog SHALL read exactly as it does today

### Requirement: Owner can restore a trashed survey
Restoring SHALL clear `deleted_at` and return the survey to its exact pre-trash state, including its lifecycle status.

#### Scenario: Restore returns survey to dashboard
- **WHEN** an owner restores a trashed survey that was published
- **THEN** the survey SHALL reappear on the dashboard with status published
- **AND** its public URL SHALL work again

### Requirement: Permanent deletion cascades and cleans media
Manual Delete-forever and auto-purge SHALL permanently delete the survey, its archived versions and draft copy, all sessions and answers, its reference layers with their objects and attachments, and SHALL remove the survey's cover image, question images and layer object attachments from file storage via the Django storage API.

A survey owning a reference layer that any of its questions is bound to SHALL purge without error. `Question.layer` is PROTECTed so that deleting a layer on its own refuses and names the bound question; that protection MUST NOT prevent the survey-wide purge, where the question is deleted too.

#### Scenario: Purge removes all data
- **WHEN** an owner clicks Delete forever on a trashed survey
- **THEN** the survey, its versions, sessions, and answers SHALL be deleted from the database

#### Scenario: Purge removes media files
- **WHEN** a survey with a cover image and question images is purged
- **THEN** those files SHALL no longer exist in storage

#### Scenario: Purge requires the survey to be in trash
- **WHEN** a Delete-forever request targets a survey that is not trashed
- **THEN** the system SHALL reject the request without deleting anything

#### Scenario: Purge of a survey with a layer-bound question
- **WHEN** an owner purges a trashed survey whose `layer_objects` question is bound to one of its reference layers
- **THEN** the survey, the question, the layer and the layer's objects SHALL all be deleted
- **AND** no error SHALL be raised

#### Scenario: Purge removes layer object attachments from storage
- **WHEN** a survey whose layer objects carry file attachments is purged
- **THEN** those files SHALL no longer exist in storage

#### Scenario: A draft copy's borrowed layer binding does not block the purge
- **WHEN** an owner purges a published survey that has a live draft copy whose question is bound to the canonical survey's layer
- **THEN** both headers, the draft's question and the layer SHALL be deleted

#### Scenario: A question outside the purged survey keeps its layer binding
- **WHEN** a purge runs
- **THEN** no question belonging to a survey outside the purged family SHALL have its layer binding cleared

### Requirement: Auto-purge is triggerable via an internal HTTP endpoint
The system SHALL expose `POST /internal/purge-trash/` that runs the auto-purge routine, authenticated by a shared secret token from the `PURGE_TASK_TOKEN` environment variable. Requests without a valid token MUST be rejected with 403. When the token is unset, the endpoint MUST be disabled (403 for all requests). The endpoint exists so a lightweight external scheduler (curl-based cron) can drive purging without a Django runtime.

#### Scenario: Valid token triggers purge
- **WHEN** a POST with the correct bearer token arrives and a survey was trashed 31 days ago
- **THEN** that survey SHALL be purged and the response SHALL report the purge count

#### Scenario: Missing or wrong token rejected
- **WHEN** a POST arrives without a token or with an incorrect token
- **THEN** the system SHALL respond 403 and purge nothing

#### Scenario: Endpoint disabled without configured token
- **WHEN** `PURGE_TASK_TOKEN` is empty and any request arrives
- **THEN** the system SHALL respond 403

### Requirement: Trashed surveys are auto-purged after 30 days
A scheduled job SHALL permanently purge surveys whose `deleted_at` is older than 30 days, using the same purge routine as manual Delete-forever, and SHALL write a `survey_auto_purge` audit record per survey. A survey whose purge fails SHALL NOT prevent the remaining expired surveys in the same run from being purged; the failure SHALL be logged and reported in the run's result rather than swallowed.

#### Scenario: Old trashed survey purged by the job
- **WHEN** the purge job runs and a survey was trashed 31 days ago
- **THEN** that survey SHALL be permanently deleted
- **AND** an audit record with action `survey_auto_purge` and no actor SHALL be written

#### Scenario: Recent trashed survey survives the job
- **WHEN** the purge job runs and a survey was trashed 5 days ago
- **THEN** that survey SHALL remain in the trash

#### Scenario: One failing survey does not abandon the run
- **WHEN** the purge job runs over several expired surveys and one of them raises
- **THEN** every other expired survey SHALL still be purged
- **AND** the run's result SHALL report the failure

