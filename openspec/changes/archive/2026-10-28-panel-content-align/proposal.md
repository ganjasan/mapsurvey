## Why

Since #473 a section's panel can be a third or half of the screen wide. Its content — title, progress, subheading, questions, Back/Next — still starts at the top edge and stretches to the panel's full width, so a wide panel reads as long lines stuck to the top with empty space below. Senf's sections (Carroll Creek case study) keep the panel at its size but set the content as a column of reading width, centred inside the panel horizontally and vertically (issue #476, epic #478).

This is one more OPTION for the creator, not a new default: a section that does not ask for it renders exactly as today.

## What Changes

- Two new per-section settings, independent of each other and of the #473 controls:
  - `content_width`: `full` (default, today — content spans the panel) or `column` (content is a column of reading width, centred horizontally in the panel).
  - `content_valign`: `top` (default, today) or `middle` (content shorter than the panel is centred vertically; longer content starts at the top and scrolls, never clipped).
- They apply to `map` and `image` sections on a desktop. A `form` section (already a centred card) and every phone layout ignore them.
- The panel's close button keeps its corner; the footer (Made with Mapsurvey, abuse notice) stays at the bottom of the panel.
- Editor: two more controls in the section modal's Layout block, hidden for the Form stage. Safe edit on a live survey; carried by the draft copy, duplicate, ZIP, REST and MCP like the #473 controls.
- No new "What's new" entry: the epic's single card (`2026-10-28-section-layout.html`) is extended.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `section-form-layout`: adds the content alignment requirement; the travel requirement and the editor requirement name the two new settings.

## Impact

- `survey/models.py` + migration `0107`: `content_width`, `content_valign`, choices; `SurveySection.layout_classes()` adds `content-column` / `content-middle`.
- Respondent: `partials/survey_section_partial.html` (data attributes), `base_survey_template.html` (`initSection()` step 0 toggles the two classes), `main.css` (desktop-only rules).
- Editor: `SurveySectionForm` fields, `section_detail_form.html` (show/hide with the stage).
- `serialization.py` (export + whitelisted import), `api/v1/schemas.py`, `out.py`, `forms_bridge.py`, `mcp/tools/sections.py`; regenerated API/MCP references.
- Catalogs for the offered languages, help page `how-to/lay-out-a-section.md`, the epic's changelog card, CLAUDE.md paragraph.
- Tests in `survey/tests/test_section_form_layout.py`, `api/tests/test_v1_structure.py`, `mcp/tests/test_structure.py`.
