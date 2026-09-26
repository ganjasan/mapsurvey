## 1. Model and helpers

- [x] 1.1 Add `basemap_mode`, `image_basemap` (public tier, `basemap_images/<uuid4>.webp`), `image_basemap_width`, `image_basemap_height`, `image_basemap_state`, `image_basemap_error`, `image_basemap_pending` to `SurveyHeader`; additive migration (check `origin/master` for the latest migration number first) — `0087_survey_image_basemap`
- [x] 1.2 `SurveyHeader.uses_image_basemap` — the single predicate (`mode == 'image'` and image set)
- [x] 1.3 `survey/image_basemap.py`: `bounds_for(width, height)` (1° long side, centred on 0,0), `config_for(survey)` (url, bounds, width, height or None), `point_inside` + `section_map_view`, `delete_if_unreferenced(name)`, `copy_fields(src)`
- [x] 1.4 Limits `IMAGE_BASEMAP_MAX_UPLOAD_BYTES` (20 MB), `IMAGE_BASEMAP_MAX_PIXELS` (64 MP), `IMAGE_BASEMAP_MAX_SIDE` (8192) — defaults in `image_basemap.py`, overridable from settings
- [x] 1.5 Tests: bounds for landscape/portrait, predicate, start-view inside/outside, delete only when no header references the name

## 2. Upload pipeline

- [x] 2.1 `image_basemap.process_file(fileobj) -> (webp_bytes, w, h)` — pixel cap from the header before decoding, `verify()`, EXIF transpose, downscale, WebP q85; raises `ImageRejected` with a translated reason
- [x] 2.2 Celery task `process_image_basemap(survey_id, raw_key, language)` — supersede check via `image_basemap_pending`, save to public tier, write size, clear state, delete old file via `delete_if_unreferenced`, delete raw in `finally`
- [x] 2.3 Editor endpoint `POST /editor/surveys/<uuid>/basemap-image/upload/` — owner role (like every survey setting), content-type + size check without decoding, raw to private tier `basemap_uploads/<uuid4>`, set `processing`, enqueue; aspect-ratio confirm step (D6) using a lazy `Image.open` header read
- [x] 2.4 Endpoints to switch `basemap_mode` (with the tiles→image warning when the family has geo answers) and to clear the image
- [x] 2.5 Tests (eager task): happy path PNG→WebP, oversized refused, non-image `failed`, decompression bomb refused without decode, downscale, supersede, raw deleted on success and failure, viewer refused, confirm only for different aspect ratio with answers

## 3. Editor UI

- [x] 3.1 Settings card image block (`editor/partials/image_basemap_card.html` + delegated script in the settings panel): upload, processing indicator polling every 2 s, preview, error, mode switch, clear; tile checkboxes/default basemap/use geolocation hidden (not removed) in `image` mode
- [x] 3.2 Section map picker: hide basemap override and geolocation (kept in the DOM for the autosave payload) and search in `image` mode; map shows the image; inherit = whole picture
- [x] 3.3 i18n: RU strings for every new message; verified through `gettext` at runtime (123 → 150 compiled entries, none lost)
- [x] 3.4 Browser check on the dev server (real Celery worker): upload 3000×2000 PNG → WebP, switch, switch back, tile settings and image kept. Found and fixed: opening the settings panel on an image survey auto-saved a 0,0 position (setMaxBounds animated pan landed after the picker attached) — `ImageBasemap.apply` now frames an off-picture view without animation first

## 4. Rendering

