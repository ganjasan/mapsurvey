## 0. Prerequisites

- [x] 0.1 Worktree `../Mapsurvey-shared-map` on `feature/respondent-shared-map` from the merged #155 master; `.env.ports` offset 10; `env` symlink; `.env`; `collectstatic` (done 2026-09-05)
- [ ] 0.2 Archive `overlay-features` in the main checkout so its delta specs land in `openspec/specs/` before this change's `validate --strict` and archive

## 1. Model and migration (specs `shared-map-layer`, `shared-map-moderation`)

- [x] 1.1 `SurveyMapLayer`: `source` (choices upload/question, default upload), `source_question_code`, `show_tallies=True`, `show_comments=False`, `approve_first=False`; `clean()` validates the code names a point/line/polygon question of the canonical survey
- [x] 1.2 `LayerObject`: `status` (visible/pending/hidden, default visible, indexed with `layer`), `source_answer` (FK Answer, SET_NULL), `source_session` (FK SurveySession, CASCADE)
- [x] 1.3 `Answer.hidden` (default False) with a model comment that it applies to text sub-answers on `question` layers only
- [x] 1.4 Migration `0072_shared_map` — defaults only, reversible
- [x] 1.5 Tests: field defaults, `clean()` rejects unknown/non-geo code, status choices

## 2. Materialisation (spec `shared-map-layer`, design D2)

- [x] 2.1 `layers.sync_question_layer(layer, session)`: resolve source question by code within `session.survey`, build `s<session>-<n>` keys, upsert title/geometry/`source_answer`, delete surplus keys, status per `approve_first`, `rebuild_layer`
- [x] 2.2 `layers.question_layers_for(survey, code)` helper (canonical layers whose `source_question_code == code`)
- [x] 2.3 Hook in `survey_section` POST after geo answers are saved: for each geo question with source layers, call 2.1 inside try/except with logging (answers never lost on failure)
- [x] 2.4 Label: `label_field` names a sub-question code; text → value, choice → label, else `''`; truncate 255
- [x] 2.5 Tests (GIVEN/WHEN/THEN): first submit creates objects; re-submit keeps key + updates geometry + preserves another session's reaction; fewer features deletes surplus and its reactions; older version feeds canonical; materialisation error logged, answers saved

## 3. Respondent delivery (specs `shared-map-layer`, `reference-overlay-layers` delta, design D3–D4)

- [x] 3.1 `layers.visible_objects(layer, exclude_session)` — status visible, clean sessions, not the given session
- [x] 3.2 `survey_layer_geojson`: `question` branch builds per request from 3.1, adds `tally_up`/`tally_down`/`comment_count` when `show_tallies`, ETag with session id, `Cache-Control: private, no-store`; `upload` branch unchanged
- [x] 3.3 `survey_layer_object`: 404 outside 3.1; `comments` (newest 10, non-hidden, clean, no author) when `show_comments`
- [x] 3.4 `object_stats`: tally helper over the bound question's `thumbs` and text sub-questions honouring `Answer.hidden` and clean sessions; `rebuild_layer` + touch after `_save_object_answers` for `question` layers
- [x] 3.5 Responses/editor surfaces (`build_layer_geojson`) keep serving all clean objects regardless of status for the creator; respondent metadata (`build_map_layers_metadata`) adds `source`, `show_tallies`
- [x] 3.6 Respondent JS (`layer_objects_block.html`): tallies in rows and badges when present; popup card shows tallies line and comments list; "Your own marks are not in this list" hint; layer name default for the pair block heading
- [x] 3.7 Tests: own marks absent; on_hold/not_approved/deleted sessions absent from collection and tallies; no-store + session-varying ETag; tallies present/absent per setting; comments present/absent per setting and `hidden`; card 404 for hidden/pending/own objects; rendered markup for rows/badges/hint

## 4. Moderation (spec `shared-map-moderation`, design D5)

