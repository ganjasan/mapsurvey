## ADDED Requirements

### Requirement: A section view only honours a session that belongs to the requested survey

`survey_section` SHALL validate the session named by `survey_session_id` before routing with it.
A session SHALL be honoured only if it exists, is not soft-deleted, and belongs to the requested
survey's family — the canonical header itself or a version whose `canonical_survey_id` points at
it. Any other cookie state SHALL start a fresh session against the canonical survey, emitting the
same `session_start` analytics as a first visit.

#### Scenario: A session from another survey is replaced, not served

- **GIVEN** a respondent whose cookie names a session belonging to survey A
- **WHEN** they open a section of survey B by direct link
- **THEN** the section renders with HTTP 200
- **AND** a new session for survey B is created and stored in the cookie

#### Scenario: Answers posted after switching surveys land in the new session

- **GIVEN** a respondent whose cookie names a session belonging to survey A
- **WHEN** they submit the last section of survey B
- **THEN** the answers are saved to a session of survey B

#### Scenario: A soft-deleted session is not continued

- **GIVEN** a respondent whose session was soft-deleted by the creator
- **WHEN** they open a section of the same survey
- **THEN** a new session is created rather than writing into the deleted one

#### Scenario: Version routing is preserved

- **GIVEN** a respondent whose session is pinned to an archived version of the survey
- **WHEN** they open a section that exists in that version
- **THEN** the archived version's section is served under the same session

### Requirement: A section miss redirects instead of erroring

The section view SHALL redirect the respondent to the survey entry point when the requested
section name does not exist in the survey the session resolves to. Respondent-facing survey URLs
SHALL NOT return HTTP 500 for any cookie or link state.

#### Scenario: A stale section link restarts at the entry point

- **WHEN** a respondent opens a section URL whose name does not exist in the survey
- **THEN** they are redirected to `/surveys/<uuid>/`
- **AND** from there to the survey's first section
