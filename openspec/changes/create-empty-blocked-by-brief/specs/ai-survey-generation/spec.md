## MODIFIED Requirements

### Requirement: AI brief panel on the create page
The Create New Survey page SHALL render an AI brief panel — a goal textarea, a "Who will
answer?" input, a "What should they mark on the map?" input, a use-case chip selector
(urban planning / citizen science / school routes / event mapping / other), a privacy
notice, and a "Generate draft" submit — only when an LLM provider is configured
(`AI_PROVIDER` resolvable and its credentials set). The existing "Create empty" path
SHALL remain available and behaviorally unchanged in all cases.

The brief SHALL be optional at the browser level: no brief field may carry the HTML5
`required` attribute, because the panel shares one `<form>` with the "Create empty" submit
and browser-level validation applies to the whole form. `goal` remains required on the
server for the generate path only. A creator who never intends to use AI SHALL be able to
reach the manual path without typing anything into the brief.

#### Scenario: Provider configured
- **WHEN** an authenticated editor opens `/editor/surveys/new/` and the key for the selected `AI_PROVIDER` is set
- **THEN** the AI brief panel with the "Generate draft" button is rendered alongside the existing name/languages/map fields, including a privacy notice stating the brief is processed by the AI provider and that survey answers are never sent to AI providers

#### Scenario: Provider not configured
- **WHEN** the key for the selected `AI_PROVIDER` is empty
- **THEN** the AI panel is not rendered, the page shows only the manual creation form, and no AI code path can be reached

#### Scenario: Create empty with an untouched brief
- **WHEN** an authenticated editor submits the create form with `action=empty`, a survey name, and every brief field left blank
- **THEN** the survey is created with its default first section and the editor is redirected to it, exactly as when the AI panel is absent

#### Scenario: Brief fields do not block the browser
- **WHEN** the create page is rendered with the AI panel present
- **THEN** no brief field carries the HTML5 `required` attribute, so a click on "Create empty" reaches the server rather than being refused by browser validation

#### Scenario: Generate draft still requires a goal
- **WHEN** an authenticated editor submits `action=generate` with a blank `goal`
- **THEN** no `AIGenerationEvent` is created and the status slot receives the invalid-brief fragment naming the goal field
