# ai-survey-generation (delta)

## MODIFIED Requirements

### Requirement: AI brief panel on the create page
The Create New Survey page SHALL render an AI brief panel — a goal textarea, a "Who will
answer?" input, a "What should they mark on the map?" input, a use-case chip selector
(urban planning / citizen science / school routes / event mapping / other), a privacy
notice, and a "Generate draft" submit — only when an LLM provider is configured
(`AI_PROVIDER` resolvable and its credentials set). When the `CREATE_STEER_AI` flag is
on, the goal textarea SHALL be the only brief field visible by default and SHALL receive
autofocus (except when the survey-name field is visible, in which case autofocus is not
emitted); the audience, map-target, and use-case fields SHALL sit inside a native
disclosure ("Add details (optional)") that is rendered expanded whenever any of those
fields is bound with a value or carries a validation error. The "Create empty" path
SHALL remain available in all cases; with `CREATE_STEER_AI` on and a non-empty goal, the
first empty-action click per page load SHALL surface a dismissible inline offer to
generate a draft instead (see the empty-path intercept requirement), after which the
empty path proceeds unchanged. With a blank goal, or with `CREATE_STEER_AI` off, the
empty path SHALL be behaviorally identical to the pre-intercept behavior.

#### Scenario: Provider configured
- **WHEN** an authenticated editor opens `/editor/surveys/new/` and the key for the selected `AI_PROVIDER` is set
- **THEN** the AI brief panel with the "Generate draft" button is rendered alongside the existing name/languages/map fields, including a privacy notice stating the brief is processed by the AI provider and that survey answers are never sent to AI providers

#### Scenario: Provider not configured
- **WHEN** the key for the selected `AI_PROVIDER` is empty
- **THEN** the AI panel is not rendered, the page shows only the manual creation form, and no AI code path can be reached

#### Scenario: Brief collapsed to one field by default
- **WHEN** the create page renders with `CREATE_STEER_AI` on and an unbound brief form
- **THEN** only the goal textarea is visible, and the audience, map-target, and use-case controls are inside a collapsed "Add details (optional)" disclosure

#### Scenario: Disclosure reopens for dirty fields
- **WHEN** the page re-renders after a submission in which the audience field carried a value
- **THEN** the disclosure is rendered expanded so the value is visible

#### Scenario: Flag off restores the flat panel
- **WHEN** `CREATE_STEER_AI` is off
- **THEN** all brief fields render flat (no disclosure, no autofocus attribute), matching the pre-change markup

## ADDED Requirements

### Requirement: Empty-path intercept when a goal is written
The create page SHALL intercept the empty-creation action when `CREATE_STEER_AI` is on,
an LLM provider is configured, and the goal field is non-empty: the first activation per
page load does not submit and instead renders an inline, non-modal prompt offering to generate a draft
("Generate draft") or continue empty ("Create empty anyway"). Accepting SHALL route to
the existing draft path for the active surface (desktop: the Generate submission; wizard:
the draft path continuing to the map step). Declining SHALL immediately resume the
original empty-creation flow. The intercept SHALL fire at most once per page load, SHALL
never appear when the goal is blank, and SHALL introduce no additional server round-trip.

#### Scenario: Intercept on filled goal (desktop)
- **WHEN** a creator with a non-empty goal clicks "Create empty" on the desktop layout for the first time
- **THEN** no POST is sent, and the inline prompt with "Generate draft" and "Create empty anyway" appears

#### Scenario: Decline proceeds empty
- **WHEN** the creator clicks "Create empty anyway" in the prompt
- **THEN** the empty-creation submission proceeds exactly as if the intercept did not exist, and an empty survey is created

#### Scenario: Accept routes to the draft path
- **WHEN** the creator clicks "Generate draft" in the prompt
- **THEN** the existing generation flow starts with the current brief, identical to having used the primary Generate action

#### Scenario: Blank goal never intercepts
- **WHEN** a creator with an empty goal field activates the empty-creation action
- **THEN** the empty survey is created immediately with no prompt

#### Scenario: Once per page load
- **WHEN** the intercept was already shown and dismissed on this page load and the creator activates the empty action again
- **THEN** the empty path proceeds without a second prompt

### Requirement: Example brief chips
When `CREATE_STEER_AI` is on and an LLM provider is configured, the create page SHALL
render a row of example chips above the goal textarea ("Try an example"), each carrying a
prewritten complete brief (goal, audience, map target, use case) for a common geo-survey
scenario. Activating a chip SHALL fill all four brief fields with its example values
(replacing current values), open the "Add details" disclosure so the filled fields are
visible, focus the goal textarea, mark the chip active, and reveal a Clear chip. The
Clear chip SHALL reset all four brief fields to their initial state, collapse the
disclosure, and hide itself. The chips SHALL NOT be rendered when the flag is off or no
provider is configured.

#### Scenario: Chip fills the whole brief
- **WHEN** a creator clicks an example chip
- **THEN** the goal, audience, and map-target fields contain that chip's example values, the matching use-case is selected, the disclosure is open, and the goal has focus

#### Scenario: Clear resets the brief
- **WHEN** a creator clicks the Clear chip after picking an example
- **THEN** all four brief fields return to their initial state, the disclosure collapses, no example chip is marked active, and the Clear chip hides

#### Scenario: Chips absent with the flag off
- **WHEN** `CREATE_STEER_AI` is off
- **THEN** no example chips are rendered
