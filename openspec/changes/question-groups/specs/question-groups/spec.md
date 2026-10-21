## ADDED Requirements

### Requirement: A group contains a run of questions in a section or in a pop-up
The system SHALL provide a question group: a container with a code, a title, a rich-text
description, a display style and an optional visibility rule. A group SHALL belong to one section
and, optionally, to one geo or Objects-on-the-map parent question; a section group SHALL contain
only top-level questions of that section and a pop-up group only sub-questions of its parent.
Groups SHALL NOT nest. A group SHALL NOT be a question: it collects no answer and creates no
answer row, and the questions inside keep their own answers.

#### Scenario: Group in a section
- **WHEN** a creator adds a group "About you" to a section and moves two questions into it
- **THEN** both questions keep their section and their answers are stored as rows on those
  questions, with no row for the group

#### Scenario: Group in a pop-up
- **WHEN** a creator adds a group "Your visit" under a point question and moves three of its
  sub-questions into it
- **THEN** the three sub-questions keep their parent, and the group is shown inside every pop-up
  of that point question

#### Scenario: No nesting
- **WHEN** a creator drags a group onto another group's question list
- **THEN** the drop is refused and the group stays at its level

### Requirement: Groups share one continuous order with the questions around them
A group's position SHALL be a slot in the same order as its sibling questions, and its members
SHALL follow it contiguously. Reordering a list SHALL renumber groups and questions as one
sequence and SHALL set each question's group from where it was dropped. A rendering surface SHALL
NOT lose a question if the members of a group are found non-contiguous.

#### Scenario: Order after a drag
- **WHEN** a section holds `Q1, [G: Q2, Q3], Q4` and the creator drags `Q4` into `G` after `Q3`
- **THEN** the stored order is `Q1, G, Q2, Q3, Q4`, `Q4` belongs to `G`, and the respondent sees
  `Q1` then the group with `Q2, Q3, Q4`

#### Scenario: Drag out of a group
- **WHEN** the creator drags `Q2` out of `G` to the top of the section
- **THEN** `Q2` no longer belongs to any group and is first in the section

#### Scenario: Reorder refuses foreign ids
- **WHEN** a reorder request names a question of another section or another pop-up
- **THEN** the request is refused with 400 and nothing is renumbered

#### Scenario: Non-contiguous members still render
- **WHEN** stored data places a question of another group or no group between two members of `G`
- **THEN** every question is rendered once, in order, and `G`'s header is repeated before its
  second run rather than any question being dropped

### Requirement: Groups render in three display styles on every respondent surface
A group SHALL render as `plain` (title and description, questions in the flow), `card` (a framed
block around its questions) or `collapsible` (a card whose title is a button with a chevron; the
body starts closed and opens on tap). The same markup SHALL be used in respondent sections, geo
pop-ups, layer-object pop-ups, the editor's section preview and the group modal's "Respondent
sees" pane. The title SHALL be escaped; the description SHALL be rendered as sanitized creator
markup. A group with no rendered question SHALL NOT render.

#### Scenario: Card in a pop-up
- **WHEN** a respondent places a point whose pop-up holds the card group "Your visit" with three
  questions
- **THEN** the pop-up shows one framed block titled "Your visit" with its description and the three
  questions inside

#### Scenario: Collapsible opens on tap
- **WHEN** a respondent taps the title of a collapsible group
- **THEN** the body opens and the button reports `aria-expanded="true"`; a second tap closes it

#### Scenario: Collapsed group with an unanswered required question
- **WHEN** a respondent submits a section in which a closed collapsible group holds a required
  question with no answer
- **THEN** the group opens and the required question is focused with its error, and the section is
  not submitted

#### Scenario: Empty group
- **WHEN** every question of a group is hidden by its own rule from an earlier section
- **THEN** neither the group's title nor its description is rendered

### Requirement: Group text is translated like question text
A group's title and description SHALL have per-language translations for every language of the
survey, edited in the group modal, shown to respondents in their chosen language with fallback to
the primary language, counted by translation gaps, and carried by ZIP export/import and every copy.
Every write of a description, including translations, import and the live preview, SHALL pass the
creator-HTML coercion used for question help text.

#### Scenario: Respondent in a second language
- **WHEN** a survey in English and Portuguese has a group titled "Your visit" / "A sua visita" and
  a respondent picks Portuguese
- **THEN** the group title reads "A sua visita"

#### Scenario: Missing translation falls back
- **WHEN** the Portuguese description is empty
- **THEN** the respondent sees the English description and the editor reports the gap

#### Scenario: Script in a description
- **WHEN** a description containing `<script>` is saved through the modal or imported from a ZIP
- **THEN** the stored description contains no script element

### Requirement: Creators author groups in the editor
The editor SHALL offer "Add group" next to "New Question" in a section and next to "+ Add
Sub-question" under a geo or Objects-on-the-map question. A group row SHALL show its title, the
first line of its description, `Group · N` (N = questions inside), its display style, its
visibility badges and its comment badge, with its questions nested beneath. The group modal SHALL
offer Name, Description, Display as, Visibility, translations, the list of questions inside and a
"Respondent sees" preview of the unsaved group. Questions SHALL be dragged into and out of a group
and a group SHALL be dragged as a whole, with long-press on touch.

#### Scenario: Add a group under a point question
- **WHEN** a creator clicks "Add group" under a point question, enters "Your visit" and creates it
- **THEN** an empty group row titled "Your visit" with `Group · 0` appears at the end of that
  question's sub-question list

#### Scenario: Add a question straight into a group
- **WHEN** a creator clicks "Add question to group" under a group and picks a type
- **THEN** the new question is created inside that group, after its last question, and the
  list shows it there without a drag

