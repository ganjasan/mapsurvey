# E2E Test Plan — Mapsurvey UI

Comprehensive Playwright coverage plan for every user-facing surface defined in `openspec/specs/`.

## Conventions

- **Status**: `done` already in the suite · `next` ready to write today · `blocked` needs infra · `manual` stays manual (visual / non-deterministic)
- **Priority**: `P0` core happy path · `P1` important flow · `P2` edge case / nice-to-have
- **Effort**: rough sizing — `S` ≤ 30 min · `M` ~1 h · `L` ½ day +
- One Playwright test = one `def test_...` in `tests_e2e/` mapped to one or two related Scenarios from a spec

## Summary matrix

| Area | Tests planned | done | next | blocked | manual |
|------|---------------|------|------|---------|--------|
| Public surfaces (landing, cards, stories, trust) | 8 | 0 | 7 | 0 | 1 |
| Authentication & registration | 4 | 0 | 4 | 0 | 0 |
| Editor — dashboard | 5 | 2 | 3 | 0 | 0 |
| Editor — survey creation | 3 | 0 | 3 | 0 | 0 |
| Editor — settings + map position | 6 | 1 | 5 | 0 | 0 |
| Editor — sections CRUD + reorder | 5 | 0 | 5 | 0 | 0 |
| Editor — questions CRUD + reorder + choices + subs | 8 | 0 | 6 | 1 | 1 |
| Editor — translations | 4 | 0 | 4 | 0 | 0 |
| Editor — live preview | 2 | 0 | 2 | 0 | 0 |
| Editor — read-only / lifecycle states | 5 | 0 | 5 | 0 | 0 |
| Editor — versioning (draft → publish) | 6 | 0 | 6 | 0 | 0 |
| Editor — version-aware download | 2 | 0 | 2 | 0 | 0 |
| Respondent — language selection | 4 | 0 | 4 | 0 | 0 |
| Respondent — section navigation + progress | 4 | 1 | 3 | 0 | 0 |
| Respondent — answer prepopulation | 7 | 0 | 7 | 0 | 0 |
| Respondent — non-geo question types (text/choice/range/etc) | 8 | 1 | 6 | 1 | 0 |
| Respondent — geo question types (point/line/polygon) | 9 | 0 | 8 | 0 | 1 |
| Respondent — mobile crosshair + edit | 7 | 0 | 1 | 6 | 0 |
| Respondent — basemaps | 3 | 1 | 2 | 0 | 0 |
| Respondent — thanks page | 4 | 0 | 4 | 0 | 0 |
| Respondent — password gate | 3 | 0 | 3 | 0 | 0 |
| Respondent — geolocation auto-center | 2 | 0 | 0 | 2 | 0 |
| Analytics — dashboard charts | 7 | 0 | 6 | 1 | 0 |
| Analytics — geo map + heatmap | 5 | 0 | 4 | 1 | 0 |
| Analytics — cross-filtering | 4 | 0 | 4 | 0 | 0 |
| Analytics — anomalies / inline editing / validation | 8 | 0 | 6 | 2 | 0 |
| Analytics — bulk operations | 4 | 0 | 4 | 0 | 0 |
| Analytics — session detail + tags | 4 | 0 | 4 | 0 | 0 |
| Export & import (ZIP / CSV / GeoJSON) | 6 | 0 | 6 | 0 | 0 |
| Organizations / multi-user | 6 | 0 | 4 | 2 | 0 |
| UTM tracking + event analytics | 4 | 0 | 3 | 1 | 0 |
| UI i18n (EN/RU chrome) | 3 | 0 | 3 | 0 | 0 |
| **TOTAL** | **160** | **6** | **134** | **17** | **3** |

---

## 1. Public surfaces

| ID | Spec / Requirement | Test | Priority | Status | Effort |
|----|---------------------|------|----------|--------|--------|
| LP-01 | landing-page · sections layout | `/` renders hero + use-cases + demo + features sections | P0 | done (Django) | — |
| LP-02 | landing-page · navbar | Sticky nav shows Mapsurvey brand, Sign In, Sign Up | P1 | next | S |
| LP-03 | landing-page · footer | Footer renders product, open-source, legal columns | P2 | next | S |
| LP-04 | survey-cards · response count visible | Public surveys list shows response counts | P1 | next | S |
| LP-05 | survey-cards · ordering | Surveys ordered by `last_response_at` desc on `/surveys/` | P1 | next | M |
| LP-06 | survey-cards · archived hidden | `archived=True` surveys are hidden from public list | P1 | next | S |
| LP-07 | public-stories · story detail | `/stories/<slug>/` renders heading + body | P2 | next | M |
| TP-01 | trust-page · `/trust/` reachable | `/trust/` returns 200 and includes GDPR keywords | P1 | manual | — |

