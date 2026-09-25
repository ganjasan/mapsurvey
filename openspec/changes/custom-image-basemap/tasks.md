## 1. Model and helpers

- [ ] 1.1 Add `basemap_mode`, `image_basemap` (public tier, `basemap_images/<uuid4>.webp`), `image_basemap_width`, `image_basemap_height`, `image_basemap_state`, `image_basemap_error`, `image_basemap_pending` to `SurveyHeader`; additive migration (check `origin/master` for the latest migration number first)
- [ ] 1.2 `SurveyHeader.uses_image_basemap` — the single predicate (`mode == 'image'` and image set)
- [ ] 1.3 `survey/image_basemap.py`: `bounds_for(width, height)` (1° long side, centred on 0,0), `config_for(survey)` (url, bounds, width, height or None), `start_view_inside(survey_or_section)`, `delete_if_unreferenced(name)`
- [ ] 1.4 Settings `IMAGE_BASEMAP_MAX_UPLOAD_BYTES` (20 MB), `IMAGE_BASEMAP_MAX_PIXELS` (64 MP), `IMAGE_BASEMAP_MAX_SIDE` (8192)
- [ ] 1.5 Tests: bounds for landscape/portrait/square, predicate, start-view inside/outside, delete only when no header references the name

## 2. Upload pipeline

- [ ] 2.1 `process_image_basemap_file(fileobj) -> (webp_bytes, w, h)` — MAX_IMAGE_PIXELS guard, `verify()`, EXIF transpose, downscale, WebP q85; raises a typed error with a translated reason
- [ ] 2.2 Celery task `process_image_basemap(survey_id, raw_key)` — supersede check via `image_basemap_pending`, save to public tier, write size, clear state, delete old file via `delete_if_unreferenced`, delete raw in `finally`
- [ ] 2.3 Editor endpoint `POST /editor/surveys/<uuid>/basemap-image/` — editor role, content-type + size check without decoding, stream raw to private tier `basemap_uploads/<uuid4>`, set `processing`, enqueue; aspect-ratio / has-geo-answers confirm step (D6) using a lazy `Image.open` header read
- [ ] 2.4 Endpoints to switch `basemap_mode` (with the tiles→image warning when the family has geo answers) and to clear the image
- [ ] 2.5 Tests (eager task): happy path PNG→WebP, 25 MB refused, non-image `failed`, decompression bomb `failed` without decode, 12000×6000 → 8192×4096, supersede, raw deleted on success and failure, viewer refused, confirm required only for different aspect ratio with answers

## 3. Editor UI

- [ ] 3.1 Settings card image block: upload, processing indicator with 2 s HTMX poll, preview, error, mode switch, clear; hide tile checkboxes/default basemap/use geolocation in `image` mode
- [ ] 3.2 Section map picker: hide basemap override and search in `image` mode; map shows the image
- [ ] 3.3 i18n: RU strings for every new message (check with the language cookie, not only `.po`)
- [ ] 3.4 Browser check on the dev server: upload, switch, switch back, values restored

## 4. Rendering

- [ ] 4.1 `survey/assets/js/image_basemap.js` — `ImageBasemap.apply(map, cfg)`: overlay, padded `maxBounds` + viscosity, min/max zoom, background, returns bounds
- [ ] 4.2 `partials/image_basemap_data.html` (`json_script`), included wherever `basemap_layers.html` is
- [ ] 4.3 `partials/basemap_layers.html` branches: no tiles, no base entries, control kept for overlays
- [ ] 4.4 Respondent page: skip `MapPlaceSearch` and geolocation, ignore `override_basemap`, fit image unless start view is inside
- [ ] 4.5 Hand-built surfaces: Overview thumbnail, settings-panel previews, public results blocks
- [ ] 4.6 Template guard test: every template with `L.tileLayer(` also handles `image-basemap-data`
- [ ] 4.7 Tests: respondent page of an image survey has the config and no tile URL / search / geolocation; public results block ignores its basemap; tiles survey output unchanged
- [ ] 4.8 Browser check of all eight surfaces with an image survey, desktop and mobile width; draw point/line/polygon on the image, reopen, marks in place

## 5. Versions, duplication, trash

- [ ] 5.1 `clone_survey_for_draft()` and `publish_draft()` copy the image fields; old canonical file deleted on publish only if unreferenced
- [ ] 5.2 Whole-survey duplication copies the fields (shared file name)
- [ ] 5.3 `purge_survey()` deletes each distinct image name once
- [ ] 5.4 Tests: draft replace leaves published image, publish switches, shared file survives, purge deletes, duplicate shows the same image

## 6. Export / import

- [ ] 6.1 `export_survey_to_zip`: `basemap_mode` + `image_basemap` in `survey.json`, file under `basemap/`
- [ ] 6.2 `import_survey_from_zip`: run the file through `process_image_basemap_file`; missing/invalid → `tiles` + report line; old archives unchanged
- [ ] 6.3 `download_data`: `mapsurvey_image_basemap` member in every GeoJSON + image in ZIP, for image surveys only
- [ ] 6.4 Tests for every scenario in `specs/survey-serialization` and the data-export requirement

## 7. Release checks

- [ ] 7.1 Full suite once before, once after; summarise the delta
- [ ] 7.2 PR preview: upload through S3, confirm `basemap_images/` public and `basemap_uploads/` denied anonymously
- [ ] 7.3 PR preview: `loadtest/lecture-burst.js` against an image survey with a shared-map question
- [ ] 7.4 Real phones (mid-range Android, iPhone) with an 8192-px image; lower `IMAGE_BASEMAP_MAX_SIDE` if either stalls
- [ ] 7.5 Update `CLAUDE.md` Key Patterns with the image basemap rules (one predicate, one renderer, Null Island bounds, shared file names)
