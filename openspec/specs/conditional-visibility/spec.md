# conditional-visibility Specification

## Purpose

Visibility rules on questions, sections and pop-up sub-questions: the rule model (controlling
choice question + any-of option codes, or "answered (any option)"), cascade semantics, the server-side not-applicable contract, editor
authoring/badges/lint, duplication behaviour, and the `CONDITIONAL_VISIBILITY` kill switch.
## Requirements
### Requirement: A visibility rule can be attached to a question or a section

A creator SHALL be able to attach at most one visibility rule to a question or to a
section. A rule names a controlling question (input_type `choice` or `multichoice`,
positioned earlier in survey order) and either one or more of its option codes (any-of
mode) or the condition that it is answered at all (answered mode). In any-of mode the item is
shown when the controlling question's answer includes any of the referenced codes; in answered
mode when it includes at least one selected choice. An item without a rule SHALL always be
shown. A section rule SHALL only reference controlling questions from earlier sections; a
question rule MAY reference a controlling question from the same section or an earlier one,
but only one earlier in `order_number` when in the same section.

#### Scenario: Question shown when the controlling answer matches

- **GIVEN** question B has a rule "show when A = Yes"
- **WHEN** a respondent answers A with "Yes"
- **THEN** question B is rendered

#### Scenario: Question hidden when the controlling answer does not match

- **WHEN** a respondent answers A with "No" or has not answered A
- **THEN** question B is not rendered at all (not disabled, absent from the form)

#### Scenario: Any-of matching over a multichoice controller

- **GIVEN** a rule referencing codes [1, 3] of a multichoice controller
- **WHEN** the respondent's selection includes code 3 among others
- **THEN** the dependent item is shown

#### Scenario: Section hidden as a unit

- **GIVEN** section "Area 1 count" has a rule "show when Area = Area 1"
- **WHEN** a respondent answered Area = "Area 7"
- **THEN** no question of "Area 1 count" is rendered or reachable for that respondent

#### Scenario: Editor offers only valid controllers

- **WHEN** the creator opens the Visibility block on a question or section
- **THEN** the controlling-question picker lists only `choice`/`multichoice` questions
  positioned earlier in survey order, grouped by section

### Requirement: Question visibility is the AND of its own rule and its section's rule

A question SHALL be visible only if its section is visible AND its own rule (if any) is
satisfied. If the controlling question of a rule is itself hidden, the rule SHALL
evaluate as not satisfied (cascade).

#### Scenario: Section rule hides questions regardless of their own rules

- **GIVEN** a hidden section containing a question whose own rule is satisfied
- **THEN** that question is hidden

#### Scenario: Cascade through a hidden controller

- **GIVEN** question C shown when B = Yes, and B shown when A = Yes
- **WHEN** the respondent answers A = No and previously answered B = Yes
- **THEN** B is hidden and C is hidden as well

### Requirement: Hidden items are not applicable server-side

The server SHALL treat a hidden question as not applicable regardless of what the client
submits: a posted answer for a question hidden under the submitted answer state SHALL be
discarded, a hidden question's `required` SHALL never block progression, and after each
section submit the session's stored answers to questions hidden under the new answer
state SHALL be deleted (including geo answers, whose sub-answers are deleted with them).
When the `CONDITIONAL_VISIBILITY` kill switch is off, all items SHALL be treated as
visible and rules SHALL have no respondent-facing effect.

#### Scenario: Tampered answer to a hidden question is discarded

- **WHEN** a POST includes a value for a question hidden under the submitted answers
- **THEN** no Answer row is stored for that question

#### Scenario: Changing the controlling answer purges the abandoned branch

- **GIVEN** a respondent answered questions inside section "Area 7 count"
- **WHEN** they go back, change Area to "Area 4", and submit
- **THEN** the stored answers inside "Area 7 count" are deleted from the session

#### Scenario: Hidden required question does not block completion

- **GIVEN** a required question hidden for this respondent
- **WHEN** the respondent submits the section and finishes the survey
- **THEN** the session completes without an answer to that question

#### Scenario: Kill switch restores pre-change behaviour

- **WHEN** `CONDITIONAL_VISIBILITY` is set to False
- **THEN** every question and section renders for every respondent and no stored
  answers are visibility-purged

### Requirement: Same-section dependents react live on the client

Answering a same-section controller SHALL show or hide its dependent questions
immediately, without a server round-trip. Hidden
dependents' inputs SHALL be disabled so they are not submitted, and the client-side
required summary SHALL count only visible questions. Cross-section effects apply at the
next navigation.

#### Scenario: Dependent appears on selection

- **WHEN** the respondent selects the triggering option of a same-section controller
- **THEN** the dependent question card appears in place without a page reload

#### Scenario: Dependent disappears and does not post

