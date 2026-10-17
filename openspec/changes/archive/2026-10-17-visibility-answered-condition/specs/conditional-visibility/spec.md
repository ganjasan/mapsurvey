## ADDED Requirements

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

## MODIFIED Requirements

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
