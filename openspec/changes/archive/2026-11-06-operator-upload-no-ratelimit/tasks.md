## 1. Implementation

- [x] 1.1 `survey_upload`: skip `is_ratelimited` when `_upload_entry_session` admitted the request's `entry_session`
- [x] 1.2 Tests (GIVEN/WHEN/THEN) in `survey/tests/test_file_upload_questions.py`: anonymous limited at 60/h; operator not limited; online session / viewer role still limited

## 2. Verification

- [x] 2.1 `./run_tests.sh survey.tests.test_file_upload_questions survey.tests.test_operator_entry`
- [x] 2.2 `openspec validate operator-upload-no-ratelimit --strict`
