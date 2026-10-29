# question-audience Specification

## Purpose
Who a section, group or question is for — respondents on the public link, operators on the
entry form, or everyone (change operator-entry). The administrator decides in the editor; the one
visibility engine enforces it on every surface.
## Requirements
### Requirement: Sections, groups and questions carry an audience
`SurveySection`, `QuestionGroup` and `Question` SHALL have an `audience` field with the values
`everyone` (default), `respondents` and `operators`. Existing rows SHALL read `everyone`. The
effective audience of an item SHALL be the intersection along its containment: a question in an
`operators` section is operator-only whatever its own value, a question in a `respondents` group
is respondent-only.

#### Scenario: Default
- **WHEN** a question is created without an audience
- **THEN** its `audience` is `everyone`

#### Scenario: Section audience cascades
- **GIVEN** a section with audience `operators` holding a question with audience `everyone`
- **WHEN** the respondent page renders
- **THEN** neither the section nor the question is shown

### Requirement: Audience is judged by the visibility engine per surface
`compute_visibility` and `popup_visibility` SHALL take a `surface` (`respondent` or `operator`)
and SHALL treat an item whose effective audience excludes that surface as hidden, with every
consequence hidden items already have: not rendered, never required, posted values discarded,
stored answers purged, skipped by section navigation and progress, and a hidden controller
satisfies no rule. The respondent page SHALL evaluate the `respondent` surface and the entry form
the `operator` surface. The `CONDITIONAL_VISIBILITY` kill switch SHALL NOT disable audience.

#### Scenario: Operator-only question is absent for respondents
- **GIVEN** a question with audience `operators`
- **WHEN** a respondent views its section
- **THEN** the question is not in the rendered form and a posted value for it is discarded

#### Scenario: Respondent-only question is absent for operators
- **GIVEN** a question with audience `respondents`
- **WHEN** an operator views its section in entry mode
- **THEN** the question is not rendered

#### Scenario: Operator-only controller shows respondents nothing
- **GIVEN** an `operators` choice question C and a section whose rule depends on C
- **WHEN** a respondent answers the survey
- **THEN** that section is hidden for the respondent and shown to an operator whose answer to C matches

#### Scenario: Kill switch off
- **WHEN** `CONDITIONAL_VISIBILITY` is False
- **THEN** rules are inert but an `operators` question is still absent from the respondent page

### Requirement: The editor sets the audience beside the visibility rule
The section, group and question modals SHALL offer the audience in the "Who sees this" block next
to the visibility rule, and the structure pane SHALL badge items whose audience is not `everyone`.
The audience control SHALL be available on every plan. The rule lint SHALL warn when a
controller's effective audience excludes respondents while the dependent item is shown to them.

#### Scenario: Badge
- **WHEN** a question's audience is `operators`
- **THEN** its row in the structure pane carries an "Operators only" badge

#### Scenario: Lint warning
- **GIVEN** an `operators` choice question controlling an `everyone` section
- **WHEN** the editor computes rule verdicts
- **THEN** the section carries a warning naming the controller as not shown to respondents

#### Scenario: Free workspace can set it
- **WHEN** an editor of a Free organisation saves a question with audience `operators`
- **THEN** the save succeeds

### Requirement: Changing the audience on a live survey is structural
On a published or closed survey a change of `audience` on a section, group or question SHALL be
a structural edit: refused on the live rows and routed to unpublished changes, named "the audience"
in the reasons.

#### Scenario: Live edit refused
- **WHEN** an editor changes a question's audience on a published survey without a draft
- **THEN** the service raises `StructureLocked` with "the audience" among the reasons

#### Scenario: Draft edit accepted
- **WHEN** the same change is made on the unpublished-changes copy
- **THEN** it saves and publishing carries it to the live rows

### Requirement: Audience travels with every copy and every interface
`audience` SHALL ride the unpublished-changes copy, publish, restore, duplicate and paste, ZIP
export and import (a missing key reads `everyone`; an unknown value is reported and read as
`everyone`), the REST API and MCP schemas, and the translation table. AI generation SHALL write no
audience.

#### Scenario: Draft copy keeps it
- **WHEN** unpublished changes are started on a survey with an `operators` section
- **THEN** the copy's section has audience `operators`

#### Scenario: ZIP round trip
- **WHEN** a survey with an `operators` question is exported and imported
- **THEN** the imported question has audience `operators`

#### Scenario: Old archive
- **WHEN** an archive without `audience` keys is imported
- **THEN** every item reads `everyone` with no warning

#### Scenario: API
- **WHEN** `PATCH /api/v1/surveys/{uuid}/questions/{id}` sends `{"audience": "operators"}`
- **THEN** the question's audience is `operators` and `GET` returns it

