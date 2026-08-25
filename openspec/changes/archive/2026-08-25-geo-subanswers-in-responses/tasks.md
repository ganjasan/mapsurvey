## 1. Service layer (survey/analytics.py)

- [x] 1.1 Add `_subanswer_display(answer)` helper formatting a sub-answer per input type (choice/multichoice/rating → joined choice names, number/range → numeric, text/text_line/datetime → text; geo/image/html → None) and a bulk fetch `_subanswers_by_parent(parent_ids)` returning `{parent_answer_id: [{name, value}]}` ordered by sub-question `order_number`
- [x] 1.2 `get_geo_feature_collection`: attach `attributes` list to each feature's properties via the bulk fetch (one extra query total), keeping `question`/`type`/`session_id` unchanged
- [x] 1.3 `format_session_answers`: for geo answers, attach `objects: [{index, attributes}]` to the answer row and put `attributes` into each mini-map feature's properties

## 2. Templates / JS

- [x] 2.1 `analytics_geo_map.html`: on pointer-mode click, open an `L.popup` at the feature built from `properties.question` + `properties.attributes` using DOM `textContent` (no innerHTML from values); keep selection and details-mode behavior untouched
- [x] 2.2 `analytics_session_detail.html`: render numbered attribute groups under each geo answer row from `row.objects`, skipping empty groups; rely on template autoescaping

## 3. Tests (survey/tests.py, GIVEN/WHEN/THEN docstrings)

- [x] 3.1 Feature collection: geo answer with choice+number sub-answers → `attributes` ordered and formatted; geo answer without children → empty list; text sub-answer included; query count bounded (assertNumQueries)
- [x] 3.2 `format_session_answers`: session with two points for one geo question → two numbered `objects` groups; geo answer without children → no group
- [x] 3.3 Rendered markup: session detail modal response contains sub-answer name and value; value with `<script>` arrives escaped (covers the "test client misses HTML5 validation" lesson — assert on markup, not just context)

## 4. Verification

- [ ] 4.1 Run `./run_tests.sh survey` (baseline before, once after; summarize delta)
- [x] 4.2 Manual pass in browser on a survey with multi-object geo answers: popup in pointer mode, modal groups, details mode unchanged
