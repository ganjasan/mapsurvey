## MODIFIED Requirements

### Requirement: Start page with three ways to begin
The system SHALL serve `GET /editor/surveys/start/` to signed-in creators whose role in the
active organization is `editor` or above, rendering three cards: *Start from scratch*,
*Draft with AI* and *Use your AI assistant*. A single click (or Enter/Space on the focused
card) on an actionable card SHALL perform that card's action, with no intermediate selection
step and no detail block revealed elsewhere on the page. *Start from scratch* SHALL be the
submit button of a POST form to the blank-creation endpoint, so the whole card submits it.
*Draft with AI* SHALL be a link to `/editor/surveys/new/?from=start`, and SHALL render
disabled, without a link, with an explanation when no LLM provider is configured. The AI-draft
path SHALL be called the *Wizard* on every creator surface — the start card (*Survey wizard*,
label "Wizard"), the create page's brief panel, the empty-path intercept, the draft feedback
strip, the generation error messages and the help centre — and not "AI". The one place that
says what the Wizard is SHALL be the provider disclosure on the create page ("The Wizard is an
AI agent: …"), which stays where the brief is entered.
When a provider is configured, the wizard card SHALL be the first card in document and visual
order, visually emphasised and badged "Best to start"; when none is configured, *Start from
scratch* SHALL be shown first and the disabled wizard card after it.
*Use your AI assistant* SHALL be the last card and a link to `/editor/surveys/start/agent/`
(change `agent-onboarding`), labelled "Your assistant", badged "New", naming Claude and ChatGPT
in its text, and SHALL NOT say "MCP" or "token"; it carries no *Coming soon* ribbon, no
disabled styling and no `aria-disabled`. The page SHALL render as a full page on every viewport. A
`welcome=1` query parameter SHALL show a "Skip to dashboard" link carrying `?dashboard=1`.
The endpoint SHALL accept only GET. Viewers SHALL receive the same response as for any
editor-only page.

#### Scenario: Editor sees three cards
- **WHEN** an editor-or-higher creator opens `/editor/surveys/start/`
- **THEN** the page shows the three cards, with *Start from scratch* as the submit button of a POST form to the blank-creation endpoint, *Draft with AI* as a link to `/editor/surveys/new/?from=start`, and *Use your AI assistant* as a link to `/editor/surveys/start/agent/`

#### Scenario: The agent card is live
- **WHEN** the start page renders
- **THEN** the agent card has no `aria-disabled`, no "Coming soon" text, carries a "New" badge, mentions Claude and ChatGPT, and does not contain the words "MCP" or "token"

#### Scenario: The wizard is the first card and best to start
- **WHEN** the start page renders on a server with a provider
- **THEN** the *Survey wizard* card precedes *Start from scratch* in the markup, carries the primary style and a "Best to start" badge, and its label does not read "With AI"

#### Scenario: One click from scratch
- **WHEN** a creator clicks anywhere on the *Start from scratch* card
- **THEN** the blank-creation form is submitted (after the browser-position step) and the editor of the new survey opens; no other control has to be clicked

#### Scenario: One click to the AI brief
- **WHEN** a creator clicks anywhere on the *Draft with AI* card on a server with a provider
- **THEN** the browser navigates to `/editor/surveys/new/?from=start`

#### Scenario: One click to the agent page
- **WHEN** a creator clicks anywhere on the *Use your AI assistant* card
- **THEN** the browser navigates to `/editor/surveys/start/agent/`

#### Scenario: No detail block, no remember option
- **WHEN** the start page renders
- **THEN** it contains no "Always start this way" control, no selected-card state and no block of extra text revealed by clicking a card

#### Scenario: No LLM provider
- **WHEN** the start page renders on a server where no provider is configured
- **THEN** the *Draft with AI* card is disabled, is not a link, carries no "Best to start" badge, is shown after *Start from scratch*, and says it is not available on this server, and *Start from scratch* still works

#### Scenario: Welcome escape
- **WHEN** the page is opened with `?welcome=1`
- **THEN** a "Skip to dashboard" link to `/editor/?dashboard=1` is shown

#### Scenario: POST refused
- **WHEN** the start page URL receives a POST
- **THEN** the response is 405 and no preference changes

#### Scenario: Viewer denied
- **WHEN** a viewer-role creator opens `/editor/surveys/start/`
- **THEN** the response is the standard editor-permission refusal and no card is rendered
