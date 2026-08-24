## MODIFIED Requirements

### Requirement: Survey creation
The system SHALL provide a form at `/editor/surveys/new/` that allows authenticated users to create a new survey. The form SHALL include fields for survey name, organization, available languages, visibility, redirect URL, and thanks HTML, and — when an LLM provider is configured — an optional AI brief panel (goal, audience, map target, use-case) with a "Generate draft" action alongside the manual empty-survey action. A manual submission (`action=empty`, `action=empty_skip`, or any POST without an explicit action) SHALL create a SurveyHeader (with auto-generated UUID) and one default section (marked `is_head=True`), then redirect to the survey editor using the UUID — byte-identical to the pre-AI behavior. A "Generate draft" submission SHALL follow the asynchronous generation flow defined in the `ai-survey-generation` capability and, on success, redirect to the populated survey's editor.

When the AI brief panel is rendered, the manual action SHALL be presented as **"Skip and Create Empty Survey"** and SHALL post `action=empty_skip`. That action is a skip of the whole wizard, not only of the AI draft: it SHALL ignore the map picker, so the created survey receives the model's default start position, zoom and base map even though the picker posted values, and the creator sets the map afterwards in Survey settings. `action=empty` — the button rendered when no AI panel is present, plus legacy and action-less POSTs — SHALL keep applying the posted map position, zoom and base map. The "Generate draft" path is unaffected and continues to frame the generated draft on the picked map.

Because the manual action discards a brief the creator may have just typed, the page SHALL confirm before submitting it: when any of `goal`, `audience` or `map_target` contains non-whitespace text, clicking "Skip and Create Empty Survey" SHALL raise a confirmation dialog naming what is lost, and SHALL submit only if the creator confirms. The preselected use-case chip SHALL NOT count as a filled brief.

#### Scenario: Create a new survey
- **WHEN** an authenticated user submits the survey creation form with name "my_test_survey" using the manual action
- **THEN** a SurveyHeader with that name and auto-generated UUID is created, a default section with `is_head=True` is created, and the user is redirected to `/editor/surveys/<uuid>/`

#### Scenario: Duplicate survey name allowed
- **WHEN** a user submits the creation form with a name that already exists for another user's survey
- **THEN** the survey SHALL be created successfully (names are not globally unique)

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated user accesses `/editor/surveys/new/`
- **THEN** the system redirects to the login page

#### Scenario: Legacy POST without action falls back to manual creation
- **WHEN** a POST reaches the view without an `action` parameter
- **THEN** the manual creation path runs exactly as before the AI panel existed, including applying any posted map position

#### Scenario: Generate draft action
- **WHEN** an authenticated editor submits the form with the "Generate draft" action, a filled brief, and a configured provider
- **THEN** generation is enqueued and the page enters the polling state defined in `ai-survey-generation`, ending on success at the populated survey's editor

#### Scenario: Skip discards the map framing
- **WHEN** an authenticated editor submits `action=empty_skip` with `map_lat`, `map_lng`, `map_zoom` and `default_basemap` all present in the POST
- **THEN** the created survey stores the model defaults for start position, zoom and base map, and the editor opens on the new survey

#### Scenario: The non-skip manual action still frames the map
- **WHEN** an authenticated editor submits `action=empty` with a posted map position, zoom and base map
- **THEN** the created survey stores exactly those values, unchanged from before this requirement

#### Scenario: Skipping with a filled brief asks first
- **WHEN** the AI panel is rendered, the creator has typed into `goal` (or `audience`, or `map_target`), and clicks "Skip and Create Empty Survey"
- **THEN** a confirmation dialog appears stating the brief will not be used; cancelling leaves the page and the typed brief untouched, and confirming submits the form

#### Scenario: Skipping with an untouched brief does not ask
- **WHEN** the AI panel is rendered, `goal`, `audience` and `map_target` are all blank (the use-case chip carrying only its preselected default), and the creator clicks "Skip and Create Empty Survey"
- **THEN** the form submits immediately with no confirmation dialog
