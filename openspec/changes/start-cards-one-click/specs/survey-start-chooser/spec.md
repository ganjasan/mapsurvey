## MODIFIED Requirements

### Requirement: Start page with three ways to begin
The system SHALL serve `GET /editor/surveys/start/` to signed-in creators whose role in the
active organization is `editor` or above, rendering three cards: *Start from scratch*,
*Draft with AI* and *Connect your AI agent*. A single click (or Enter/Space on the focused
card) on an actionable card SHALL perform that card's action, with no intermediate selection
step and no detail block revealed elsewhere on the page. *Start from scratch* SHALL be the
submit button of a POST form to the blank-creation endpoint, so the whole card submits it.
*Draft with AI* SHALL be a link to `/editor/surveys/new/?from=start`, and SHALL render
disabled, without a link, with an explanation when no LLM provider is configured. When a
provider is configured, *Draft with AI* SHALL be the first card in document and visual order,
visually emphasised and labelled "Recommended"; when none is configured, *Start from scratch*
SHALL be shown first and the disabled AI card after it.
*Connect your AI agent* SHALL be inert until the MCP server ships: not a link, not focusable
as a control, marked *Coming soon* and visibly disabled; the agent page is reached from the
account and help menus instead. The page SHALL render as a full page on every viewport. A
`welcome=1` query parameter SHALL show a "Skip to dashboard" link carrying `?dashboard=1`.
The endpoint SHALL accept only GET. Viewers SHALL receive the same response as for any
editor-only page.

#### Scenario: Editor sees three cards
- **WHEN** an editor-or-higher creator opens `/editor/surveys/start/`
- **THEN** the page shows the three cards, with *Start from scratch* as the submit button of a POST form to the blank-creation endpoint, *Draft with AI* as a link to `/editor/surveys/new/?from=start`, and *Connect your AI agent* carrying no link and `aria-disabled`

#### Scenario: AI is the recommended first card
- **WHEN** the start page renders on a server with a provider
- **THEN** the *Draft with AI* card precedes *Start from scratch* in the markup, carries the primary style and a "Recommended" label

#### Scenario: One click from scratch
- **WHEN** a creator clicks anywhere on the *Start from scratch* card
- **THEN** the blank-creation form is submitted (after the browser-position step) and the editor of the new survey opens; no other control has to be clicked

#### Scenario: One click to the AI brief
- **WHEN** a creator clicks anywhere on the *Draft with AI* card on a server with a provider
- **THEN** the browser navigates to `/editor/surveys/new/?from=start`

#### Scenario: No detail block, no remember option
- **WHEN** the start page renders
- **THEN** it contains no "Always start this way" control, no selected-card state and no block of extra text revealed by clicking a card

#### Scenario: No LLM provider
- **WHEN** the start page renders on a server where no provider is configured
- **THEN** the *Draft with AI* card is disabled, is not a link, carries no "Recommended" label, is shown after *Start from scratch*, and says it is not available on this server, and *Start from scratch* still works

#### Scenario: Welcome escape
- **WHEN** the page is opened with `?welcome=1`
- **THEN** a "Skip to dashboard" link to `/editor/?dashboard=1` is shown

#### Scenario: POST refused
- **WHEN** the start page URL receives a POST
- **THEN** the response is 405 and no preference changes

#### Scenario: Viewer denied
- **WHEN** a viewer-role creator opens `/editor/surveys/start/`
- **THEN** the response is the standard editor-permission refusal and no card is rendered

### Requirement: Remembered start default
The system SHALL store a creator's preferred way to start in
`CreatorPreferences.survey_start_default` with values `''` (ask), `blank` and `ai`. The value
SHALL be set only from the Preferences page (`creator-preferences-page`); neither the start
page nor the blank-creation endpoint SHALL write it, and a `remember` field posted to the
blank-creation endpoint SHALL be ignored. When a default is set, the start page SHALL show it
with a link to the Preferences page. The dashboard's "+ New Survey" SHALL route by the
default: `''` → the start page; `ai` → the create page; `blank` → a POST form to the
blank-creation endpoint. The dashboard's ⋯ menu SHALL offer "Start another way…" linking to
the start page, and the create page opened with `from=start` SHALL show a link back to it in
place of "Skip and start from scratch".

#### Scenario: Start page shows the default
- **WHEN** a creator with `survey_start_default='ai'` opens the start page
- **THEN** the header names *Draft with AI* as the default and links to `/editor/account/`, and offers no "Clear" button

#### Scenario: Creating from scratch does not set a default
- **WHEN** a creator with no default posts `remember=1` to the blank-creation endpoint
- **THEN** a survey is created and `survey_start_default` stays `''`

#### Scenario: Default routes the button
- **WHEN** a creator with `survey_start_default='ai'` opens the dashboard
- **THEN** "+ New Survey" links to `/editor/surveys/new/`, and the ⋯ menu offers "Start another way…"

#### Scenario: Blank default is one click
- **WHEN** a creator with `survey_start_default='blank'` clicks "+ New Survey"
- **THEN** a blank survey is created by POST and the editor opens, without the start page

#### Scenario: Create page from the start page
- **WHEN** the create page is opened with `?from=start`
- **THEN** "Skip and start from scratch" is not rendered and a "Start another way" link to the start page is

#### Scenario: Create page without the parameter
- **WHEN** the create page is opened without `from`
- **THEN** it renders exactly as before this change, including "Skip and start from scratch"
