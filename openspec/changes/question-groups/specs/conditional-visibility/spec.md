## ADDED Requirements

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