## 2. Authentication & registration

| ID | Spec | Test | Priority | Status | Effort |
|----|------|------|----------|--------|--------|
| AU-01 | django-registration | `/accounts/register/` form creates user + personal org | P0 | next | M |
| AU-02 | django-registration | Duplicate username shows error inline | P1 | next | S |
| AU-03 | login flow | Valid credentials redirect to `/editor/` | P0 | next | S |
| AU-04 | login flow | Invalid credentials show error, stay on `/accounts/login/` | P1 | next | S |

## 3. Editor — dashboard

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| ED-01 | survey-editor · dashboard integration | `/editor/` lists my surveys with cover gradients | P0 | done | — |
| ED-02 | (cover-gradient bug fix) | Cover gradient stable across reloads | P0 | done | — |
| ED-03 | survey-editor · dashboard integration | "New Survey" link visible and goes to `/editor/surveys/new/` | P0 | next | S |
| ED-04 | survey-editor · dashboard integration | "Show Archived" toggle reveals archived surveys | P1 | next | S |
| ED-05 | survey-deletion · confirmation + cascade | Delete from dashboard confirms then removes survey + sessions | P0 | next | M |

## 4. Editor — survey creation

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| EC-01 | survey-editor · Survey creation | Submit form → SurveyHeader created with UUID + default head section | P0 | next | M |
| EC-02 | (creation page map picker) | Create form has interactive map picker; click sets start position | P1 | next | M |
| EC-03 | (creation page geolocation) | When geolocation succeeds, picker auto-centers on user's coords | P1 | blocked (browser perms) | M |

## 5. Editor — settings + map position

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| ES-01 | survey-editor · Survey settings | Editor toolbar shows Settings link | P0 | done | — |
| ES-02 | survey-editor · Survey settings | Update visibility public ↔ private persists | P0 | next | S |
| ES-03 | survey-editor · Survey settings | Update `available_languages` saves and reloads correctly | P1 | next | S |
| ES-04 | survey-editor · Section map position | Settings → Map Position modal opens, click sets section start | P1 | next | M |
| ES-05 | (inherit mode) | "Use survey default" shows faded marker + flyTo | P1 | next | M |
| ES-06 | (read-only lock) | Map Position button disabled with tooltip on `published` survey | P1 | next | S |

## 6. Editor — sections CRUD + reorder

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| SC-01 | survey-editor · Section CRUD · create | "New Section" appends to linked list, sidebar updates | P0 | next | M |
| SC-02 | survey-editor · Section CRUD · edit | Rename section title persists + updates sidebar | P0 | next | S |
| SC-03 | survey-editor · Section CRUD · delete | Delete middle section re-links neighbours | P0 | next | M |
| SC-04 | survey-editor · Section reordering | Drag section up rebuilds linked list | P0 | next | L |
| SC-05 | survey-editor · Section CRUD · delete only | Delete the only section leaves survey with zero sections | P2 | next | S |

## 7. Editor — questions CRUD + reorder + choices + subs

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| QC-01 | survey-editor · Question CRUD | Add question of each type via select + form | P0 | next | M |
| QC-02 | survey-editor · Question reordering | Drag question rebuilds order_number | P0 | next | M |
| QC-03 | survey-editor · Choices editor | Add 3 choices, set names, save → JSON in `Question.choices` | P0 | next | M |
| QC-04 | survey-editor · Sub-question management | Geo question accepts a text sub-question; renders nested in editor | P1 | next | M |
| QC-05 | inline-choices · validate JSON structure | Submitting malformed JSON shows error | P1 | next | S |
| QC-06 | question-card-styling · cards wrap each question | Each question rendered inside `.question-card` div | P1 | next | S |
| QC-07 | question-card-styling · custom radio/checkbox | Custom-styled inputs render (visual diff) | P2 | manual | — |
| QC-08 | survey-editor · Question CRUD · delete cascades | Delete question removes its sub-questions + choices | P1 | blocked (need fixture w/ subs) | M |

