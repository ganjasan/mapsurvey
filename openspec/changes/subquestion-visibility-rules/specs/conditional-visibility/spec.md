## ADDED Requirements

### Requirement: A visibility rule can be attached to a sub-question of a pop-up

A creator SHALL be able to attach at most one visibility rule to a sub-question of a geo question
or of an Objects-on-the-map question. The rule has the same shape as a question rule
(`{"question_code", "choice_codes"}`); its controlling question MUST be a `choice` or `multichoice`
sub-question of the **same pop-up** (same `parent_question_id`) with a smaller `order_number`. The
rule is evaluated **per feature / per object** against that feature's own sub-answers, never
against the session. A sub-question without a rule SHALL always be shown. Rules on sub-questions
SHALL NOT take part in section-level visibility.

#### Scenario: One follow-up per picked type

- **GIVEN** a point question with a `choice` sub-question "Type of place" (Park, School, Shop,
  Other) and four follow-ups each ruled on one option
- **WHEN** a respondent places a point and picks "School"
- **THEN** exactly the "School" follow-up is shown in the pop-up and the other three are not

#### Scenario: Nothing shown before the pick

- **WHEN** a respondent places a point and has not yet answered "Type of place"
- **THEN** none of the four follow-ups is shown

#### Scenario: Two features of one question decide independently

- **GIVEN** a respondent placed one point as "Park" and another as "School"
- **WHEN** the section is submitted
- **THEN** the first feature stores the Park follow-up only and the second the School follow-up only

#### Scenario: Editor offers siblings only

- **WHEN** the creator opens the Visibility block on a sub-question
- **THEN** the controlling-question picker lists only `choice`/`multichoice` sub-questions of the
  same pop-up that come before it, under one group "This pop-up"
- **AND** a section-level question is never offered

### Requirement: Pop-up dependents react live and hidden ones never post

Answering a controlling sub-question SHALL show or hide its dependent sub-questions in the same
pop-up immediately, without a server round-trip, on every pop-up of that question (a freshly placed
feature, a reopened feature, a layer object). Hidden dependents' inputs SHALL be disabled so they
are not serialised into the feature's properties or the object's posted fields; a value a hidden
card still carried from before SHALL be dropped from the feature's properties when the pop-up is
applied or closed. A hidden sub-question SHALL never count as required.

#### Scenario: Dependent appears on pick

- **WHEN** the respondent selects the triggering option in the pop-up
- **THEN** the dependent card appears in the same pop-up without reload

#### Scenario: Switching the pick hides the first follow-up and its value

- **GIVEN** the respondent picked "Park", typed into the Park follow-up and applied
- **WHEN** they reopen the pop-up, switch to "School" and apply
- **THEN** the Park follow-up is hidden, its value is gone from the feature, and the section POST
  stores no answer for it

#### Scenario: Restored feature opens in the right state

- **GIVEN** a feature restored on revisit with "School" stored
- **WHEN** its pop-up opens
- **THEN** the School follow-up is visible with its stored value and the others are hidden

### Requirement: Hidden sub-questions are not applicable server-side

For every posted geo feature and every posted layer object, the server SHALL evaluate the pop-up
rules against the choice sub-answers posted for that feature or object and SHALL store no answer
for a sub-question hidden under that state, whatever the client submitted. When the
`CONDITIONAL_VISIBILITY` kill switch is off, every sub-question SHALL be stored and shown as before.

#### Scenario: Tampered sub-answer to a hidden sub-question is discarded

- **WHEN** a feature's properties carry "Type of place" = Park and a value for the School follow-up
- **THEN** no child Answer row is stored for the School follow-up on that feature

#### Scenario: Object answers follow the same rule

- **GIVEN** an Objects-on-the-map question whose pop-up has a ruled follow-up
- **WHEN** `obj__<key>__<follow-up>` is posted for an object whose controller value does not match
- **THEN** no Answer row with `layer_object` set is stored for that follow-up

#### Scenario: Kill switch off

- **WHEN** `CONDITIONAL_VISIBILITY` is False
- **THEN** every sub-answer posted for a feature is stored and the pop-up shows every sub-question

### Requirement: Sub-question rules are legible in the editor

A sub-question carrying a rule SHALL show the branch badge on its row in the section list and in
the in-modal sub-question list; a controlling sub-question SHALL show the dependents count; the
"Shown when" pill SHALL appear under "Respondent sees" in the sub-question modal. A broken
sub-question rule (controller not a sibling, no longer a choice type, no longer earlier, or every
referenced option gone) SHALL fail open and be badged as broken. The editor section preview SHALL
toggle pop-up dependents the way the respondent page does. The Visibility block on a sub-question
follows the same read-only / structural gating as on a question.

#### Scenario: Badges on sub-question rows

- **GIVEN** "Type of place" controls four follow-ups
- **WHEN** the creator views the question in the section list or opens its modal
- **THEN** each follow-up row shows `if Type of place = <option>` and the controller row shows `4`

#### Scenario: Reordering the controller below its dependent breaks loudly

- **WHEN** the creator drags "Type of place" below a follow-up
- **THEN** that follow-up is shown on every feature and its row shows the broken-rule badge

#### Scenario: Rule change on a live survey is structural

- **GIVEN** a published survey
- **WHEN** the creator changes a sub-question's rule
- **THEN** the save is refused with the unpublished-changes affordance, as for a question rule

### Requirement: Sub-question rules travel with the pop-up

ZIP export SHALL write a sub-question's rule; import SHALL resolve it among the imported siblings
of the same parent (through the code remap) and drop an unresolvable rule with a report line.
Duplicating or pasting a parent question (within or across surveys) SHALL carry its sub-question
rules remapped to the cloned siblings. Publishing unpublished changes and restoring a version SHALL
keep the rules verbatim.

#### Scenario: Round trip through a ZIP

- **WHEN** a survey with a ruled follow-up is exported and imported into a database where the
  sub-question codes collide
- **THEN** the imported follow-up's rule names the remapped sibling code

#### Scenario: Duplicated point question keeps its pop-up logic

- **WHEN** the creator duplicates the point question
- **THEN** the copy's follow-ups are ruled on the copy's "Type of place", not the original's

#### Scenario: Read surfaces unchanged

- **GIVEN** sub-questions without a rule
- **WHEN** the data export and the object aggregates are built
- **THEN** their columns and counts are identical to before this change
