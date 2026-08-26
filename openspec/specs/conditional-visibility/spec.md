# conditional-visibility Specification

## Purpose

Visibility rules on questions and sections: the rule model (controlling choice question +
any-of option codes), cascade semantics, the server-side not-applicable contract, editor
authoring/badges/lint, duplication behaviour, and the `CONDITIONAL_VISIBILITY` kill switch.

## Requirements

### Requirement: A visibility rule can be attached to a question or a section

A creator SHALL be able to attach at most one visibility rule to a question or to a
section. A rule names a controlling question (input_type `choice` or `multichoice`,
positioned earlier in survey order) and one or more of its option codes. The item is
shown when the controlling question's answer includes any of the referenced codes
(any-of). An item without a rule SHALL always be shown. A section rule SHALL only
reference controlling questions from earlier sections; a question rule MAY reference a
controlling question from the same section or an earlier one, but only one earlier in
`order_number` when in the same section.

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
or every referenced option code is gone. The editor MUST badge such items as broken instead of
silently dropping or silently hiding. If only some referenced codes are gone, the rule
MUST keep matching on the remaining codes.

#### Scenario: Deleting a referenced option breaks the rule loudly

- **GIVEN** a section rule referencing only option "Area 3"
- **WHEN** the creator deletes option "Area 3" from the controlling question
- **THEN** the section is shown to all respondents
- **AND** the section row shows a broken-rule warning badge in the editor

#### Scenario: Reordering the controller past its dependent breaks the rule loudly

- **WHEN** the creator moves the controlling question after its dependent in survey order
- **THEN** the dependent is treated as always shown and badged as broken

### Requirement: Conditioned items are legible in the editor structure pane

Questions and sections carrying a rule SHALL display a branch badge summarising the
condition; a controlling question SHALL display how many rules depend on it; and the
editor SHALL warn when options of a controlling question referenced by sibling section
rules leave some options showing no section. The editor live preview SHALL apply
visibility rules so the creator can play both branches.

#### Scenario: Branch badges in the structure pane

- **GIVEN** ten sections each shown for one option of the Area question
- **WHEN** the creator views the structure pane
- **THEN** each section row shows its condition badge and the Area question shows a
  dependents count

#### Scenario: Uncovered option lint

- **GIVEN** options Area 1–9 each show a section and Area 10 shows none
- **WHEN** the creator views the structure pane
- **THEN** a hint reports that "Area 10" shows no section

#### Scenario: Preview plays a branch

- **WHEN** the creator selects the triggering option in the live preview
- **THEN** the dependent question appears in the preview as it would for a respondent

### Requirement: Duplication carries the rule within a survey

Duplicating a question or a section SHALL copy its visibility rule verbatim. Pasting a
copied item into a different survey SHALL drop the rule (its controller does not exist
there).

#### Scenario: Duplicated section keeps its rule

- **WHEN** the creator duplicates section "Area 1 count" (rule: Area = Area 1)
- **THEN** the copy carries the same rule, ready for re-ticking a different option

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