## 8. Editor — translations

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| TR-01 | survey-content-translation · section | Add `ru` translation to section, save → `SectionTranslation` row | P0 | next | M |
| TR-02 | survey-content-translation · question | Same for question name + subtext | P0 | next | M |
| TR-03 | inline-choices · choice translation | Choice `name` JSON gets `{"en", "ru"}` keys after edit | P1 | next | M |
| TR-04 | survey-editor · Translation management | Translation tab lists all translatable strings for a survey | P1 | next | M |

## 9. Editor — live preview

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| LV-01 | survey-editor · Live inline preview | Preview iframe loads on section select | P1 | next | S |
| LV-02 | survey-editor · Live inline preview | Editing a question name updates the preview after save | P1 | next | M |

## 10. Editor — read-only / lifecycle states

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| LS-01 | survey-lifecycle-states · transitions | `draft → testing → published → closed → archived` buttons each work | P0 | next | M |
| LS-02 | survey-lifecycle-states · published lock | Published survey: editor inputs disabled, "Create draft" prompt | P0 | next | M |
| LS-03 | survey-password-protection · set password | Add password to survey; password hash saved | P1 | next | S |
| LS-04 | survey-access-control · testing token | Testing survey accessible via `?test_token=...` even without login | P1 | next | M |
| LS-05 | survey-lifecycle-states · archived hidden | Archived survey hidden from `/editor/` unless `?show_archived=1` | P1 | next | S |

## 11. Editor — versioning (draft → publish)

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| VS-01 | survey-versioning · create draft | Click "Create draft" on published survey → new draft clone exists | P0 | next | M |
| VS-02 | survey-versioning · publish draft | Compatible draft can be published; canonical pointer updated | P0 | next | M |
| VS-03 | survey-versioning · publish moves sections | After publish, Answer→Question FKs intact | P0 | next | M |
| VS-04 | survey-versioning · discard draft | Discard removes draft + its sessions | P0 | next | M |
| VS-05 | survey-versioning · incompatibility blocks | Removing a question that has answers blocks publish | P1 | next | M |
| VS-06 | (test-session cleanup) | Publish deletes draft test sessions | P1 | next | S |

## 12. Editor — version-aware download

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| DL-01 | version-export-ui | Download dropdown lists `latest`, `vN`, `all` options | P0 | next | M |
| DL-02 | version-export-ui | Each option triggers `?version=...` parameter on download URL | P0 | next | S |

## 13. Respondent — language selection

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| RL-01 | survey-language-selection · multilingual entry | `/surveys/<slug>/` redirects to `/language/` for multilingual | P0 | next | S |
| RL-02 | survey-language-selection · single-language entry | Single-language survey skips the picker | P0 | next | S |
| RL-03 | survey-language-selection · select stores in session | Click language → `SurveySession.language` set, redirected to first section | P0 | next | M |
| RL-04 | survey-language-selection · direct section access | Direct `/surveys/<slug>/section_2/` redirects back to `/language/` | P1 | next | S |

## 14. Respondent — section navigation + progress

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| RN-01 | persistent-map-htmx-navigation · DOM identity | Map DOM node survives section navigation (sentinel test) | P0 | done | — |
| RN-02 | survey-progress · indicator format | Section page shows "N / M" format | P1 | next | S |
| RN-03 | persistent-map-htmx-navigation · back button | Back navigation returns previous section partial | P0 | next | M |
| RN-04 | persistent-map-htmx-navigation · last section | Submitting last section triggers HX-Redirect to thanks | P0 | next | M |

## 15. Respondent — answer prepopulation

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| AP-01 | answer-prepopulation · text/number | Back nav prepopulates text and number inputs | P0 | next | M |
| AP-02 | answer-prepopulation · choice/multichoice | Radios + checkboxes restore selection | P0 | next | M |
| AP-03 | answer-prepopulation · range/rating | Slider value restored | P1 | next | S |
| AP-04 | answer-prepopulation · datetime | Datetime input restored | P1 | next | S |
| AP-05 | answer-prepopulation · geo features | Pinned point/line/polygon restored on map | P0 | next | L |
| AP-06 | answer-prepopulation · sub-question values | Sub-questions of restored geo features prepopulate too | P1 | next | L |
| AP-07 | answer-prepopulation · re-submission updates | Re-submitting a section updates not duplicates Answers | P1 | next | M |

