## Why

The respondent upload endpoint limits every caller to 60 uploads an hour per IP. That ceiling exists for
anonymous respondents: a survey session is free to create, so per-session caps alone do not bound how much
an anonymous script can push into our storage. The operator entry form (change operator-entry, #355) uploads
through the same endpoint, so a workspace member entering paper forms is throttled like an anonymous visitor.
Loading 77 scanned paper forms into a customer survey stopped at the 60th file with 429 (#528).

## What Changes

- `survey_upload` skips the per-IP rate limit when the request names a valid operator-entry session
  (`entry_session` passing `_upload_entry_session`: signed in, editor role, Pro `operator_entry` in force,
  a non-online session of the survey's family).
- Anonymous and respondent uploads keep the limit unchanged. Content validation, size caps and per-session
  caps stay for everyone, operators included.

## Capabilities

### Modified Capabilities

- `file-upload-questions`: the per-IP upload rate limit is now specified, with the operator exemption.

## Impact

- `survey/views.py::survey_upload` — one condition before `is_ratelimited`.
- Tests in `survey/tests/test_file_upload_questions.py`.
- No migration, no setting, no template.