- **WHEN** the respondent switches the controller away from the triggering option
- **THEN** the dependent card is removed and its inputs are excluded from the POST

### Requirement: Broken rules fail open and are surfaced in the editor

A broken rule MUST evaluate as always-visible (fail-open): broken means its controlling
question no longer exists, is no longer a choice type, is no longer earlier in order,
or — for an any-of rule — every referenced option code is gone. The editor MUST badge such items
as broken instead of silently dropping or silently hiding. If only some referenced codes are
gone, the rule MUST keep matching on the remaining codes. A rule in answered mode references no
option codes and therefore MUST NOT break when options are removed; it breaks only through its
controller.

#### Scenario: Deleting a referenced option breaks the rule loudly

- **GIVEN** a section rule referencing only option "Area 3"
- **WHEN** the creator deletes option "Area 3" from the controlling question
- **THEN** the section is shown to all respondents
- **AND** the section row shows a broken-rule warning badge in the editor

#### Scenario: Reordering the controller past its dependent breaks the rule loudly

- **WHEN** the creator moves the controlling question after its dependent in survey order
- **THEN** the dependent is treated as always shown and badged as broken

#### Scenario: Answered rule survives option changes

- **GIVEN** a section ruled "Area answered"
- **WHEN** the creator deletes every original option of Area and adds new ones
- **THEN** the rule is not badged as broken and keeps hiding the section until Area is answered

### Requirement: Conditioned items are legible in the editor structure pane

Questions and sections carrying a rule SHALL display a branch badge summarising the
condition (`if <controller> = <options>` for any-of, `if <controller> answered` for answered);
a controlling question SHALL display how many rules depend on it; and the editor SHALL warn when
options of a controlling question referenced by sibling section rules leave some options showing
no section — a section ruled "answered" counts as showing for every option. The editor live
preview SHALL apply visibility rules so the creator can play both branches.

#### Scenario: Branch badges in the structure pane

- **GIVEN** ten sections each shown for one option of the Area question
- **WHEN** the creator views the structure pane
- **THEN** each section row shows its condition badge and the Area question shows a
  dependents count

#### Scenario: Uncovered option lint

- **GIVEN** options Area 1–9 each show a section and Area 10 shows none
- **WHEN** the creator views the structure pane
- **THEN** a hint reports that "Area 10" shows no section

#### Scenario: Answered section covers every option

- **GIVEN** options Area 1–9 each show a section and a tenth section is ruled "Area answered"
- **THEN** no uncovered-option hint is shown

#### Scenario: Preview plays a branch

- **WHEN** the creator selects the triggering option in the live preview
- **THEN** the dependent question appears in the preview as it would for a respondent

### Requirement: Duplication carries the rule within a survey

Duplicating a question or a section SHALL copy its visibility rule verbatim. Creating a draft copy
or restoring an archived version SHALL copy every question and section rule verbatim (codes are
preserved, so the controller resolves in the copy). Pasting a copied item into a different survey
SHALL drop the rule (its controller does not exist there).

#### Scenario: Duplicated section keeps its rule

- **WHEN** the creator duplicates section "Area 1 count" (rule: Area = Area 1)
- **THEN** the copy carries the same rule, ready for re-ticking a different option

#### Scenario: Draft copy keeps the rules

- **WHEN** the creator starts unpublished changes on a survey with conditional questions and sections
- **THEN** the draft carries every rule, and publishing it keeps them on the live survey

#### Scenario: Cross-survey paste drops the rule

- **WHEN** a copied conditioned question is pasted into another survey
- **THEN** the pasted question has no visibility rule

### Requirement: Rules on published surveys follow the draft-copy path

Visibility rules SHALL be editable only where the survey structure is editable: the
Visibility block follows the editor's existing read-only gating, so on a published
survey it is read-only with the standard "Create a draft to edit" affordance, and
rules reach respondents by publishing a new version. Saving a rule SHALL NOT delete
or modify existing Answer rows. Sessions in flight on an older version SHALL keep
that version's rules.

#### Scenario: Published survey offers the draft path, not inline rule editing

- **GIVEN** a published survey
- **WHEN** the creator opens the Visibility block on a question or section
- **THEN** the controls are read-only with the standard draft affordance

#### Scenario: New version's rules apply to new sessions only

- **GIVEN** a live survey republished as a new version with a rule added
- **WHEN** a respondent whose session is pinned to the old version continues it
- **THEN** they see the old version's behaviour
- **AND** new sessions follow the new rule

#### Scenario: Collected answers survive rule changes

- **GIVEN** collected sessions on the previous version
- **WHEN** the new version with rules is published
- **THEN** all previously collected answers remain unchanged

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

### Requirement: A rule can require only that the controller is answered