## 16. Respondent — non-geo question types

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| QT-01 | question types | `text` + `text_line` accept input and persist | P0 | next | S |
| QT-02 | question types | `number` accepts numeric value and persists | P0 | next | S |
| QT-03 | question types | `choice` (radio) accepts one selection | P0 | next | S |
| QT-04 | question types | `multichoice` (checkbox) accepts multiple selections | P0 | next | S |
| QT-05 | (range slider tick marks) | Range slider renders ticks + from-to labels | P0 | done | — |
| QT-06 | question types | `rating` widget accepts star value | P1 | next | M |
| QT-07 | question types | `datetime` input accepts ISO timestamp | P1 | next | S |
| QT-08 | question types | `image` upload — multipart PUT writes to media | P1 | blocked (file fixture) | M |

## 17. Respondent — geo question types

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| GT-01 | marker-draw-lifecycle · single-shot point | Click "Add point" → click map → marker drops, draw mode ends | P0 | next | M |
| GT-02 | marker-draw-lifecycle · single-shot line | Draw line, click finish-button, line persists | P0 | next | M |
| GT-03 | marker-draw-lifecycle · single-shot polygon | Draw polygon, finish, polygon persists | P0 | next | M |
| GT-04 | marker-popup-isolation · scoped form | Two markers each open their own scoped popup form | P1 | next | L |
| GT-05 | geo-field-validation · required empty | Required geo question with no feature blocks submit | P0 | next | M |
| GT-06 | geo-field-validation · visual feedback | Validation error highlights the geo widget | P1 | next | S |
| GT-07 | crosshair-marker-edit · reposition | Click existing marker → crosshair → drag → Apply moves it | P1 | next | M |
| GT-08 | crosshair-marker-edit · cancel restores | Cancel returns marker to original lat/lng | P1 | next | S |
| GT-09 | (limit-geopoint-count, future) | After N points the "Add" button disables | P2 | manual | — |

## 18. Respondent — mobile crosshair + edit

Use Playwright `device` profile (iPhone 13) for these. All marked blocked except apply-action smoke because they need a touch-emulated viewport plus real Leaflet draw lifecycle.

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| MO-01 | mobile-point-crosshair · apply places marker | Crosshair Apply on point question places marker | P0 | next | M |
| MO-02 | mobile-point-crosshair · cancel discards | Cancel hides crosshair without placing | P0 | blocked (touch lifecycle) | M |
| MO-03 | mobile-point-crosshair · only point uses crosshair | Polygon draw on touch uses normal draw, not crosshair | P1 | blocked | M |
| MO-04 | mobile-point-crosshair · info panel slide | Info panel animates in from right on mobile | P2 | blocked | L |
| MO-05 | crosshair-marker-edit · info-panel hides | Existing marker tap opens edit-mode crosshair, info panel hides | P1 | blocked | L |
| MO-06 | crosshair-marker-edit · cancel restores position | Edit-mode Cancel keeps original lat/lng | P1 | blocked | M |
| MO-07 | mobile-point-crosshair · touch detection | `data-touch="true"` set on body when ontouch supported | P2 | blocked | S |

## 19. Respondent — basemaps

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| BM-01 | satellite-basemap-options · respondent | Satellite + topo tile URLs render | P0 | done | — |
| BM-02 | satellite-basemap-options · settings | Owner sees basemap checkboxes in settings | P0 | done | — |
| BM-03 | satellite-basemap-options · switcher | Click satellite layer in switcher → tiles change | P1 | next | M |

## 20. Respondent — thanks page

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| TH-01 | survey-thanks-page · default | Submitting last section redirects to `/thanks/` | P0 | next | M |
| TH-02 | survey-thanks-page · custom html | Custom `thanks_html` (per language) renders | P1 | next | S |
| TH-03 | survey-thanks-page · custom redirect | When `redirect_url ≠ "#"`, redirect goes there instead | P1 | next | S |
| TH-04 | survey-thanks-page · clears session | After thanks page, `survey_session_id` cleared from cookie | P0 | next | S |

## 21. Respondent — password gate

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| PW-01 | survey-password-protection · gate shown | Password-protected survey shows `/password/` form | P0 | next | M |
| PW-02 | survey-password-protection · correct accepts | Right password sets cookie + advances to language/section | P0 | next | M |
| PW-03 | survey-password-protection · wrong rejects | Wrong password keeps gate, shows error | P1 | next | S |