- [x] 4.1 `survey/assets/js/image_basemap.js` — `ImageBasemap.apply(map, cfg)`: overlay, padded `maxBounds` + viscosity, min/max zoom, background, returns bounds
- [x] 4.2 Config reaches every map through one filter, `survey|image_basemap_json` (replaces the planned `json_script` partial — see design D4)
- [x] 4.3 `partials/basemap_layers.html` branches: no tiles, no base entries, control kept for overlays
- [x] 4.4 Respondent page (and the editor's live preview): skip `MapPlaceSearch`, the locate button and geolocation, ignore `override_basemap`, fit image unless start view is inside
- [x] 4.5 Hand-built surfaces: Overview thumbnail, per-response map modal, settings-panel map picker and style preview, legacy settings page, public results blocks
- [x] 4.6 Template guard test: every template with `L.tileLayer(` also reads `image_basemap_json` (`survey_create.html` exempt — no survey yet)
- [x] 4.7 Tests: respondent page of an image survey has the config and no real-world settings; public results carry the picture; tiles survey output unchanged
- [x] 4.8 Browser check: settings picker, respondent map (desktop + 390 px), point placed and stored on the picture, Responses Overview thumbnail and Map pane; no JS errors. Found and fixed: Map pane zoomed to a single mark (blurred pixels) and still offered real-world place search — both now keyed on the per-map `map._imageBasemapBounds`. Not driven in the browser: section map picker modal, layer object editor, per-response modal, public results page (covered by render tests only)

## 4b. Settings card UX (owner review on PR #200, design D9)

- [x] 4b.1 Radios always enabled; "Map tiles" shows tile choices only, "My own image" shows the image block (client-side toggle when no picture is stored yet)
- [x] 4b.2 One app-styled "Choose image…" control (label over a hidden file input); upload starts on selection; "Replace image" / "Remove image" once a picture exists
- [x] 4b.3 A successful upload sets `basemap_mode = 'image'` in the task; `store_processed` stays mode-neutral for ZIP import
- [x] 4b.4 First upload on a tiles survey with geo answers asks the mode-switch confirmation; the chosen file survives the round trip
- [x] 4b.5 "Map tiles" while processing abandons the pending upload
- [x] 4b.6 Tests for every new scenario (5 new, 2 updated); browser check on the dev server with a real Celery worker: tiles → My own image → pick file → confirm → processing → switched; back to tiles and to image again

## 5. Versions and trash

- [x] 5.1 `clone_survey_for_draft()` and `publish_draft()` copy the image fields; the archived version keeps the old picture; a discarded draft releases only its own picture
- [x] 5.2 ~~Whole-survey duplication~~ — the product has none (only question/section duplication); ZIP export/import covers copying
- [x] 5.3 `purge_survey()` deletes each distinct image name once, unless a header outside the family still names it
- [x] 5.4 Tests: draft replace leaves published image, publish switches, archived keeps old, discard, purge

## 6. Export / import

- [x] 6.1 `export_survey_to_zip`: `basemap_mode` + `image_basemap` in `survey.json`, file under `basemap/`
- [x] 6.2 `import_survey_from_zip`: run the file through `process_file`; missing/invalid/oversized → `tiles` + report line; old archives unchanged
- [x] 6.3 `download_data`: `mapsurvey_image_basemap` member in every GeoJSON + image in ZIP (per version prefix), for image surveys only
- [x] 6.4 Tests for every scenario in `specs/survey-serialization` and the data-export requirement

## 7. Release checks

- [x] 7.1 Full suite after the change: 2161 tests OK (1 skipped); the 43 image-basemap + template tests re-run green after the browser-check fixes
- [ ] 7.2 PR preview: upload through S3, confirm `basemap_images/` public and `basemap_uploads/` denied anonymously
- [ ] 7.3 PR preview: `loadtest/lecture-burst.js` against an image survey with a shared-map question
- [ ] 7.4 Real phones (mid-range Android, iPhone) with an 8192-px image; lower `IMAGE_BASEMAP_MAX_SIDE` if either stalls
- [x] 7.6 Preview worker read a different S3 prefix than its web service (design D8): `MEDIA_NAMESPACE_SERVICE` on the worker in `render.yaml`, handled in `namespace_from_env`, tests for web/worker parity, slug names, production and the Blueprint
- [x] 7.7 A task whose raw file is missing marks the upload `failed` ("upload it again") instead of leaving "Processing" forever; the Upload button is never disabled while processing (a new upload supersedes)
- [x] 7.5 Update `CLAUDE.md` Key Patterns with the image basemap rules (one predicate, one renderer, Null Island bounds, shared file names)
