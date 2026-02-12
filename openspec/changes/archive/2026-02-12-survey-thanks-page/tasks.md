## 1. URL and View

- [x] 1.1 Add `survey_thanks` view to `survey/views.py`: get survey by name (404 if not found), clear `survey_session_id` and `survey_language` from session, render template
- [x] 1.2 Add URL pattern `surveys/<survey_name>/thanks/` in `survey/urls.py` before the `<section_name>/` pattern, named `survey_thanks`

## 2. Template

- [x] 2.1 Create `survey/templates/survey_thanks.html` extending `base.html` with a thank-you message

## 3. Redirect Logic

- [x] 3.1 Update last-section POST redirect in `survey_section` view: use `reverse('survey_thanks', args=[survey_name])` when `redirect_url == "#"`, otherwise use `redirect_url` as-is

## 4. Custom HTML Content with Language Support

- [x] 4.1 Add `thanks_html` JSONField (default=dict, blank=True) to `SurveyHeader` model
- [x] 4.2 Create migration for the new field
- [x] 4.3 Update `survey_thanks` view: read `survey_language` before clearing session, resolve `thanks_html` content with fallback (requested lang → "en" → first key → None), pass resolved HTML to template
- [x] 4.4 Update `survey_thanks.html`: render resolved HTML via `|safe` when set, default message otherwise

## 5. Tests

- [x] 5.1 Test: GET `/surveys/<name>/thanks/` returns 200 and clears session
- [x] 5.2 Test: GET `/surveys/nonexistent/thanks/` returns 404
- [x] 5.3 Test: Last section POST with default `redirect_url="#"` redirects to thanks page
- [x] 5.4 Test: Last section POST with custom `redirect_url` redirects to custom URL
- [x] 5.5 Test: Thanks page with empty `thanks_html` shows default message
- [x] 5.6 Test: Thanks page with multilingual `thanks_html` renders correct language
- [x] 5.7 Test: Thanks page falls back to "en" when session language not in `thanks_html`
- [x] 5.8 Test: Thanks page with plain string `thanks_html` renders it directly