## 22. Respondent — geolocation auto-center

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| GL-01 | geolocation-map-centering · with permission | When geolocation granted, map centers on user coords | P1 | blocked (permission grant) | M |
| GL-02 | geolocation-map-centering · denied fallback | When denied, map falls back to `start_map_postion` | P1 | blocked | M |

## 23. Analytics — dashboard charts

Owner-only — runs as `logged_in_page`. Pre-seed survey + N sessions + answers via ORM.

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| AN-01 | survey-analytics-dashboard · loads | `/editor/surveys/<uuid>/analytics/` returns 200 with charts | P0 | next | M |
| AN-02 | analytics · choice histogram | Choice question chart renders bars matching counts | P0 | next | M |
| AN-03 | analytics · multichoice histogram | Multichoice chart sums counts > sessions (multi-select) | P1 | next | M |
| AN-04 | analytics · range/rating histogram | Range chart shows distribution across ticks | P1 | next | M |
| AN-05 | analytics · text answers list | Text answers list paginates 20 per page | P1 | next | M |
| AN-06 | analytics · language breakdown | Multilingual survey shows Languages chart + table | P1 | next | M |
| AN-07 | plausible-analytics | Plausible script tag injected on prod-like setup | P2 | blocked (env-gated) | S |

## 24. Analytics — geo map + heatmap

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| GM-01 | analytics geo map · features layer | Each geo question becomes a layer with N markers | P0 | next | M |
| GM-02 | analytics-heatmap · add layer | "+ Heatmap" creates a new heat layer from selected questions | P1 | next | L |
| GM-03 | analytics-heatmap · radius/blur/opacity | Settings popover changes layer rendering live | P2 | next | L |
| GM-04 | analytics-heatmap · z-order | Drag-reorder of legend items reflects in canvas stacking | P2 | next | L |
| GM-05 | analytics-heatmap · canvas display toggle | Hide/show toggles `canvas.style.display` | P1 | blocked (canvas access) | M |

## 25. Analytics — cross-filtering

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| CF-01 | cross-filtering · click bar filters | Click a chart bar adds filter pill, other charts update | P0 | next | M |
| CF-02 | cross-filtering · clear all | "Clear all filters" resets every chart | P0 | next | S |
| CF-03 | unify-selection-filtering · selection → filter | Map lasso selection turns into a filter pill | P1 | next | L |
| CF-04 | unify-selection-filtering · table sync | Table row selection mirrored on map | P1 | next | M |

## 26. Analytics — anomalies / inline editing / validation

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| AV-01 | session-validation-status · 4 statuses | Set Pending/Valid/Invalid/Trash via UI persists | P0 | next | M |
| AV-02 | clean-export · respects status | Export with "valid only" excludes invalid sessions | P0 | next | M |
| AV-03 | auto-validation-basic · empty rule | Empty session auto-flags as invalid | P1 | next | M |
| AV-04 | answer-linting-errors · geo bbox | Out-of-bbox geo answer raises a lint error | P1 | next | M |
| AV-05 | anomalies-panel · checkboxes | Anomalies panel lists sessions, checking moves them in bulk | P1 | next | L |
| AV-06 | inline-editing-basic · text/choice/number | Inline-edit a text answer in attribute table persists | P1 | next | M |
| AV-07 | inline-editing-geo · redraw | Inline geo redraw saves new geometry | P2 | blocked (drag emulation) | L |
| AV-08 | validation-settings · per-survey thresholds | Configure thresholds per survey, apply triggers re-validation | P2 | blocked (background job) | L |

## 27. Analytics — bulk operations

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| BO-01 | bulk-operations · select all | Header checkbox selects all visible rows | P0 | next | S |
| BO-02 | bulk-operations · bulk delete | "Move to trash" applies to selection | P0 | next | M |
| BO-03 | bulk-operations · bulk tag | "Tag selection" assigns tag to all selected | P1 | next | M |
| BO-04 | bulk-operations · empty selection guard | Bulk action with no selection shows nothing/no-op | P2 | next | S |

## 28. Analytics — session detail + tags

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| SD-01 | analytics-session-detail · panel opens | Click row → side panel shows session metadata + answers | P0 | next | M |
| SD-02 | session-tags-notes · add tag | Type tag in panel → saved on session | P1 | next | S |
| SD-03 | session-tags-notes · note text | Note textarea saves on blur | P1 | next | S |
| SD-04 | analytics-session-detail · trash button | Trash button moves session to trashed, panel closes | P1 | next | S |

