## MODIFIED Requirements

### Requirement: AI brief panel on the create page
The Create New Survey page SHALL render an AI brief panel — a goal textarea, a "Who will
answer?" input, a "What should they mark on the map?" input, a use-case chip selector
(urban planning / citizen science / school routes / event mapping / other), a privacy
notice, and a "Generate draft" submit — only when an LLM provider is configured
(`AI_PROVIDER` resolvable and its credentials set). The goal textarea SHALL carry a visible
hint that the brief may be written in any language and that the draft is generated in the
survey languages chosen on the form. When the `CREATE_STEER_AI` flag is
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

#### Scenario: Any-language hint is shown with the goal field
- **WHEN** the AI brief panel renders
- **THEN** a hint adjacent to the goal textarea states that the brief can be written in any language and that the draft is generated in the survey languages picked on the form

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

### Requirement: Validation gate before persistence
Model output SHALL pass `validate_blob()` before any database write: 2–4 sections; at
least one answerable (non-`html`) question; every localized text dict has exactly the
requested language key set; `input_type` within the serialization whitelist;
choice/multichoice/range/rating questions have non-empty choices with unique integer
codes (strictly ascending for range/rating); at most one top-level geo question with 0–2
non-geo sub-questions. The top-level `location` field SHALL NOT participate in validation:
a missing, non-string, or over-long (more than 120 characters) `location` SHALL be treated
as empty and SHALL never cause a retry or rejection. On validation failure the task SHALL
retry the model exactly once with the error list; a second failure SHALL record
`invalid_draft` and write nothing.

#### Scenario: Invalid output retried once then rejected
- **WHEN** the model returns output failing validation twice in a row
- **THEN** exactly two provider calls are made, no `SurveyHeader` row is created, and the event outcome is `invalid_draft`

#### Scenario: Missing translation is a validation error
- **WHEN** the requested languages are `["en", "de"]` and any question name dict lacks the `de` key
- **THEN** validation fails (silent base-language fallback is not permitted for generated drafts)

#### Scenario: Bad location is not a validation error
- **WHEN** an otherwise valid draft has `location` missing, set to a non-string, or longer than 120 characters
- **THEN** validation passes, one provider call is made, and the draft is materialized as if `location` were empty

### Requirement: Materialization through the serialization import path
Validated drafts SHALL be materialized by building the `{"version": "1.0", "survey":
{...}}` envelope and passing it through `serialization.import_survey_from_zip` (in-memory
ZIP), with the owner `SurveyCollaborator` created in the same outer transaction. Header
fields (name, languages, default basemap) SHALL come from the form, never from the model
output. The start map position and zoom SHALL come from the form when the creator framed
the map (`map_touched` posted as `1`); otherwise they SHALL come from the geocoded model
`location` when it is non-empty and resolves, and from the form when it is empty or does
not resolve.

#### Scenario: Atomic failure
- **WHEN** materialization raises after partial object creation
- **THEN** the transaction rolls back completely — no survey, sections, questions, or collaborator rows remain — and the event outcome records the failure

#### Scenario: Creator-framed map wins over the brief
- **WHEN** the POST carries `map_touched=1` with a position and the model returns a resolvable `location`
- **THEN** the survey's start position and zoom equal the posted values and no geocode request is made

#### Scenario: Untouched map takes the brief's place
- **WHEN** the POST carries no `map_touched` and the model returns a `location` that geocodes
- **THEN** the survey's start position is the geocoded point and its zoom follows the place type (country 6, state or county 9, otherwise 12)

#### Scenario: Geocoding falls back to the form
- **WHEN** the map was untouched and the `location` is empty, unresolvable, or the geocoder errors or times out
- **THEN** the survey's start position and zoom equal the posted form values and the generation outcome is `success`

## ADDED Requirements

### Requirement: Survey location inferred from the brief
The generation response schema SHALL include a required top-level `location` string. The
system prompt SHALL instruct the model to return the geographic place the survey is
about — read from any brief field, in any language — as a geocodable name in the form
"<locality>, <region>, <country>", and to return an empty string when the brief names no
place. The returned value SHALL be kept in the event's `generated_blob`. The system SHALL
resolve a non-empty location with at most one geocoder lookup, bounded by a timeout of at
most 4 seconds, performed outside the materialization transaction; the lookup SHALL never
raise into the generation task.

#### Scenario: Place named in a non-goal field, in another language
- **WHEN** the goal is "Where people feel thermally comfortable." and the audience is "Residents of Ülemiste City, all ages" with survey language `et`
- **THEN** the returned `location` names Ülemiste in Tallinn, Estonia, and the resulting untouched-map survey opens there

#### Scenario: Brief names no place
- **WHEN** the brief describes a project without any place
- **THEN** `location` is an empty string, no geocode request is made, and the form position is used

#### Scenario: Geocoder is slow
- **WHEN** the geocoder does not answer within the timeout
- **THEN** the lookup returns no position, the draft is materialized with the form position, and no database transaction was held open during the wait

### Requirement: Place prefill from the brief on the create map
The create page SHALL attempt to aim the map picker at a place named in the brief before
submission, on every viewport. Candidates SHALL be taken from the goal, audience, and
map-target fields. The attempt SHALL run when the mobile wizard shows the map step, and on
desktop after a pause in typing in any brief field and once more when the draft action is
triggered. The map SHALL only be moved while the creator has not framed it themselves
(dragged, zoomed by wheel, pinch, double-click or zoom control, chosen a search result, or
used "My location"); a prefill move or a browser-geolocation move SHALL NOT count as the
creator framing the map. A successful prefill SHALL show the resolved place name in the
map search box. The form SHALL post a hidden `map_touched` field equal to `1` if and only
if the creator framed the map.

#### Scenario: Desktop brief names a place
- **WHEN** a desktop creator types "Residents of Ülemiste City" into the audience field and pauses
- **THEN** the map moves to Ülemiste, the search box shows the resolved name, and `map_touched` stays unset

#### Scenario: Creator framed the map first
- **WHEN** the creator dragged the map and then types a place into the goal
- **THEN** the map does not move and `map_touched` is posted as `1`

#### Scenario: Geolocation jump does not lock the map
- **WHEN** the browser geolocation moved the map on page load and the creator then types a place into the brief
- **THEN** the prefill still moves the map to the named place and `map_touched` stays unset
