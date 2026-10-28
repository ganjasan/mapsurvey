# survey-serialization — delta for layer-memory-diet

## MODIFIED Requirements

### Requirement: Import survey from ZIP via Web UI
The system SHALL provide an upload form in `/editor/` dashboard to import surveys. The
import SHALL run on the background worker as a tracked job: the request stores the
archive and returns at once, the dashboard shows the job's state (queued, running, done
with a link to the survey, failed with the reason) and refreshes it while a job is open,
and the archive is removed when the job finishes.

#### Scenario: Import from editor
- **WHEN** authenticated user clicks "Import Survey" and uploads ZIP file
- **THEN** the system starts an import job, redirects to `/editor/` and shows the job's progress there; when it finishes, the card links to the imported survey and lists any warnings

#### Scenario: Import validation error in Web UI
- **WHEN** user uploads an invalid archive via Web UI
- **THEN** the job ends as failed and the dashboard card shows the reason

#### Scenario: Unauthenticated upload
- **WHEN** unauthenticated user accesses import URL directly
- **THEN** system redirects to login page