#### Scenario: Preview of an empty group
- **WHEN** the creator opens the modal of a group with no questions
- **THEN** "Respondent sees" shows the group in the chosen style with two example questions,
  marked as examples, between a faded question before and after it, and Tips explain when to
  use each style

#### Scenario: Preview while editing
- **WHEN** the creator switches Display as from card to collapsible without saving
- **THEN** the "Respondent sees" pane re-renders the group collapsed with a chevron

### Requirement: A question can be moved between the section and a pop-up by drag
The editor SHALL let a creator drag a section question into the pop-up of a geo or
Objects-on-the-map question of the same section (into the pop-up list or into one of its
groups), and a pop-up sub-question out to the section. A question whose type cannot live in a
pop-up (point, line, polygon, spray area, Objects on the map) SHALL NOT be accepted by a pop-up.
Because a section question is answered once per respondent and a sub-question once per placed
mark, existing answers of the moved question SHALL be deleted, behind the same answer-loss
acknowledgement as a delete. The moved question's own visibility rule and every rule that names
it as controller SHALL be removed when the move makes them invalid, and the editor SHALL say
which. On a live survey the move SHALL be a structural edit.

#### Scenario: Section question into a pop-up group
- **WHEN** a creator drags the unanswered section question "Your age" into the group "Your
  visit" of a point question
- **THEN** it becomes a sub-question of that point question inside "Your visit", and the list
  shows it there

#### Scenario: Answered question
- **WHEN** the moved question has 5 answers and the move is posted without the acknowledgement
- **THEN** the response is 409 reporting 5 answers at risk and nothing moves; with the
  acknowledgement the question moves and its 5 answers are deleted

#### Scenario: Geo question refused by a pop-up
- **WHEN** a creator drags a polygon question into a pop-up
- **THEN** the drop is refused and nothing changes

#### Scenario: Rules that the move breaks
- **WHEN** the moved question controlled a rule of another section question
- **THEN** that rule is removed and the editor names the item that lost it

### Requirement: Deleting a group asks what happens to its questions
Deleting a group that holds questions SHALL ask the creator to choose between deleting only the
group and deleting the group together with its questions; "only the group" SHALL be the default
choice. Deleting only the group SHALL keep every question inside it, ungrouped, in the same place in
the order. Deleting with questions SHALL delete the group, its questions and their sub-questions,
and SHALL go through the same answer-loss acknowledgement as deleting a question: when any of those
questions has answers, the server SHALL refuse without the acknowledgement and report how many
answers would be destroyed. An empty group SHALL be deleted after a plain confirmation.

#### Scenario: Delete only the group
- **WHEN** a creator deletes the group "Your visit" holding three questions and keeps the default
  choice "Delete only the group"
- **THEN** the three questions are in the list where the group was, with no group, and their
  answers are untouched

#### Scenario: Delete with questions that have answers
- **WHEN** the creator chooses "Delete the group and its 3 questions" and those questions have 12
  answers, without the acknowledgement
- **THEN** the response is 409 reporting 12 answers at risk, and the group, the questions and the
  answers still exist

#### Scenario: Delete with questions, acknowledged
- **WHEN** the same request carries the acknowledgement
- **THEN** the group, its three questions and their 12 answers are deleted

#### Scenario: Empty group
- **WHEN** a creator deletes a group with no questions
- **THEN** the dialog offers no choice and the group is deleted after one confirmation

### Requirement: Live-survey edits to groups follow the safe/structural split
The system SHALL let a creator edit a group's title, description, display style and translations
in place on a published or closed survey, re-screened like other live creator text. Adding or deleting a
group, changing its rule, and moving questions in or out of it SHALL be structural edits that go
to "Unpublished changes".

#### Scenario: Retitle a group on a live survey
- **WHEN** a creator edits the title of a group on a published survey
- **THEN** the change is saved in place, respondents see the new title, and no draft is created

#### Scenario: Add a group on a live survey
- **WHEN** a creator clicks "Add group" on a published survey
- **THEN** the gate offers to start "Unpublished changes" and nothing is added to the live survey

### Requirement: Groups travel with every copy of a survey
ZIP export SHALL write each group with its code, title, description, display style, visibility
rule, order and translations, and each question SHALL name its group by code. Import SHALL
recreate groups and memberships, remap colliding codes, and drop an unresolvable membership with a
report line; an archive without groups SHALL import unchanged. Duplicating a section or a geo
question SHALL clone its groups with their members; duplicating a question inside a group SHALL
keep it in that group right after the source; a pasted question SHALL land ungrouped. Draft copies,
publishing a draft and restoring a version SHALL keep groups with their codes and rules.

#### Scenario: Round trip
- **WHEN** a survey with a section group and a pop-up group is exported and imported
- **THEN** the imported survey has both groups with the same titles, styles, rules, order and
  members

#### Scenario: Publish unpublished changes
- **WHEN** a creator adds a group in "Unpublished changes" and publishes them
- **THEN** the live survey shows the group and earlier answers to its questions are kept

### Requirement: Comment threads can anchor to a group
A workspace member SHALL be able to open a comment thread on a group from its row or its modal.
The anchor SHALL be the group's code, so a thread survives publishing unpublished changes.

#### Scenario: Thread on a group
- **WHEN** a member opens comments on the group "Your visit" and posts
- **THEN** the group row shows a comment badge with 1 and the thread is still attached after the
  survey's unpublished changes are published

### Requirement: Groups change nothing on read surfaces
Data export, Responses, public results and object statistics SHALL be unchanged by groups: the
same columns in the same order as the same questions without groups.

#### Scenario: Export of a grouped pop-up
- **WHEN** a survey whose pop-up group "Your visit" holds three sub-questions is exported
- **THEN** the export carries three ordinary columns for them, the same as without the group
