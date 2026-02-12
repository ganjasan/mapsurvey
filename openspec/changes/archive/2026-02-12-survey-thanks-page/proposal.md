## Why

After completing a survey, users are redirected to `SurveyHeader.redirect_url` which defaults to `"#"` (no redirect). Most surveys set it to `/thanks/` or an external URL, but the platform has no built-in completion page. Survey creators have to either host their own thanks page or leave users on a dead-end. A built-in thanks page removes this friction and provides a polished survey completion experience out of the box.

## What Changes

- Add a new `survey_thanks` view and template that displays a "Thank you" message after survey completion
- Register the URL at `/surveys/<survey_name>/thanks/`
- The page clears the survey session so the user can retake the survey by navigating back
- The page uses the existing `base.html` for a lightweight page without map dependencies
- The default `SurveyHeader.redirect_url` changes from `"#"` to a sentinel value that routes to the built-in thanks page
- Add `thanks_html` JSONField to `SurveyHeader` — stores HTML per language as `{"en": "<h1>Thanks!</h1>", "ru": "<h1>Спасибо!</h1>"}` (same pattern as `Question.choices[].name`). When empty, shows default message. View reads `survey_language` from session before clearing it to pick the right translation.

## Capabilities

### New Capabilities
- `survey-thanks-page`: Built-in survey completion page with session cleanup, accessible at `/surveys/<survey_name>/thanks/`

### Modified Capabilities

## Impact

- `survey/views.py` — new view function
- `survey/urls.py` — new URL pattern, placed **before** the `<section_name>/` pattern (same approach as existing `language/` and `download` routes — "thanks" becomes a reserved section name)
- `survey/templates/` — new template
- `survey/models.py` — new `thanks_html` TextField, migration
- `survey/views.py:285` — update redirect logic for last section POST to use built-in thanks page when `redirect_url` is default
