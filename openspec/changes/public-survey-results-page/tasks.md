## 1. Data model & migration

- [ ] 1.1 Add `PublicResultsPage` model (OneToOne→`SurveyHeader`; fields: `slug` unique, `visibility`, `is_published`, `intro` JSON, `mode`, `snapshot` JSON null, `snapshot_version`, `frozen_at`, `show_response_count`, `show_participate_cta`, `feature_in_listing`, `k_anonymity_threshold` default 3, timestamps)
- [ ] 1.2 Add `PublicResultsBlock` model (FK→`PublicResultsPage`; `question` FK null, `block_type`, `viz`, `custom_title` JSON, `geo_label_fields` JSON, `order`)
- [ ] 1.3 Register both models in `survey/admin.py`
- [ ] 1.4 Generate and apply migration; verify no changes to existing tables
- [ ] 1.5 Add model-level tests: defaults (k=3, mode=live, is_published=False), slug uniqueness, cascade on page delete

## 2. Results rendering service

- [ ] 2.1 Add a `PublicResultsService` (or thin wrapper) that, given a page, produces ordered per-block payloads from `SurveyAnalyticsService` for the canonical survey, using clean-session filtering
- [ ] 2.2 Implement k-anonymity masking (count>0 and <K → "<K"; K=1 disables) applied to bucket payloads only, not inside `SurveyAnalyticsService`
- [ ] 2.3 Implement anonymous geo payload builder: include only `geo_label_fields` in popups; strip session id / IP / UTM / per-record timestamps
- [ ] 2.4 Exclude blocks whose referenced question is missing/deleted; produce empty-state payload when zero clean responses
- [ ] 2.5 Ensure live and frozen render through one block-payload contract (same shape)
- [ ] 2.6 Tests: clean-session exclusion, canonical-survey aggregation across versions, k-anon masking, no record identifiers in geo, deleted-question omission, zero-response empty state

## 3. Freeze / live mechanics

- [ ] 3.1 Implement freeze: serialize current per-block payloads + counts + `frozen_at` into `snapshot` with `snapshot_version`; set `mode=frozen`
- [ ] 3.2 Implement refresh-snapshot and return-to-live transitions
- [ ] 3.3 Live render: wrap service call in Django cache keyed by `slug`+`lang`+`mode`, 60s TTL; frozen render reads `snapshot` only (no DB/cache)
- [ ] 3.4 Handle unknown `snapshot_version` on read with a "re-freeze needed" notice instead of crashing
- [ ] 3.5 Tests: frozen unchanged on new response, live reflects new response after cache window, freeze captures current data, return-to-live recomputes

## 4. Public page view, URL & SEO

- [ ] 4.1 Add `/r/<slug>/` route in `survey/urls.py` and the public view (read-only, 404 unless `is_published`)
- [ ] 4.2 Build public template: hero + intro, response counter, ordered blocks (chart/map/text/counter), CTA, "Made with Mapsurvey" footer
- [ ] 4.3 Chart blocks via Chart.js; map blocks via Leaflet + leaflet.heat reusing existing geo rendering patterns (respect leaflet.heat canvas-toggle quirk)
- [ ] 4.4 CTA: render only while survey is open to responses; hide otherwise
- [ ] 4.5 SEO: `robots index` + OG tags for public; `robots noindex` for unlisted; `?lang=` language switch consistent with other public pages
- [ ] 4.6 Integrate visibility into `/stories/` listing, `robots.txt`, and `sitemap.xml` (public+listing only)
- [ ] 4.7 Tests: reachability (published/unpublished/unknown slug), visibility→robots + listing inclusion/exclusion, CTA open/closed, footer present, no raw texts on page

## 5. Editor configuration tab (contextual)

- [ ] 5.1 Add `/editor/surveys/<uuid>/public-results/` views (editor-only) and a "Public results" nav tab
- [ ] 5.2 Sidebar: pinned "Page settings" entry separated from the "Content blocks" list (SortableJS drag-reorder, per-block hide toggle)
- [ ] 5.3 Contextual center: render EITHER page settings (visibility, URL/slug, intro, data mode + freeze, display & privacy incl. k-anon threshold) OR the selected block's config (visualization, custom title, geo popup fields) — never both
- [ ] 5.4 "Add block" question picker marks text/text_line questions as unavailable
- [ ] 5.5 HTMX endpoints: save page settings, add/edit/delete block, reorder, freeze/refresh/return-to-live; live preview pane
- [ ] 5.6 Tests: non-editor blocked, text questions not addable, reorder persists, freeze/live toggles persist, draft survey cannot publish results

## 6. Wiring & verification

- [ ] 6.1 Auto-create or lazily create `PublicResultsPage` on first visit to the config tab; default slug derived from survey
- [ ] 6.2 Run full `./run_tests.sh survey` suite; fix regressions
- [ ] 6.3 Update `CLAUDE.md` (URL structure + feature note) and survey serialization if results-page config should travel with export (decide; default: not exported)
- [ ] 6.4 Manual verification on Render PR preview: public page, unlisted noindex, freeze vs live, anonymous geo popup