## 29. Export & import

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| EX-01 | survey-serialization · ZIP via Web UI | Download → ZIP contains GeoJSON + CSV + survey.json | P0 | next | M |
| EX-02 | survey-serialization · GeoJSON content | Each geo question file has FeatureCollection with N features | P0 | next | M |
| EX-03 | survey-serialization · CSV content | CSV has header + row per session, multichoice joined `; ` | P0 | next | M |
| EX-04 | (export language column) | CSV/GeoJSON include `language` column for multilingual | P1 | next | S |
| EX-05 | survey-serialization · import via Web UI | Upload prior ZIP creates a new survey clone | P0 | next | M |
| EX-06 | survey-serialization · roundtrip | Export survey → import → questions/sections match | P1 | next | L |

## 30. Organizations / multi-user

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| OR-01 | org-workspaces · personal org auto-created | New user has personal org + owner membership | P0 | next | M |
| OR-02 | org-workspaces · org switcher | Switcher in nav lists all my orgs and switches active | P0 | next | M |
| OR-03 | org-workspaces · invite by email | Owner invites email; pending invitation visible | P1 | next | M |
| OR-04 | org-workspaces · accept invite | Invitee logs in → membership granted | P1 | next | M |
| OR-05 | org-workspaces · permission denial | Member cannot delete a survey they didn't create | P1 | blocked (role matrix) | L |
| OR-06 | org-workspaces · cross-org survey hidden | User can't see another org's surveys | P1 | blocked (multi-user fixture) | L |

## 31. UTM tracking + event analytics

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| UT-01 | survey-event-tracking · session_start | Visit survey emits `session_start` event row | P0 | next | M |
| UT-02 | survey-event-tracking · session_complete | Submit last section emits `session_complete` | P0 | next | M |
| UT-03 | utm-link-generator · link tracking | Visiting `?utm_source=foo` creates a `TrackedLink` row | P1 | next | M |
| UT-04 | survey-event-tracking · page_leave | Closing tab emits `page_leave` event (sendBeacon) | P2 | blocked (beacon timing) | L |

## 32. UI i18n (EN/RU chrome)

| ID | Spec / Req | Test | Priority | Status | Effort |
|----|------------|------|----------|--------|--------|
| UI-01 | ui-internationalization · all strings i18n | Page in `?lang=ru` shows translated nav labels | P1 | next | S |
| UI-02 | ui-internationalization · JS receives translated | Confirm-delete dialog uses translated string in RU | P1 | next | M |
| UI-03 | ui-internationalization · email template | Password-reset email body in user's chosen language | P2 | next | M |

---

## Suggested rollout order

1. **P0 happy-path stack first** (≈ 35 tests): AU-03 → EC-01 → SC-01..03 → QC-01/03 → ES-02 → LS-01 → RL-01..03 → RN-01/04 → AP-01/02/05 → QT-01..04 → GT-01..03/05 → TH-01/04 → DL-01/02 → AN-01/02 → CF-01/02 → AV-01/02 → BO-01/02 → SD-01 → EX-01..03/05 → OR-01/02 → UT-01/02
2. **P1 round-up** (~ 70 tests) — fills feature parity
3. **P2 + blocked** — defer until tooling ready

## Tooling gaps to unblock

- **File upload fixture** for `image` question (MO-08 / QT-08 / EX-fixtures)
- **Mobile viewport profile** for crosshair tests (MO-* group)
- **Geolocation permission grant** in browser context (GL-*, EC-03)
- **Multi-user session** for org-membership tests (OR-05/06)
- **Background job stub** for validation re-run (AV-08)
- **Email outbox capture** for password-reset / invite tests (UI-03, OR-04)
- **Plausible script env override** for AN-07
- **Canvas pixel inspection** for heatmap tests (GM-05)

## Maintenance rules

- One spec scenario → one test where possible. Keep tests independent (each creates its own survey via the fixture).
- Use selectors stable across CSS refactors: prefer roles, `name`, and `data-testid` (none exist yet — adding them is a follow-up). Avoid relying on Tailwind class names.
- Skip-on-CI markers (`@pytest.mark.flaky`) only for genuinely time-dependent flows like UT-04.
- Keep the suite under ~5 minutes by parallelising via `pytest -n auto` (`pytest-xdist`) once headcount > 30 tests.
