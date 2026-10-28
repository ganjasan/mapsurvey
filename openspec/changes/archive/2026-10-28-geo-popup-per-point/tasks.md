## 1. Service (render)

- [x] 1.1 `_map_payload`: build each feature's `properties` per point from its own sub-answers; drop the session-join
- [x] 1.2 Replace `_collect_label_values` with `_collect_point_labels` — one query over `parent_answer_id__in` grouped per geo answer, reusing `_answer_display_value` (free text self-excludes)

## 2. Editor (config)

- [x] 2.1 `public_results_config` context: `geo_subquestions` = non-text sub-questions of the selected map block's geo question
- [x] 2.2 `public_results.html` geo-popup-fields: iterate `geo_subquestions`; checkbox value = sub-question code; empty state when the geo question has no eligible sub-questions

## 3. Tests

- [x] 3.1 Rework `test_geo_popup_only_selected_fields` to the sub-answer model (sub-question of the point question)
- [x] 3.2 Add: two points in one session show DISTINCT popup values from their own sub-answers (proves per-point, not per-session)
- [x] 3.3 Keep `test_geo_has_no_record_identifiers`; free-text sub-answer never appears
- [x] 3.4 Full `./run_tests.sh survey` green

## 4. Verify

- [x] 4.1 Browser on :8010: pick a geo question with sub-questions → popup fields list its sub-questions; a geo question without sub-questions → empty state
