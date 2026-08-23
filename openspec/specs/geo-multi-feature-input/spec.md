# geo-multi-feature-input Specification

## Purpose
A single geo question (point/line/polygon) accepts several features from one respondent.
This capability covers how that multiplicity is made visible on the respondent side —
counter, "add another" invitation, in-button progress — and how creators bound it with
per-question min/max feature limits. It exists because an invisible multiplicity makes
creators clone geo questions ("Mark the 1st / 2nd location"), which fragments one GeoJSON
layer into many single-feature ones.
## Requirements
### Requirement: Completing a feature returns the respondent to the question list
The system SHALL return the respondent to the section panel after a feature is completed —
its sub-question popup saved, or its geometry drawn when the question has no sub-questions —
so the respondent explicitly picks which question to answer next. Drawing mode SHALL NOT
re-arm automatically: with several geo questions in a section an auto-re-armed question
gives no orientation about which question is being answered. The completed question SHALL
remain immediately re-selectable (one click starts the next feature) unless it reached
`max_features`.

#### Scenario: Popup save returns to the panel
- **WHEN** a respondent places a point on a geo question with sub-questions and clicks the
  popup's apply button
- **THEN** the popup closes, the section panel with all questions is visible again, and no
  drawing mode is active

#### Scenario: Adding the next feature is one click away
- **WHEN** a respondent has just completed a feature on a question below its max
- **THEN** clicking that question's button starts drawing the next feature immediately

#### Scenario: Max reached disables the button
- **WHEN** a respondent completes a feature and the question's feature count now equals
  `max_features`
- **THEN** the question's draw button is disabled

### Requirement: Draw button reflects multi-feature state without losing the title
The draw button of a geo question SHALL show how many features the respondent has placed on
that question (a counter chip, hidden at zero) and an "add another" invitation in its
subtitle line once at least one feature exists. The question's own title SHALL never be
replaced — it is the only thing distinguishing several geo questions in one section. Each
indicator SHALL be scoped to its own question.

#### Scenario: Counter appears after the first feature
- **WHEN** a respondent saves the first feature on a geo question
- **THEN** the button shows a counter chip with "1", keeps the question title, and its
  subtitle invites adding another

#### Scenario: Two geo questions with features stay distinguishable
- **WHEN** a section has two geo questions and the respondent has added features to both
- **THEN** each button still shows its own question title

#### Scenario: Counters are per question
- **WHEN** a section has two geo questions and the respondent has placed 3 features on the
  first and none on the second
- **THEN** the first button shows 3, the second shows no chip and its original subtitle

### Requirement: Placed features are managed on the map, not in a panel list
The system SHALL NOT render a per-question list of placed features in the section panel
(an early build had one; with several geo questions it duplicated the map pins and the
counter while adding noise — "Answer 1 / Answer 2" rows carry no information of their own).
Editing and deleting a placed feature SHALL remain available through the feature's popup
on the map, as today.

#### Scenario: No list rows in the panel
- **WHEN** a respondent has placed several features on a geo question
- **THEN** the section panel shows the counter chip and progress for that question but no
  per-feature rows

#### Scenario: Feature management via the map
- **WHEN** a respondent clicks a placed feature on the map
- **THEN** its popup opens with edit and delete controls (existing behaviour)

#### Scenario: Deleting on the map revives a maxed-out button
- **WHEN** a question is at `max_features` and the respondent deletes one of its features
  through the feature's map popup
- **THEN** the counter and progress update and the disabled button becomes enabled again

#### Scenario: Restored session answers are counted
- **WHEN** a respondent returns to a section whose geo answers were previously submitted
- **THEN** the restored features are reflected in their questions' counters and progress
  exactly like newly placed ones

### Requirement: Feature count limits per geo question
A geo question SHALL support optional `min_features` and `max_features` in its
`validation_settings`. `max_features` SHALL be enforced in the respondent UI (button
disabled, drawing not re-armed); on the section POST the server SHALL store at most
`max_features` features for the question, discarding the excess (the section POST has no
error-re-render path — `required` itself is client-enforced there — so the server's job is
to keep stored data within bounds, not to produce form errors). `min_features` SHALL be
enforced client-side on forward navigation only, exactly like `required`; navigating back
SHALL never block on it. Absent keys SHALL mean unlimited (today's behaviour).

#### Scenario: Progress renders inside the button, only when configured
- **WHEN** a geo question has `max_features` (or a nonzero `min_features`) set
- **THEN** the respondent sees an "N of M marked" progress indicator **inside that
  question's draw button** (so it is unambiguous which question it belongs to); a question
  with neither key set shows no progress indicator

#### Scenario: Server stores at most max features
- **WHEN** a section POST carries more features for a question than its `max_features`
  (a tampered or scripted submission — the UI prevents this)
- **THEN** only the first `max_features` features are stored as answers

#### Scenario: Below minimum blocks forward navigation
- **WHEN** a respondent submits a section forward with fewer features than a question's
  `min_features`
- **THEN** the client highlights the question and blocks the submit, the same way an
  unanswered `required` question does

#### Scenario: Back navigation ignores minimum
- **WHEN** a respondent navigates back from a section with an unmet `min_features`
- **THEN** navigation proceeds

### Requirement: Editor configures feature count limits
The question form modal SHALL offer min/max feature inputs for geo question types
(point/line/polygon) and persist them as integers in `validation_settings.min_features` /
`max_features`. Blank inputs SHALL remove the keys. The editor SHALL reject max < min and
values below 0 (min) / 1 (max).

#### Scenario: Round trip
- **WHEN** a creator sets min 1 and max 5 on a point question and saves
- **THEN** reopening the modal shows 1 and 5, and the question's `validation_settings`
  contains `{"min_features": 1, "max_features": 5}`

#### Scenario: Clearing the limits
- **WHEN** a creator blanks both inputs and saves
- **THEN** neither key remains in `validation_settings`

#### Scenario: Invalid range rejected
- **WHEN** a creator submits max 2 with min 4
- **THEN** the form re-renders with a validation error and nothing is saved

