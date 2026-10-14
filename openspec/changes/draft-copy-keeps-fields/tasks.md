## 1. Copy helper

- [x] 1.1 `cloning.plain_field_values(instance, exclude)` — every concrete non-relational non-pk field
- [x] 1.2 `cloning.copy_section_translations(section, new_section)` — all fields incl. `next_label`
- [x] 1.3 `clone_section` and `clone_survey_for_draft` create sections from the helper; explicit only `is_head`, `name`, `title`, `code`, `survey_header`, `visibility_rule`, linked list
- [x] 1.4 `clone_question` takes plain fields from the helper; keeps `visibility_rule` when in-survey or codes are preserved

## 2. Tests

- [x] 2.1 Guard test: every concrete field of `SurveySection`, `SurveySectionTranslation`, `Question`, `QuestionTranslation` equal between live and draft (ids/FKs excluded)
- [x] 2.2 Round-trip: live survey with question + section rules, form section, `next_label` (+ translation), `hidden_layers` → `clone_survey_for_draft` → `publish_draft` → all preserved on the canonical
- [x] 2.3 Cross-survey paste still drops the rule (existing test stays green)

## 3. Repair report

- [x] 3.1 `report_draft_field_loss` management command (read-only) with a test
- [x] 3.2 Run it against production and attach the result to #329

## 4. Verification

- [x] 4.1 `./run_tests.sh survey` once before and once after
