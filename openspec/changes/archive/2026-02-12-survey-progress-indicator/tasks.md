## 1. Backend — compute progress in the view

- [x] 1.1 In `survey_section` view, traverse `prev_section` links to compute `section_current` (1-based index) and traverse `next_section` links to compute `section_total`
- [x] 1.2 Add `section_current` and `section_total` to the template context dict passed to `render()`

## 2. Template — display progress indicator

- [x] 2.1 Add a `{% block progress %}{% endblock %}` in `base_survey_template.html` inside the header div (between title and close button area)
- [x] 2.2 In `survey_section.html`, fill the `progress` block with `{{ section_current }} / {{ section_total }}` markup
- [x] 2.3 Add CSS styling for the progress indicator in `main.css` — subtle, non-intrusive, readable on mobile

## 3. Tests

- [x] 3.1 Write a test that verifies `section_current` and `section_total` are correct in the template context for first, middle, and last sections of a multi-section survey