A visibility rule SHALL support a second match mode, stored as
`{"question_code": <controller code>, "answered": true}` with no `choice_codes`. Such a rule is
satisfied when the controlling question has at least one selected choice, whichever option it is;
options added to the controller later count without any change to the rule. The mode SHALL be
available on every host a rule can be attached to — questions, sections and pop-up
sub-questions — and SHALL follow the same position, controller-type, cascade, fail-open,
server-side not-applicable and client-side live-toggle behaviour as the any-of mode. The two
modes SHALL be the only ones: a rule carrying `answered: true` is read as the answered mode even
if it also carries option codes.

#### Scenario: Section hidden until the controller is answered

- **GIVEN** section "Details" has the rule "Q1 answered"
- **WHEN** a respondent starts a fresh session
- **THEN** "Details" is skipped by navigation and not counted in progress
- **AND** after the respondent picks any option of Q1 and moves on, "Details" is shown

#### Scenario: Adding an option does not change the rule

- **GIVEN** a sub-question ruled "Type of place answered" and a controller with options A, B
- **WHEN** the creator adds option C and a respondent picks C
- **THEN** the sub-question is shown for that feature with no edit to the rule

#### Scenario: Multichoice controller with one selection

- **WHEN** the respondent ticks exactly one option of a multichoice controller
- **THEN** the dependent ruled "answered" is shown

#### Scenario: Hidden controller satisfies nothing

- **GIVEN** B ruled "A answered" and A itself hidden by its own rule
- **THEN** B is hidden even if an earlier answer to A is still stored

#### Scenario: Editor offers the mode

- **WHEN** the creator opens the Visibility block in conditional mode
- **THEN** below the controlling question a match select offers *any of…* and
  *answered (any option)*; choosing the latter hides the option list and shows one line of help
- **AND** saving stores the answered shape without option codes

#### Scenario: Both shapes round-trip through a ZIP

- **WHEN** a survey with one any-of rule and one answered rule is exported and imported
- **THEN** each imported item carries its rule in the same mode, with the controller code remapped
  if it collided
- **AND** an archive written before this change imports exactly as before

### Requirement: A visibility rule can be attached to a question group
A question group SHALL accept one visibility rule of the same shape and modes as a question rule
(any-of options, or "answered (any option)"). The controller SHALL be a choice or multichoice
question positioned before the group: for a section group, an earlier question of the same or an
earlier section; for a pop-up group, an earlier sub-question of the same pop-up. A question inside
the group SHALL NOT control its own group. A rule that breaks these conditions SHALL fail open and
be badged like any broken rule.

#### Scenario: Rule on a pop-up group
- **WHEN** a creator sets the group "Your visit" to show when "Type of place" is answered
- **THEN** the rule is stored on the group and the group row shows the branch badge naming
  "Type of place"

#### Scenario: Controller inside the group
- **WHEN** the group's controller is moved into that group
- **THEN** the rule is reported broken, the group is shown to everyone, and the editor badges it

### Requirement: A hidden group hides every question inside it
A question inside a group SHALL be visible only if its section is visible, its group is visible and
its own rule (if any) matches. Hidden questions inside a hidden group SHALL never be required,
their submitted answers SHALL be discarded, and their stored answers SHALL be purged, exactly as
for any hidden question. In a pop-up the group SHALL be evaluated per feature or per layer object
with that feature's own answers.

#### Scenario: Group appears after the type is picked
- **WHEN** a respondent places a point whose pop-up has the card group "Your visit" (three
  sub-questions, rule "Type of place answered") and has not picked a type
- **THEN** the group is not shown; after a type is picked the group appears with its three
  questions

#### Scenario: Hidden group answers do not post
- **WHEN** a respondent answers the group's questions, then clears "Type of place" and applies
- **THEN** the feature's stored answers contain none of the group's questions

#### Scenario: Member rule on top of a group rule
- **WHEN** a question inside a visible group has its own rule that does not match
- **THEN** that question is hidden and the rest of the group is shown

#### Scenario: Section group controlled from the same section toggles live
- **WHEN** a section group's controller is an earlier question of the same section and the
  respondent changes that answer
- **THEN** the group shows or hides immediately without a page load, and its inputs are disabled
  while hidden

### Requirement: Group rules travel with the survey
ZIP import SHALL resolve a group rule against the imported controllers (remapped codes) and drop an
unresolvable one with a report line. Duplicating a section or a pop-up SHALL remap a group rule to
the cloned controller; draft copies, publishing and version restore SHALL keep it verbatim. On a
published survey a change to a group rule SHALL be structural.

#### Scenario: Duplicate a point question with a ruled group
- **WHEN** a creator duplicates a point question whose pop-up group is ruled by its "Type of place"
  sub-question
- **THEN** the copy's group is ruled by the copy's "Type of place", not by the original's

