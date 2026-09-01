## 0. Working checkout and prerequisites

- [x] 0.1 Worktree `../Mapsurvey-feature-browser` on `feature/overlay-feature-browser` from `origin/master`; bootstrapped (`env`, `.env`, `PORT_OFFSET=250`, `collectstatic`)
- [ ] 0.2 Commit backlog items #151, #152 and the INDEX row to `master` (they exist only uncommitted in the main checkout) and mark them "Promoted on 2026-09-01"; mark FD-17 `feature-draw-overlay-layer-in-editor` as absorbed by this change
- [ ] 0.3 Run `geo_subq_usage.sql` against prod (owner runs `! psql "$MAPSURVEY_DB_URL" -f …`) and paste the four result blocks into `mechanism-ab.mockup.html` section 0 note — informs hint copy only (D4)
- [ ] 0.4 Baseline: `./run_tests.sh survey` green before any change

## 1. PR 1 — Objects: model, migration, derived GeoJSON (spec `layer-objects`)

- [ ] 1.1 Models: `LayerObject` (layer FK, key, title, category, description, link, `GeometryField(srid=4326)`, position, properties JSON, timestamps, `unique(layer, key)`) and `LayerObjectAsset` (object FK, kind, file on `PublicMediaStorage` under `layer_assets/<uuid4>.<ext>`, embed_url, title, size_bytes, position); `SurveyMapLayer.geojson_legacy`
- [ ] 1.2 `survey/layers.py`: `build_layer_geojson(layer)` (raw properties + reserved `_key/_title/_category/_has_content/_cover`), `rebuild_layer(layer)` updating `geojson`, `feature_count`, `size_bytes`, `updated_at`; caps enforced on object create (5000 features, 10 MB derived)
- [ ] 1.3 `layers_for(survey)` resolver (`canonical_survey or survey`) and route every reader through it: `build_map_layers_metadata`, `_editor_layers`, `survey_layer_geojson`, settings card, serialization of versions; regression test that a draft copy and an archived version read the canonical layers
- [ ] 1.4 Data migration splitting existing layers into objects per design D-4 (key from `key_field` if unique else `f-<index>`; title from `label_field`/`name`/key; Multi*/GeometryCollection exploded with `<key>-<n>`; raw properties kept), verifying feature count + bbox, keeping `geojson_legacy`, logging fallbacks; rehearse on a prod dump
- [ ] 1.5 Object card endpoint `GET /surveys/<uuid>/layers/<id>/objects/<key>/` (same gate + kill switch as the layer endpoint; description via `coerce_creator_html`; attachments as URLs/embeds)
- [ ] 1.6 Asset validation: reuse `uploads.py` MIME sniffing and the 25 MB constant; per-object cap 10, per-layer cap 200 MB; embed allow-list (YouTube, Vimeo) → sanitized iframe
- [ ] 1.7 Tests (GIVEN/WHEN/THEN): rebuild on write + ETag change; key uniqueness on import; raw properties preserved; card endpoint gated; script stripped; cover = first image; oversized/spoofed/over-cap uploads refused; embed host allow-list; migration lossless on a 35-polygon fixture and duplicate-key fallback

## 2. PR 1 — Object editor screen (spec `layer-object-editor`)

