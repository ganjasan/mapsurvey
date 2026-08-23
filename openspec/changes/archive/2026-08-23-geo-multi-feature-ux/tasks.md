# Tasks — Geo Multi-Feature UX

## 1. Editor: min/max feature limits

- [x] 1.1 `question_form_modal.html`: add "Places per respondent" min/max number inputs,
      shown only for point/line/polygon input types, prefilled from
      `question.validation_settings.min_features` / `max_features`
- [x] 1.2 `editor_views.py` (`editor_question_edit`): parse `vs_min_features` /
      `vs_max_features` as ints for geo types; blank removes the key; reject
      `max < min`, `min < 0`, `max < 1` with a form error
- [x] 1.3 Tests: save round-trip (set → reload modal → values present; blank → keys gone),
      invalid range rejected, non-geo types never gain the keys

## 2. Widget plumbing

- [x] 2.1 `forms.py`: pass `min_features`/`max_features` from `question.validation_settings`
      through `LeafletDrawButtonField` → `LeafletDrawButtonWidget` context
- [x] 2.2 `leaflet_draw_button.html`: render `data-min-features`/`data-max-features` on the
      button (empty when unset); keep original title/subtitle in `data-orig-title`/
      `data-orig-subtitle`; add counter-chip span, progress container, feature `<ul>`,
      "show all" toggle
- [x] 2.3 Test: rendered section markup contains the data attributes and containers for a
      geo question with limits, and no progress container without limits

## 3. Respondent flow (base_survey_template.html + main.css)

- [x] 3.1 CSS in `survey/assets/css/main.css`: chip, progress line, feature list, armed
      button state, collapsed-list toggle (then `collectstatic`)
- [x] 3.2 `refreshGeoQuestionUI()`: derive per-question counts from `editableLayers`,
      update chip/title/subtitle/progress/disabled; `max_features == 1` questions keep
      today's look (no chip/progress/list)
- [x] 3.3 ~~Feature list~~ DROPPED in review: rows duplicated pins/chip; features are managed via their map popup. Progress moved inside the button.
      opens the layer popup, delete removes the layer, collapse past 3 rows
- [x] 3.4 Re-arm cycle: after popup apply (and after `draw:created` with no sub-questions)
      trigger the question's draw button on next tick unless at max; clicking the armed
      button disarms; verify no click leaks a stray feature (design §9)
- [x] 3.5 Hook refresh into: `draw:created`, popup apply, list delete, `restoreGeoAnswers`,
      `initSection`
- [x] 3.6 min enforcement in `htmx:configRequest`: forward-only, reuse
      `is-required-invalid` + `#required-summary`
- [x] 3.7 Template-comment guard test right after editing templates (feedback rule)

## 4. Server clamp

- [x] 4.1 `views.py` section POST: slice `geostr_list` to `max_features` when set
- [x] 4.2 Test: POST with more features than max stores exactly max answers; no limit
      stores all

## 5. Verification

- [x] 5.1 Full test suite `./run_tests.sh survey`
- [x] 5.2 Browser walkthrough of a dev survey: multi-geo section — place/save/delete cycle,
      counters per question, max disable, min block on forward nav, back nav restore
