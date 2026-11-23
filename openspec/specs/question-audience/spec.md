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

### Requirement: The public link starts at the first section respondents see
The respondent entry and the language picker SHALL send a respondent to the first section of the
chain that the visibility engine shows on the `respondent` surface for an empty answer set, not to
the head section. When the survey has sections but none of them is shown on that surface, the entry
SHALL render a page saying the survey has nothing to fill in yet (status 200, noindex) and SHALL NOT
redirect or create a session; a signed-in collaborator of the survey SHALL additionally see that the
sections are set to "Operators only" and a link to the editor. A survey without sections keeps its
current behaviour (the completion page).

#### Scenario: Operators-only first section is skipped
- **GIVEN** a published survey whose head section has audience `operators` and whose next section has audience `everyone`
- **WHEN** a respondent opens `/surveys/<uuid>/`
- **THEN** they are redirected to the second section

#### Scenario: No section reaches the public link
- **GIVEN** a published survey whose only section has audience `operators`
- **WHEN** a respondent opens `/surveys/<uuid>/`
- **THEN** the response is a 200 page saying the survey has nothing to fill in yet, with no redirect and no new session

#### Scenario: Direct section link never loops
- **GIVEN** the same survey
- **WHEN** a respondent opens the operators-only section's URL directly and follows the redirect
- **THEN** they land on that page and the redirect chain ends there

#### Scenario: The owner learns why
- **GIVEN** the same survey
- **WHEN** its owner opens the public link while signed in
- **THEN** the page names "Operators only" as the cause and links to the survey in the editor

#### Scenario: Multilingual survey
- **GIVEN** a multilingual survey whose head section has audience `operators` and whose next section has audience `everyone`
- **WHEN** a respondent picks a language
- **THEN** they are redirected to the second section

### Requirement: The editor warns when no section reaches the public link
The Build pane SHALL show a warning banner while the survey has sections and none of them is shown
on the `respondent` surface, naming "Operators only" as the cause. The check SHALL use the same
helper as the respondent entry.

#### Scenario: Banner shown
- **GIVEN** a survey whose only section has audience `operators`
- **WHEN** an editor opens its Build pane
- **THEN** the page carries the no-public-pages banner

#### Scenario: Banner absent
- **GIVEN** a survey with at least one section shown to respondents
- **WHEN** an editor opens its Build pane
- **THEN** the banner is not rendered