- [ ] 2.1 View + URL `/editor/surveys/<uuid>/layers/<id>/` (owner-only, 404 under kill switch) rendering `editor/layer_editor.html` from `editor_base.html`: list column, map column, card column; "published: changes are visible immediately" banner when the canonical survey is published
- [ ] 2.2 JSON endpoints in new `survey/layer_object_views.py`: `POST objects/`, `PATCH objects/<key>/`, `DELETE objects/<key>/` (reports answer count in the confirm payload), `POST objects/<key>/geometry/`, assets `POST/PATCH/DELETE` + `reorder/`, `POST bulk/` (`set_category`, `delete`)
- [ ] 2.3 Imports: `POST import/geojson/` with mapping + dry-run report (collisions, unmapped), `POST import/csv/` (coordinates → objects; content → matched by key then title, unmatched reported), `POST import/photos/` (multi-file, stem matched by key then title, unmatched reported); `label_field`/`key_field` as default mapping
- [ ] 2.4 Front-end `survey/assets/js/layer_editor.js`: virtualised list (search, category chips, "no photo"/"no text" chips, multi-select + bulk bar, ↑/↓/Enter, map follows selection), Leaflet.draw (point/line/polygon/edit/delete → create/geometry endpoints), card autosave (debounced PATCH, saved/saving/error indicator), Quill description with image upload via a layer-scoped endpoint mirroring `editor_survey_thanks_image`, attachment list with drag reorder + cover marking + drop zone + embed link, Prev/Next over the filtered list; labels above a zoom threshold for > 50 objects
- [ ] 2.5 Empty state with the three entry points; Reference layers card: object count + attachment summary, "Open editor", "New layer" (creates empty layer → editor), delete refused when bound (message names the question)
- [ ] 2.6 Serialization (`survey-serialization` delta): export `objects.json` + `assets/` per layer, derived GeoJSON keyed by `_key`; import objects then assets with per-item warnings; legacy `layers/<n>.geojson` without `objects.json` → objects created as the migration does; whitelist cleaner extended (description sanitized, embed hosts)
- [ ] 2.7 Tests: owner/viewer access; draw → create → card open; geometry move rebuilds; GeoJSON dry-run and confirm; CSV coordinates; content CSV matched by title with unmatched report; photo import by key + unmatched; bulk category; delete-with-answers confirm payload; autosave PATCH; description sanitized on save; caps; serialization round-trip incl. attachments and missing-asset warning; template-comment guard test on new templates
- [ ] 2.8 Browser pass on the real page (not the test client): draw, import 200-row CSV, filter, keyboard, upload photo, reorder, embed, Prev/Next; screenshot into the change folder
- [ ] 2.9 PR 1: `feat(layers): object editor — objects, attachments, imports` with the migration; verify pre-deploy migration on a Render PR preview seeded from a prod dump

## 3. PR 2 — Question types and editor modal (specs `thumbs-question`, `question-type-picker`, `survey-editor`)

- [ ] 3.1 `thumbs`: `INPUT_TYPE_CHOICES`, picker metadata (Questions group, `fa-thumbs-up`, hint), form field + widget (two buttons, stores `up`/`down` in `Answer.text`), respondent CSS, required handling, translations of the two labels; tests: answer/change, required, export value
- [ ] 3.2 `layer_objects`: `INPUT_TYPE_CHOICES`, picker metadata (Map questions group, `fa-map-marked-alt`, hint), offered only on map-layout sections with ≥1 layer and kill switch on; `Question.layer` FK (PROTECT), `min_objects`, `objects_search`; `QuestionForm` fields (layer picker limited to `layers_for(survey)`, minimum replaces `required`, search mode), validation "layer required"
- [ ] 3.3 Sub-question form excludes `layer_objects` alongside geo types (client + server); parent-capable check helper `question.can_have_subquestions` used by list item, modal and form
- [ ] 3.4 Question modal *Sub-questions* section for parent-capable types: nested list rendered from `question_list_item.html` in sub mode, "Add sub-question" → existing `editor_subquestion_create`, empty-state geo tip line, `hx-swap-oob` keeping modal and section lists in sync; disabled state in read-only surveys
- [ ] 3.5 Section list item: `layer_objects` badge with layer name + count and `min N` badge; "Add Sub-question" under `layer_objects` cards
- [ ] 3.6 Modal preview for `layer_objects` renders the list block; `editor_question_preview_live` handles the new types
- [ ] 3.7 Tests: picker groups/visibility rules; thumbs widget + storage; `layer_objects` form validation; sub-question exclusion client/server for `layer_objects`; modal Sub-questions list add/reorder/delete and sync with section list; read-only disabled; polygon without sub-questions saves; cloning keeps `Question.layer`

