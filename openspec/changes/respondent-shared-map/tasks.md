## 0. Prerequisites

- [ ] 0.1 Worktree `../Mapsurvey-shared-map` on `feature/respondent-shared-map` from the merged #155 master; `.env.ports` offset 10; `env` symlink; `.env`; `collectstatic` (done 2026-09-05)
- [ ] 0.2 Archive `overlay-features` in the main checkout so its delta specs land in `openspec/specs/` before this change's `validate --strict` and archive

## 1. Model and migration (specs `shared-map-layer`, `shared-map-moderation`)

- [ ] 1.1 `SurveyMapLayer`: `source` (choices upload/question, default upload), `source_question_code`, `show_tallies=True`, `show_comments=False`, `approve_first=False`; `clean()` validates the code names a point/line/polygon question of the canonical survey
- [ ] 1.2 `LayerObject`: `status` (visible/pending/hidden, default visible, indexed with `layer`), `source_answer` (FK Answer, SET_NULL), `source_session` (FK SurveySession, CASCADE)
- [ ] 1.3 `Answer.hidden` (default False) with a model comment that it applies to text sub-answers on `question` layers only
- [ ] 1.4 Migration `0072_shared_map` — defaults only, reversible
- [ ] 1.5 Tests: field defaults, `clean()` rejects unknown/non-geo code, status choices

## 2. Materialisation (spec `shared-map-layer`, design D2)

- [ ] 2.1 `layers.sync_question_layer(layer, session)`: resolve source question by code within `session.survey`, build `s<session>-<n>` keys, upsert title/geometry/`source_answer`, delete surplus keys, status per `approve_first`, `rebuild_layer`
- [ ] 2.2 `layers.question_layers_for(survey, code)` helper (canonical layers whose `source_question_code == code`)
- [ ] 2.3 Hook in `survey_section` POST after geo answers are saved: for each geo question with source layers, call 2.1 inside try/except with logging (answers never lost on failure)
- [ ] 2.4 Label: `label_field` names a sub-question code; text → value, choice → label, else `''`; truncate 255
- [ ] 2.5 Tests (GIVEN/WHEN/THEN): first submit creates objects; re-submit keeps key + updates geometry + preserves another session's reaction; fewer features deletes surplus and its reactions; older version feeds canonical; materialisation error logged, answers saved

## 3. Respondent delivery (specs `shared-map-layer`, `reference-overlay-layers` delta, design D3–D4)

- [ ] 3.1 `layers.visible_objects(layer, exclude_session)` — status visible, clean sessions, not the given session
- [ ] 3.2 `survey_layer_geojson`: `question` branch builds per request from 3.1, adds `tally_up`/`tally_down`/`comment_count` when `show_tallies`, ETag with session id, `Cache-Control: private, no-store`; `upload` branch unchanged
- [ ] 3.3 `survey_layer_object`: 404 outside 3.1; `comments` (newest 10, non-hidden, clean, no author) when `show_comments`
- [ ] 3.4 `object_stats`: tally helper over the bound question's `thumbs` and text sub-questions honouring `Answer.hidden` and clean sessions; `rebuild_layer` + touch after `_save_object_answers` for `question` layers
- [ ] 3.5 Responses/editor surfaces (`build_layer_geojson`) keep serving all clean objects regardless of status for the creator; respondent metadata (`build_map_layers_metadata`) adds `source`, `show_tallies`
- [ ] 3.6 Respondent JS (`layer_objects_block.html`): tallies in rows and badges when present; popup card shows tallies line and comments list; "Your own marks are not in this list" hint; layer name default for the pair block heading
- [ ] 3.7 Tests: own marks absent; on_hold/not_approved/deleted sessions absent from collection and tallies; no-store + session-varying ETag; tallies present/absent per setting; comments present/absent per setting and `hidden`; card 404 for hidden/pending/own objects; rendered markup for rows/badges/hint

## 4. Moderation (spec `shared-map-moderation`, design D5)

- [ ] 4.1 Endpoints: object status change (approve/hide/show) and comment hide/show, owner/editor only, touch layer, 404 under kill switch
- [ ] 4.2 Responses → Shared map pane per `question` layer: per-object table + Status column, chips All/Pending/Hidden with counts, actions, row expander with comments and per-comment Hide/Show; warning when approve_first ∧ pending>0 ∧ min_objects>0; read-only for non-editors
- [ ] 4.3 Session validation-status change and soft-delete trigger `rebuild_layer` for `question` layers of that survey family
- [ ] 4.4 Tests: pending on approve_first layer; approve/hide/show transitions and respondent visibility after each; comment hide affects card and count, not export; warning condition; permissions

## 5. Editor (spec `survey-editor` delta, design D6)

- [ ] 5.1 Layer card: "New layer from answers" (geo question picker + label sub-question picker, choice types first, "listed by number" note), "source: answers" badge naming the question, settings in edit state, no upload/draw actions
- [ ] 5.2 Object editor read-only for `question` layers (no draw/import/card edits, explanatory banner)
- [ ] 5.3 Refuse deleting a geo question that is a layer source (message names the layer); code change cascades to `source_question_code`; note on the geo question form naming the layer(s)
- [ ] 5.4 Tests: create from answers (valid/invalid question, label picker contents and order); settings save; badge and absence of upload actions; read-only editor; delete refused; code cascade; note rendered

## 6. Export and serialization (specs `shared-map-layer`, `survey-serialization` delta, design D8–D9)

- [ ] 6.1 `download_data`: source geo question GeoJSON adds `mark_key`, `votes_up`, `votes_down`, `comments`; per-object CSV adds `status`
- [ ] 6.2 `serialize_layers` / `_clean_layer_config` / `extract_layers`: five new fields, no objects for `question` layers, downgrade with report line when the code resolves to nothing
- [ ] 6.3 Tests: export properties; CSV status column; ZIP round-trip of a `question` layer + pair; dangling code downgrade

## 7. Verification and close-out

- [ ] 7.1 Full suite once before and once after (no linter loops); `openspec validate --strict respondent-shared-map`
- [ ] 7.2 Browser pass on the dev stand: create the layer from answers, bind an Objects question with 👍/👎 + comment; as respondent A place a mark; as B see it, 👍 + comment, ✓; A re-submits, B's reaction survives; hide from Responses, B no longer sees it; approve-first flow; tallies off; comments on. Screenshots into the change folder
- [ ] 7.3 k6 `lecture-burst` on a PR preview against a shared-map survey (per-session endpoint cost, design risk 1)
- [ ] 7.4 Backlog: mark #160 promoted, note #153 no longer a prerequisite; CLAUDE.md paragraph on `question` layers and the one-source-of-truth rule for object keys
- [ ] 7.5 PR to master; Discord `#announcements` after merge; reply to Julian Thomas with the preview link (outreach rules: short, no technical cause)