- [x] 4.1 Endpoints: object status change (approve/hide/show) and comment hide/show, owner/editor only, touch layer, 404 under kill switch
- [x] 4.2 Responses → Shared map block (inside the bound question's per-object results on the Charts pane, not a new pane — the pane router, split view and mobile bar would all need plumbing for one table): per-object table + Status column, chips All/Pending/Hidden with counts, actions, row expander with comments and per-comment Hide/Show; warning when approve_first ∧ pending>0 ∧ min_objects>0; read-only for non-editors
- [x] 4.3 Session validation-status change and soft-delete trigger `rebuild_layer` for `question` layers of that survey family
- [x] 4.4 Tests: pending on approve_first layer; approve/hide/show transitions and respondent visibility after each; comment hide affects card and count, not export; warning condition; permissions

## 5. Editor (spec `survey-editor` delta, design D6)

- [x] 5.1 Layer card: "New layer from answers" (geo question picker + label sub-question picker, choice types first, "listed by number" note), "source: answers" badge naming the question, settings in edit state, no upload/draw actions
- [x] 5.2 Object editor read-only for `question` layers (no draw/import/card edits, explanatory banner)
- [x] 5.3 Refuse deleting a geo question that is a layer source (message names the layer); question codes are not editable in the editor, so the cascade lives only in the import remap (6.2); note on the geo question form naming the layer(s)
- [x] 5.4 Tests: create from answers (valid/invalid question, label picker contents and order); settings save; badge and absence of upload actions; read-only editor; delete refused; code cascade; note rendered

## 6. Export and serialization (specs `shared-map-layer`, `survey-serialization` delta, design D8–D9)

- [x] 6.1 `download_data`: source geo question GeoJSON adds `mark_key`, `votes_up`, `votes_down`, `comments`; per-object CSV adds `status`
- [x] 6.2 `serialize_layers` / `_clean_layer_config` / `extract_layers`: five new fields, no objects for `question` layers, downgrade with report line when the code resolves to nothing
- [x] 6.3 Tests: export properties; CSV status column; ZIP round-trip of a `question` layer + pair; dangling code downgrade

## 8. Owner revisions after the PR-preview test (2026-09-05)

- [x] 8.1 One door (D6): layer picker on the Objects question form with the "Respondents' marks on…" group; `_resolve_layer_choice` creates/reuses the `question` layer; shared-map settings block on the form (`_apply_shared_map_settings`); type offered when geo questions exist; `json_attr` filter
- [x] 8.2 Settings card: question-layer card shows badge + used-by, name/colour only; "New layer from answers" view, URL, form and JS removed
- [x] 8.3 Question rows created on type pick (D6a): `draft=1` branch of `editor_question_create`, `_edit_modal_response` with out-of-band list item and `questionUpdated` trigger; create modal = picker only (`data-create-picker`); draft cleanup on `hidden.bs.modal` when the name is empty
- [x] 8.4 Sub-questions block restored in the edit modal; `?return=modal` / `return_to_parent=1` bring sub-question create and edit back to the parent's modal ("Back to question"); the undefined `section` in the sub-question create error path fixed
- [x] 8.5 Mobile: tappable markers radius 11 under `pointer: coarse`, interactive tally badge; counter without a total on question layers
- [x] 8.6 Tests: `QuestionDraftOnTypePickTest`, `SharedMapEditorTest` rewritten for the one door, modal test rewritten; 47 OK on the editor classes
- [ ] 8.7 Owner browser pass of the new creator flow on the preview (automation cannot log in): pick type → edit modal → add sub-question → back; Objects question with a geo source; close an unnamed draft

## 7. Verification and close-out

- [x] 7.1 Full suite after: 1911 OK, 1 skipped (2026-09-05, after the owner revisions); `openspec validate --strict` valid
- [x] 7.2 (respondent flow, 2026-09-05 on dev 8010: three seeded marks with tallies + badge, popup with tallies line, 👍 + comment + ✓, own mark placed via crosshair + WHY, Finish → materialised as s10-1, reload: own mark restored as editable, absent from the list, park-gate tally 5·1, reacted row ticked. Editor screens covered by SharedMapEditorTest/SharedMapModerationTest — the automation cannot log in.) Browser pass on the dev stand: create the layer from answers, bind an Objects question with 👍/👎 + comment; as respondent A place a mark; as B see it, 👍 + comment, ✓; A re-submits, B's reaction survives; hide from Responses, B no longer sees it; approve-first flow; tallies off; comments on. Screenshots into the change folder
- [ ] 7.3 k6 `lecture-burst` on a PR preview against a shared-map survey (per-session endpoint cost, design risk 1)
- [ ] 7.4 Backlog: mark #160 promoted, note #153 no longer a prerequisite (the backlog file lives only in the main checkout's uncommitted changes — do it there); [x] CLAUDE.md paragraph on `question` layers and the one-source-of-truth rule for object keys
- [ ] 7.5 PR to master; Discord `#announcements` after merge; reply to Julian Thomas with the preview link (outreach rules: short, no technical cause)
