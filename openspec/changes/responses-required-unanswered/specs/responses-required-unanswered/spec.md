## ADDED Requirements

### Requirement: One definition of missing required questions
A session's *missing required questions* SHALL be the required top-level questions of the
session's own survey version that were visible to that session and have no stored answer that
satisfies them, wherever in the survey they sit and whichever sections the respondent reached.
Visibility SHALL be decided by the conditional-visibility engine on the session's stored answers
(section rules, group rules, question rules, audience), on the operator surface for paper and
operator-entered sessions and on the respondent surface otherwise. `html` and `image` blocks are
never required. A question is satisfied by at least one top-level answer carrying a value; a geo
question with a minimum number of features needs at least that many; an "Objects on the map"
question with a minimum number of objects needs answers about at least that many distinct
objects. Answers left blank by inline editing SHALL NOT satisfy a question.

#### Scenario: Required question on a later page never reached
- **WHEN** a survey has a required question on page 3 and a respondent answered pages 1 and 2
  and left
- **THEN** the session's missing required questions name that question

#### Scenario: Optional last page skipped
- **WHEN** every required question was answered and the respondent skipped an optional last page
- **THEN** the session has no missing required questions

#### Scenario: Hidden by a visibility rule
- **WHEN** a required question is shown only to respondents who chose "Cyclist" and the
  respondent chose "Driver"
- **THEN** that question is not missing for the session

#### Scenario: Hidden section
- **WHEN** a whole section is hidden by its rule for a respondent and holds a required question
- **THEN** that question is not missing for the session

#### Scenario: Operator-only question on a paper sheet
- **WHEN** a required question is shown to operators only, and a paper sheet entered by an
  operator left it blank
- **THEN** it is missing for the paper session and never missing for an online session

#### Scenario: Geo minimum
- **WHEN** a required point question asks for at least 3 places and the session placed 2
- **THEN** that question is missing for the session

#### Scenario: Objects minimum
- **WHEN** an "Objects on the map" question asks about at least 2 objects and the session
  answered about 1
- **THEN** that question is missing for the session

#### Scenario: Blank row from inline editing
- **WHEN** a creator clears a required text answer inline on Responses
- **THEN** that question becomes missing for the session

### Requirement: Completed means every visible required question answered
A session SHALL be *completed* when it is not empty and has no missing required questions. A
survey without required questions SHALL count every non-empty session as completed. Reaching the
last section or the thank-you page SHALL NOT be part of the definition. The Responses Overview,
the Responses table's Complete filter, the dashboard cards, the export's `completed_only`, the
REST response summary and the MCP response tools SHALL all read completion through one shared
queryset helper over one stored per-session state, so none of them can disagree.

#### Scenario: Four surfaces agree
- **WHEN** a survey has 5 non-empty sessions, 3 of them with no missing required questions
- **THEN** the Overview shows 3 completed (60 %), the Complete chip shows 3, `completed_only=1`
  exports 3 sessions, and the API summary reports `completed: 3`

#### Scenario: No required questions
- **WHEN** a survey has no required questions and 4 non-empty sessions
- **THEN** every surface reports 4 completed

### Requirement: The stored state follows every write that can change it
The per-session state SHALL be recomputed after every section submission on the respondent,
operator-entry and paper-entry surfaces (forward and back), after an inline answer edit on
Responses, after paper review replaces machine-read answers, and for imported sessions after a
ZIP import of responses. When a question's `required`, minimum number of features or minimum
number of objects changes, or a question with answers is deleted, the state of every non-empty
session of that survey version SHALL be recomputed, in the background with a synchronous
fallback when the task cannot be queued. Existing sessions SHALL be backfilled when the change is
deployed.

#### Scenario: Making a question required on a live survey
- **WHEN** a creator ticks Required on a question of a published survey whose 10 sessions all
  completed and 4 of them skipped that question
- **THEN** after the save, 6 sessions are completed and 4 show the question as missing

#### Scenario: Back navigation saves and recomputes
- **WHEN** a respondent answers a required question, goes Back and clears it
- **THEN** the session shows that question as missing

#### Scenario: Publishing does not change old sessions
- **WHEN** a creator publishes unpublished changes that add a required question
- **THEN** sessions answered on the previous version keep their state, judged against the
  version they answered

### Requirement: Quiet marker with the unanswered questions named
The Responses table SHALL show, on a non-empty session with missing required questions, a small
neutral marker — no error colour, no counter chip, no "issue" or "violation" wording. Hovering or
focusing it SHALL show a tooltip that says in plain words what it means and names the questions,
e.g. "Didn't answer 2 required questions: Where do you live?, How often do you visit the park?".
Empty sessions SHALL keep their "Empty" badge and carry no marker. The marker column SHALL sort
by the number of missing questions.

#### Scenario: Tooltip names the questions
- **WHEN** a session missed the required questions "Where do you live?" and "Age group"
- **THEN** its marker's tooltip reads "Didn't answer 2 required questions: Where do you live?,
  Age group"

#### Scenario: Complete session shows nothing
- **WHEN** a session answered every visible required question
- **THEN** its row shows no marker

### Requirement: One filter for required questions unanswered
The Responses toolbar SHALL offer the filters All, Complete and Required unanswered (with counts)
next to Trash. Complete and Required unanswered SHALL partition the shown non-empty sessions. The
filter SHALL travel in the table URL as `required=missing` (Complete keeps its existing value);
an `issues=` parameter from an old link SHALL be ignored. The phone filter sheet SHALL offer the
same options.

#### Scenario: Filter returns exactly the marked sessions
- **WHEN** the creator selects Required unanswered
- **THEN** the table lists exactly the sessions that carry the marker, and the chip count equals
  their number

### Requirement: Crossed polygon edges are noted on the answer
A polygon answer whose edges cross SHALL keep a quiet mark on its table cell, in the same neutral
style as the required marker, with the tooltip "The edges of this shape cross each other. It may
not open correctly in GIS software." No other per-answer mark SHALL be shown on Responses: no
out-of-range, numeric outlier, short text, area outlier or empty-required mark, in the table, the
detail surface or the map.

#### Scenario: Crossed polygon
- **WHEN** a session drew a bow-tie polygon
- **THEN** that cell shows the mark and the tooltip above

#### Scenario: Short text is not marked
- **WHEN** a text answer is "ok"
- **THEN** the cell shows no mark

### Requirement: Removed signals stay removed
Responses SHALL NOT label any session as duplicate, fast, or incomplete by last section, and
SHALL NOT offer settings for them. The survey-level validation-settings dialog and its endpoint
SHALL NOT exist; values stored in `SurveyHeader.validation_settings` SHALL be ignored.

#### Scenario: Two respondents on the same phone model
- **WHEN** two sessions of one survey started ten minutes apart from the same User-Agent string
- **THEN** neither carries any mark and both count as completed if they answered every visible
  required question

### Requirement: Creators are told why the numbers changed
The change SHALL ship a "What's new" entry saying that the Issues column is gone because most of
its marks were wrong, that "completed" now means "answered every required question" so completion
rates change, that number Min/Max now limit what respondents can enter, and that responses moved
to the trash can be restored from it.

#### Scenario: Entry loads
- **WHEN** the changelog entries are loaded
- **THEN** the new entry parses and `ChangelogEntriesTest` passes
