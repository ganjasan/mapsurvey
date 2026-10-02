## Why

A creator who describes their project on the create page and clicks Generate on a desktop
gets a survey whose map opens on the default Berlin framing unless they dragged the map
themselves. The brief usually names the place ("Residents of Ülemiste City", "parks in
Bishkek") but only the mobile wizard tries to read it, only from the goal field, only with a
capital-letter heuristic that knows Russian case endings and nothing else. Prod event #44
(2026-09-08) is the concrete case: an Estonian-language survey briefed in English, the place
in the audience field, the map left where it was. The same brief form also silently tells
creators to write English — every placeholder is English — although the model reads any
language.

## What Changes

- The generation response schema gains a `location` string: the geographic place the brief is
  about, as a geocodable name, or empty when the brief names none. The model reads the whole
  brief in any language, so it replaces the client-side regex as the primary source.
- The generation task geocodes that name server-side (Photon, the same geocoder the map search
  uses) and writes the result as the survey's start position and zoom — but only when the
  creator did not frame the map themselves. A new hidden `map_touched` field on the create
  form carries that fact; today the hidden lat/lng are always filled with the map centre, so
  the server cannot tell a chosen position from the untouched default.
- Geocoding failures, empty locations and unresolvable names never fail or delay a draft
  beyond a short timeout; the form position is the fallback, exactly as today.
- The existing client-side place prefill runs on desktop too (debounced on brief input and
  before Generate), reads all three brief text fields instead of only the goal, and keeps its
  "never move a map the creator already moved" guard. It remains a fast hint; the server path
  is the reliable one.
- A hint under the goal field says the brief can be written in any language and that the
  draft is produced in the survey languages chosen on the form.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `ai-survey-generation`: the brief panel gains the any-language hint; the response schema
  gains `location` and the validator tolerates its absence; materialization takes the start
  position from the geocoded location when the map was untouched; the create-map place
  prefill is specified for both viewports and all brief fields.

## Impact

- `survey/ai/schema.py`, `survey/ai/prompts.py`, `survey/ai/validator.py` — new `location`
  field, prompt rule, tolerant validation.
- `survey/ai/generation.py`, `survey/ai/tasks.py`, `survey/ai/materialize.py`,
  `survey/editor_views.py` — `map_touched` travels from the POST to the task; geocode step
  before materialization.
- New `survey/ai/geocode.py` — one Photon lookup with timeout, returns position + zoom or
  `None`. Outbound HTTP from the Celery worker to `photon.komoot.io` (already a browser-side
  dependency; new from the server).
- `survey/editor_forms.py`, `survey/templates/editor/survey_create.html` — hint text, hidden
  `map_touched`, prefill on desktop and over all brief fields.
- `survey/tests.py` — geocode mocked; no live network in tests.
- No model or migration changes. `generated_blob` on `AIGenerationEvent` keeps the returned
  `location`, so how often the model finds a place can be read from the event log.
