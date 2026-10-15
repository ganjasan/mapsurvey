# survey-start-chooser Specification

## Purpose
The page where a creator chooses how to begin a survey — the Wizard (AI draft), an empty survey, or (soon) their own AI agent — with one click, and the remembered default that lets "+ New Survey" skip it.
## Requirements
### Requirement: Start page with three ways to begin
The system SHALL serve `GET /editor/surveys/start/` to signed-in creators whose role in the
active organization is `editor` or above, rendering three cards: *Start from scratch*,
*Draft with AI* and *Connect your AI agent*. A single click (or Enter/Space on the focused
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
*Connect your AI agent* SHALL be inert until the MCP server ships: not a link, not focusable
as a control, marked *Coming soon* and visibly disabled; the agent page is reached from the
account and help menus instead. The page SHALL render as a full page on every viewport. A
`welcome=1` query parameter SHALL show a "Skip to dashboard" link carrying `?dashboard=1`.
The endpoint SHALL accept only GET. Viewers SHALL receive the same response as for any
editor-only page.

#### Scenario: Editor sees three cards
- **WHEN** an editor-or-higher creator opens `/editor/surveys/start/`
- **THEN** the page shows the three cards, with *Start from scratch* as the submit button of a POST form to the blank-creation endpoint, *Draft with AI* as a link to `/editor/surveys/new/?from=start`, and *Connect your AI agent* carrying no link and `aria-disabled`

#### Scenario: The wizard is the first card and best to start
- **WHEN** the start page renders on a server with a provider
- **THEN** the *Survey wizard* card precedes *Start from scratch* in the markup, carries the primary style and a "Best to start" badge, and its label does not read "With AI"

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
- **THEN** the header names *Survey wizard* as the default and links to `/editor/account/`, and offers no "Clear" button

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