## 4. PR 2 — Respondent list block, popup and answers (specs `layer-objects-question`, `object-answers`, `reference-overlay-layers` delta)

- [ ] 4.1 `Answer.layer_object` FK (CASCADE) + partial `UniqueConstraint(survey_session, question, layer_object)`; migration verified against existing rows
- [ ] 4.2 `SurveySectionAnswerForm`: `layer_objects` renders the list block (no own field); sub-question forms pre-rendered into `_subquestionsForms[code]` as for geo; POST parsing of `obj__<key>__<code>` fields (unknown keys ignored, hidden block discarded, one row per (session, question, object) upsert); `min_objects` validation with the inline required message; session restore repopulates values and answered state
- [ ] 4.3 Respondent JS in `base_survey_template.html`: list block from the loaded layer GeoJSON (cover, title, category), search/chips per `objects_search` (`auto` rule), list ↔ map dimming, row/feature click → `flyToBounds` + highlight + `openPopup(_buildPopupHtml(card + sqHtml))` with ✓ only, card HTML fetched from the object endpoint and cached per key, `onPopupClose` keeps values, answered Set → ticks/badges/counter; interactivity off during draw/crosshair modes (`draw:drawstart/drawstop`); `show_popups` keeps read-only meaning for unbound layers
- [ ] 4.4 Layer deletion refused when bound (PROTECT surfaced as a message); editor preview renders the block identically
- [ ] 4.5 Tests: constraint; POST upsert and unknown-key ignore; hidden-block discard; min_objects pass/fail; session restore; rendered markup asserts for list, chips (auto rule at 3 vs 6 objects), ✓/badge classes, popup controls (no delete/edit); bound-layer popup vs unbound read-only popup; draw-mode guard (browser pass — the test client cannot drive Leaflet)
- [ ] 4.6 Browser pass on desktop + a 360 px phone: list → popup → ✓ → tick → counter; Next with min unmet; tap over object during point placement places the point; screenshots into the change folder
- [ ] 4.7 PR 2: `feat(survey): objects on the map — list block, popup answers, thumbs`

## 5. PR 3 — Read: export, Responses, public results (spec `object-answers`)

- [ ] 5.1 `download_data`: `objects_<code>.csv` (session_id, object_key, object_title, one column per sub-question; thumbs as `up`/`down`) and `layers/<name>.results.geojson` (derived GeoJSON + `answers`, per-sub-question `mean/count`, `up/down`, per-choice counts, text `count`; no text values)
- [ ] 5.2 Responses tab: per-object badge on the map ("31 · 4.2★ · 👍 24/7"), object selection through `SelectionManager` keyed by `object_key`, per-object table filter; thumbs aggregate in question stats
- [ ] 5.3 Public results: block type `object_ratings` in `PublicResultsService` (per-object bars, k-anonymity mask, no text), editor block picker entry, serialization excluded as before
- [ ] 5.4 Drop `geojson_legacy` (migration) after one release with PR 1 in production and no mismatch logs
- [ ] 5.5 Tests: CSV shape and columns; results GeoJSON aggregates and absence of text; Responses badge data + selection filter; `object_ratings` masking at `k = 3`; thumbs share
- [ ] 5.6 PR 3: `feat(results): per-object export, aggregates and public block`

## 6. Close-out

- [ ] 6.1 CLAUDE.md: replace the FD-1 paragraph's "`key_field` … no UI consumer" with the objects model, the canonical-ownership rule (D-3) and the live-edit caveat; note the one-mechanism rule for sub-questions
- [ ] 6.2 Backlog: add "variant B — object card in the panel as an alternative view" (D6) and "per-layer category colours" as new items; close #151, #152, FD-17
- [ ] 6.3 `/opsx:verify` then `/opsx:archive` — sync deltas into `openspec/specs/` (watch the delta-header-in-main-spec archive trap)
- [ ] 6.4 Discord post per shipped PR (`scripts/notify_discord.sh`); Sarasota MPO and ThINK Jena told when PR 2 is live
