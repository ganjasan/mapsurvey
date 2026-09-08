## Context

The create page (`survey/templates/editor/survey_create.html`) has a Leaflet picker whose
centre is live-synced into hidden `map_lat`/`map_lng`/`map_zoom`. Both create paths read
those fields; the AI path passes them through `header_overrides_from_form()` into the
serialization envelope. The picker opens on Berlin (52.52, 13.405), then jumps to the
browser geolocation if the creator allows it. The mobile wizard (`< 1024px`) additionally
runs `prefillPlaceFromGoal()` when it shows the map step: capitalized word groups from the
goal field, one Photon lookup each, first hit wins, guarded by `_userMovedMap`. Desktop
never calls it because desktop has no map step.

The generation pipeline (`survey/ai/generation.py`) is: build prompt → provider call →
`validate_blob()` → retry once → `materialize_draft(blob, header_overrides, ...)` inside a
transaction. The response schema is strict (`additionalProperties: False`, every property
required), so a new field is both requested and guaranteed present.

Constraints: no new kill switches (owner rule); tests run without network; the draft must
not fail because of the map; `AIGenerationEvent.brief` stays a record of what the creator
wrote, not of what we derived.

## Goals / Non-Goals

**Goals:**
- A brief that names a place, in any language and in any brief field, yields a survey that
  opens on that place — on desktop and mobile alike — unless the creator framed the map.
- Creators learn on the page that the brief may be written in any language.
- Zero new failure modes for generation: geocoding is best-effort and bounded in time.

**Non-Goals:**
- Section-level map positions (the section inherits the survey position as today).
- Place search on the settings/section pickers — separate change
  `editor-map-picker-search`.
- Replacing Photon or adding a geocoding cache/quota layer.
- Inferring a place for the "Create empty" path (no model call there; the client prefill
  is the only help it gets, as before).

## Decisions

**D1. The model extracts the place; the server geocodes it.**
`survey_draft_schema()` gains `"location": {"type": "string"}` at the top level, required,
with a prompt rule: the place the survey is about as a geocodable name in the form
"<locality>, <region>, <country>" using the spelling most likely to resolve (local or
English), or `""` when the brief names no place. Alternatives: (a) a second, cheaper LLM
call only when heuristics fail — adds a round trip and a code path for a field that costs
a few output tokens inside the call we already make; (b) improve the regex — cannot know
that "Ülemiste City" is a place or that "Tallinnas" is Tallinn, and every language needs
its own endings. Having the model return a name, not coordinates, keeps hallucinated
coordinates out: a name that does not geocode is simply dropped.

**D2. `location` never fails validation.**
`validate_blob()` accepts a missing, non-string or over-long (`> 120` chars) `location` by
treating it as empty; it is not an error and never triggers the retry prompt. A draft
with good questions and a bad place is a good draft. The prompt still asks for the field
so the strict schema is satisfied.

**D3. Geocoding lives in `survey/ai/geocode.py`, one function, bounded.**
`geocode_place(name) -> (lat, lng, zoom) | None` calls Photon
(`https://photon.komoot.io/api/?limit=1&q=…`, `requests`, 4 s timeout, a descriptive
`User-Agent`). Zoom follows the client heuristic so both paths agree: `country` → 6,
`state`/`county` → 9, everything else → 12. Any exception, non-200, empty feature list or
malformed geometry returns `None` and is logged at info level. Photon is chosen over
Mapbox because it is what the map search and the wizard prefill already use, needs no key,
and has no billing exposure from a worker retrying.

**D4. Precedence: creator-framed map > brief location > form default.**
The create form gains hidden `map_touched` (`"1"` once the creator drags, wheel/pinch/
double-click zooms, uses the zoom control, picks a search result or presses "My
location"; the browser-geolocation jump and the client prefill do NOT set it — neither is
the creator's choice). The view passes `map_locked=bool(map_touched)` alongside
`header_overrides` to the task. In `run_generation`, after validation succeeds and before
`materialize_draft`, when `not map_locked and blob.get("location")`, a successful geocode
replaces `start_map_position` and `start_map_zoom` in `header_overrides`. Everything else
is unchanged, so the rollback story is "the form position wins", which is today's behavior.
Alternative considered: comparing the posted lat/lng with the default constants — breaks
as soon as geolocation moved the map, which is exactly the Estonian case (creator in
Tallinn, map on Tallinn by geolocation, brief about Ülemiste — fine; but a creator in
Berlin briefing about Tallinn would lose).

**D5. The geocode call happens outside the materialization transaction.**
It runs before `transaction.atomic()` so a slow Photon response never holds a database
transaction open. It adds at most 4 s to a generation that already takes 20–60 s.

**D6. Client prefill stays, widened, as the visible hint.**
`prefillPlaceFromGoal()` becomes `prefillPlaceFromBrief()`: candidates come from goal +
audience + map target; it runs on desktop on a debounced `input` (800 ms) of any brief
field and once more on Generate/Draft click; the wizard call site is unchanged. It still
only moves an untouched map and still writes the resolved name into the search box so the
jump is explained. Its value on desktop is that the creator sees the map move before
they submit and can correct it; the server path then resolves the same place (or a
better one) for the saved survey. Duplicated effort is acceptable: the request is tiny
and the two paths cover different moments.

**D7. Hint copy.**
Under the goal textarea: "Write in any language — the draft is generated in the survey
languages you pick." Plain template string like the rest of the page; the in-flight
`creator-ui-localization` change owns wrapping creator UI in `{% trans %}` and will pick
this string up with the rest of the page.

## Risks / Trade-offs

- [Photon down or rate-limiting the worker IP] → 4 s timeout, `None`, form position used;
  logged. No retry: one lookup per generation.
- [Model invents a place when the brief has none] → prompt asks for `""` explicitly and the
  schema field is documented as "empty when unknown"; a wrong place is one drag away in
  settings, and the event log (`generated_blob.location`) shows how often it happens.
- [Ambiguous names ("Springfield")] → Photon's first hit, same as the map search gives
  today; the creator's correction path is the settings picker.
- [Creator framed the map but `map_touched` missed the gesture] → server geocode
  overwrites their framing. Mitigated by marking every user-originated Leaflet interaction
  listed in D4 and by the desktop prefill showing the map move before submit. The reverse
  (touched set spuriously) only means no server geocode, i.e. today's behavior.
- [Tests hitting the network] → `geocode_place` is patched in every generation test; one
  unit test covers the parsing with a stubbed `requests.get`.

## Migration Plan

No schema or data migration. Deploy is a normal merge. Rollback: revert the PR; surveys
created in between keep their (correct) positions.

## Open Questions

None blocking. Whether the brief hint should also mention that placeholders are examples
only can be judged on the rendered page during implementation.
