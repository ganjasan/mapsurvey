## Context

Survey sections form a linked list via `next_section` / `prev_section` ForeignKeys on `SurveySection`. The `survey_section` view renders one section at a time. Currently there is no indication of how many sections exist or where the user is in the sequence. Users navigate with "Back" / "Next" buttons but have no sense of overall progress.

The base survey template (`base_survey_template.html`) has a `header` div containing the section title and a close button. The section template (`survey_section.html`) extends it and adds a subheading and question form.

## Goals / Non-Goals

**Goals:**
- Show the user their current position in the survey (e.g., "3 / 7")
- Minimal, non-intrusive indicator that works on both desktop and mobile layouts
- No database schema changes

**Non-Goals:**
- Visual progress bar (a simple text counter is sufficient for v1)
- Per-question progress within a section
- Tracking completion percentage based on answered questions

## Decisions

### 1. Compute section position by traversing the linked list in the view

**Choice:** Walk `prev_section` backward to count the current index, and walk `next_section` forward to count total remaining, then derive `current` and `total`.

**Alternative considered:** Query `SurveySection.objects.filter(survey_header=survey).count()` for total, and use an `order_number` field for position. Rejected because sections don't have an `order_number` — the ordering is defined solely by the linked list. A queryset count gives total but not position without the linked list walk anyway.

**Approach:** Helper method or inline logic in the view. Since this is a simple traversal used in one place, inline logic in the view is sufficient — no need for a model method.

### 2. Display location: inside the header area of `base_survey_template.html`

**Choice:** Add a `{% block progress %}` in `base_survey_template.html` between the title and content, and fill it from `survey_section.html`. This way other templates that extend the base aren't affected.

**Alternative considered:** Render inside navigation buttons area. Rejected — the progress indicator is informational context, not an action, so it belongs in the header.

### 3. Pass `section_current` and `section_total` as template context variables

**Choice:** Two integers in the template context. The template renders them as `{{ section_current }} / {{ section_total }}`.

**Rationale:** Simple, i18n-friendly (the template can wrap with `{% blocktrans %}`), and testable — the view test can assert on context values.

## Risks / Trade-offs

- **Linked list walk is O(n):** For a survey with many sections this adds n DB queries. In practice surveys have < 20 sections, so this is negligible. If needed later, the traversal can be replaced with a single `COUNT()` query + index computation. → Acceptable for now.
- **Broken linked list:** If `prev_section` / `next_section` links are inconsistent (e.g., a section is orphaned), the count may be wrong. → Low risk; section links are managed by admin and import code which maintain consistency.
