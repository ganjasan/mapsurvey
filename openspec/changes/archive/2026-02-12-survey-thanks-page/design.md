## Context

After the last survey section, `survey_section` POST handler redirects to `survey.redirect_url` (default `"#"`). There's no built-in completion page — survey creators must host their own or leave users stranded.

Existing URL patterns already reserve names at the `<section_name>` level: `language/` and `download`. The same approach applies here.

The thanks page doesn't need map functionality, so it should extend `base.html` (Bootstrap, navbar) rather than `base_survey_template.html` (Leaflet, draw controls).

## Goals / Non-Goals

**Goals:**
- Provide a built-in thanks page at `/surveys/<survey_name>/thanks/`
- Clear the survey session on page load so the user can retake the survey
- Use `base.html` for a clean, lightweight page without map dependencies
- Make the built-in thanks page the default when `redirect_url` is not explicitly set

**Non-Goals:**
- Preventing re-submission (session clearing is for UX, not security)
- WYSIWYG editor for thanks_html in admin (raw HTML in TextField is sufficient, like Story.body)

## Decisions

### 1. Template base: `base.html` not `base_survey_template.html`

`base_survey_template.html` loads Leaflet, draw controls, crosshair overlay, and map JS — all unnecessary for a static thanks page. `base.html` provides Bootstrap and navbar, which is sufficient.

**Alternative considered**: Extending `base_survey_template.html` for visual consistency with survey sections. Rejected — it would load ~200 lines of unused JS and map dependencies for a page that just shows text.

### 2. Default redirect: use Django `reverse()` instead of sentinel string

When `redirect_url` is `"#"` (default), the last-section POST logic will redirect to the named URL `survey_thanks` using `reverse()`. If `redirect_url` is set to anything else, it's used as-is (preserving existing behavior for surveys with custom redirect URLs).

**Alternative considered**: Changing the model default to a sentinel like `"__thanks__"`. Rejected — it couples model state to URL routing. Checking for `"#"` is simpler and backwards-compatible.

### 3. Session cleanup in the thanks view

The thanks view reads `survey_language` first (for content resolution), then flushes `survey_session_id` and `survey_language` from `request.session`. This allows the user to retake the survey by navigating back to the survey start.

### 4. "thanks" as reserved section name

The URL pattern for `/surveys/<survey_name>/thanks/` is registered before `<section_name>/` in `urls.py`. This is the same pattern used for `language/` and `download`. A section named "thanks" would be unreachable.

### 5. Custom HTML content: `thanks_html` JSONField with language support

Add `SurveyHeader.thanks_html` — a `JSONField(default=dict, blank=True)` storing HTML per language: `{"en": "<h1>Thanks!</h1>", "ru": "<h1>Спасибо!</h1>"}`. Same key format as `Question.choices[].name` multilingual pattern.

The view reads `survey_language` from session **before** clearing it, then resolves content with fallback: requested language → `"en"` → first available key → empty (default message).

For single-language surveys (`survey_language` is None), a plain string is also accepted for convenience: `"<h1>Thanks!</h1>"`. The view normalizes both formats.

**Alternative considered**: TextField with single HTML for all languages. Rejected — doesn't support multilingual surveys, and the JSONField pattern is already established in the codebase for `Question.choices`.

## Risks / Trade-offs

- **Reserved name collision** → Acceptable trade-off. Same approach as `language/` and `download`. Section name "thanks" is unlikely and can be documented.
- **XSS via thanks_html** → Same trust model as `Story.body` — only survey creators (authenticated admin users) can edit the field. Acceptable.
