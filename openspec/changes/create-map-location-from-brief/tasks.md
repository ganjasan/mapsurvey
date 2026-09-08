## 1. Model contract

- [x] 1.1 Add required top-level `location` string to `survey_draft_schema()` in `survey/ai/schema.py`
- [x] 1.2 Add the location rule to the system prompt in `survey/ai/prompts.py` (geocodable "<locality>, <region>, <country>", any brief field, any language, `""` when none)
- [x] 1.3 Make `validate_blob()` tolerant: missing / non-string / >120-char `location` is normalized to `""`, never an error; unit test both directions

## 2. Server-side geocoding

- [x] 2.1 Create `survey/ai/geocode.py` with `geocode_place(name)` → `(lat, lng, zoom)` or `None`: Photon `limit=1`, 4 s timeout, User-Agent, zoom by place type (country 6, state/county 9, else 12), all failures logged and swallowed
- [x] 2.2 Unit tests with `requests.get` stubbed: hit, empty features, non-200, timeout, malformed geometry
- [x] 2.3 In `run_generation` (`survey/ai/generation.py`), after validation and before `transaction.atomic()`: when `not map_locked` and `location` non-empty, geocode and overwrite `start_map_position`/`start_map_zoom` in `header_overrides`
- [x] 2.4 Thread `map_locked` from `_start_survey_generation` (`request.POST.get('map_touched') == '1'`) through `generate_survey_draft_task` to `run_generation`
- [x] 2.5 Generation tests with `geocode_place` patched: touched map keeps form position and makes no lookup; untouched map takes geocoded point and zoom; empty/unresolvable location falls back to form values with outcome `success`

## 3. Create page

- [x] 3.1 Add hidden `map_touched` input to the create form; set to `1` on dragstart, wheel/dblclick/pinch zoom, zoom-control click, search-result select, and "My location"; leave unset on geolocation jump and prefill moves
- [x] 3.2 Rename `prefillPlaceFromGoal` → `prefillPlaceFromBrief`; build candidates from goal + audience + map target; keep the `_userMovedMap` guard and the search-box echo
- [x] 3.3 Run the prefill on desktop: debounced 800 ms `input` on the three brief fields and once on Generate/Draft click; wizard map-step call site unchanged
- [x] 3.4 Any-language hint under the goal textarea — already shipped upstream by `creator-ui-localization` slice 1 (`.ai-lang-hint`), nothing to add
- [x] 3.5 Template test: hint rendered with the brief panel; `map_touched` input present

## 4. Verification

- [x] 4.1 `./run_tests.sh survey -v2` green, no network access during tests
- [x] 4.2 Browser check on desktop and at <1024px: brief naming a place moves the map; dragging first blocks the move; posted form carries `map_touched` correctly
- [ ] 4.3 One real generation on a PR preview with the Estonian brief from event #44; survey opens on Ülemiste
