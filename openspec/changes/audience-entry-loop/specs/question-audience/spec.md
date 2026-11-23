## ADDED Requirements

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
