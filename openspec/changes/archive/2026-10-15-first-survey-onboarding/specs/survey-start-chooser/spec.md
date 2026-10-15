## ADDED Requirements

### Requirement: Start page with three ways to begin
The system SHALL serve `GET /editor/surveys/start/` to signed-in creators whose role in the
active organization is `editor` or above, rendering three cards: *Start from scratch*,
*Draft with AI* and *Connect your AI agent*. *Start from scratch* SHALL be a POST form to
the blank-creation endpoint. *Draft with AI* SHALL link to `/editor/surveys/new/?from=start`,
and SHALL render disabled with an explanation when no LLM provider is configured.
*Connect your AI agent* SHALL be inert until the MCP server ships: not a link, not
selectable, marked *Coming soon* and visibly disabled; the agent page is reached from the
account and help menus instead. The page SHALL render as a full page on every viewport. A
`welcome=1` query parameter SHALL show a "Skip to dashboard" link carrying `?dashboard=1`.
Viewers SHALL receive the same response as for any editor-only page.

#### Scenario: Editor sees three cards
- **WHEN** an editor-or-higher creator opens `/editor/surveys/start/`
- **THEN** the page shows the three cards, with *Start from scratch* as a POST form, *Draft with AI* linking to `/editor/surveys/new/?from=start`, and *Connect your AI agent* carrying no link and `aria-disabled`

#### Scenario: No LLM provider
- **WHEN** the start page renders on a server where no provider is configured
- **THEN** the *Draft with AI* card is disabled and says it is not available on this server, and *Start from scratch* still works

#### Scenario: Welcome escape
- **WHEN** the page is opened with `?welcome=1`
- **THEN** a "Skip to dashboard" link to `/editor/?dashboard=1` is shown

#### Scenario: Viewer denied
- **WHEN** a viewer-role creator opens `/editor/surveys/start/`
- **THEN** the response is the standard editor-permission refusal and no card is rendered

### Requirement: Blank survey in one request
The system SHALL accept `POST /editor/surveys/new/blank/` from an `editor`-or-higher
creator and create a `SurveyHeader` in the active organization named "Untitled survey"
(translated into the creator's interface language), with `available_languages` set to the
creator's interface language when it is a key of `settings.LANGUAGES` and `['en']`
otherwise, a start map position and zoom from the `map-start-position` chain (taking
posted `map_lat`, `map_lng`, `map_zoom` as the browser rung), one default section
(`code='S1'`, `is_head=True`), and the creator as owner collaborator. It SHALL then
redirect to the survey editor. A GET to the endpoint SHALL NOT create anything. The
survey-building steps SHALL be shared with the create page's manual path so the two
cannot diverge.

#### Scenario: One click to the editor
- **WHEN** an editor posts to `/editor/surveys/new/blank/` with no body
- **THEN** a survey named "Untitled survey" with one head section exists in the active organization, the creator is its owner collaborator, its start position is set, and the response redirects to `/editor/surveys/<uuid>/`

#### Scenario: Interface language becomes the survey language
- **WHEN** a creator whose UI language is `de` posts to the endpoint
- **THEN** the survey's `available_languages` is `['de']` and its name is the German translation of "Untitled survey"

#### Scenario: Unsupported interface language
- **WHEN** a creator whose UI language is not in `settings.LANGUAGES` posts to the endpoint
- **THEN** the survey's `available_languages` is `['en']`

#### Scenario: Browser position wins
- **WHEN** the POST carries `map_lat=42.87`, `map_lng=74.59`
- **THEN** the survey's start position is that point and the `survey_created` event has `map_source='browser'`

#### Scenario: GET creates nothing
- **WHEN** the endpoint receives a GET
- **THEN** no survey is created and the response is a method-not-allowed or a redirect to the start page

#### Scenario: Viewer cannot create
- **WHEN** a viewer posts to the endpoint
- **THEN** no survey is created and the response is the editor-permission refusal

### Requirement: Remembered start default
The system SHALL store a creator's preferred way to start in
`CreatorPreferences.survey_start_default` with values `''` (ask), `blank` and `ai`. The
start page's two actionable cards SHALL offer "Always start this way"; submitting a card
with it ticked SHALL write the matching value before proceeding. The start page SHALL
show the current default with a "Clear" action (POST) when one is set. The dashboard's
"+ New Survey" SHALL route by the default: `''` → the start page; `ai` → the create
page; `blank` → a POST form to the blank-creation endpoint. The dashboard's ⋯ menu
SHALL offer "Start another way…" linking to the start page, and the create page opened
with `from=start` SHALL show a link back to it in place of "Skip and start from scratch".

#### Scenario: Default set with the AI card
- **WHEN** a creator ticks "Always start this way" on *Draft with AI* and proceeds
- **THEN** `survey_start_default` is `ai` and the creator lands on the create page

#### Scenario: Default routes the button
- **WHEN** a creator with `survey_start_default='ai'` opens the dashboard
- **THEN** "+ New Survey" links to `/editor/surveys/new/`, and the ⋯ menu offers "Start another way…"

#### Scenario: Blank default is one click
- **WHEN** a creator with `survey_start_default='blank'` clicks "+ New Survey"
- **THEN** a blank survey is created by POST and the editor opens, without the start page

#### Scenario: Default cleared
- **WHEN** a creator with a default posts `action=clear` on the start page
- **THEN** `survey_start_default` is `''` and "+ New Survey" links to the start page again

#### Scenario: Create page from the start page
- **WHEN** the create page is opened with `?from=start`
- **THEN** "Skip and start from scratch" is not rendered and a "Start another way" link to the start page is

#### Scenario: Create page without the parameter
- **WHEN** the create page is opened without `from`
- **THEN** it renders exactly as before this change, including "Skip and start from scratch"
