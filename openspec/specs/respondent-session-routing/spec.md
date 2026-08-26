# respondent-session-routing Specification

## Purpose

How the respondent-facing section view resolves the site-wide `survey_session_id` cookie into a
usable survey session: validation of the session's ownership, fallback to a fresh session, and
graceful handling of section lookups that miss.

## Requirements

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

### Requirement: Section navigation walks the visible chain

Forward and backward navigation between sections SHALL skip sections that are hidden
for the current session under conditional-visibility rules, in both directions. The
stored `next_section`/`prev_section` links SHALL remain untouched — skipping is a
read-time filter. Visibility for navigation SHALL be evaluated against the session's
answers as of the submit being processed. A respondent whose answers satisfy no
section rule in a group of conditioned sections SHALL flow past all of them to the
next unconditional section. Opening a hidden section by direct URL SHALL redirect the
respondent as an unknown-section miss does, not render it.

#### Scenario: Forward navigation skips hidden sections

- **GIVEN** sections "Your area" → "Area 1 count" … "Area 10 count" → "Thanks", each
  area section shown only for its option
- **WHEN** a respondent who answered Area = "Area 7" submits "Your area"
- **THEN** the next rendered section is "Area 7 count"

#### Scenario: Backward navigation skips the same sections

- **WHEN** that respondent presses Back on "Thanks"
- **THEN** the previous rendered section is "Area 7 count", not "Area 10 count"

#### Scenario: No matching rule flows past the fan

- **GIVEN** a respondent whose Area answer shows no area section (uncovered option)
- **WHEN** they submit "Your area"
- **THEN** the next rendered section is "Thanks"

#### Scenario: Direct URL to a hidden section does not render it

- **WHEN** a respondent opens the URL of a section hidden for their session
- **THEN** they are redirected instead of the hidden section rendering
