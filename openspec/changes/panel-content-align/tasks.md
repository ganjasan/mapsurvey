## 1. Model

- [x] 1.1 `CONTENT_WIDTH_CHOICES`, `CONTENT_VALIGN_CHOICES`; `SurveySection.content_width`, `content_valign`; `layout_classes()` adds `content-column` / `content-middle` (not for `form`, not for unknown values)
- [x] 1.2 Migration `0107_section_content_align`

## 2. Respondent page

- [x] 2.1 `survey_section_partial.html`: `data-content-width`, `data-content-valign`
- [x] 2.2 `base_survey_template.html` `initSection()` step 0: toggle `content-column` / `content-middle` (off on `form`)
- [x] 2.3 `main.css` (min-width block): column rules on `.header`, `.survey-progress`, `#content`, `#navig_buttons`; middle rules on `#section-panel` / `#section-data` with auto margins
- [x] 2.4 Manual pass: image + right/half column/middle (welcome), HTMX into a long map + right/half column/middle section (starts at the title, scrolls), 390 px for both; the other combinations and the switch back to a default section are covered by the class tests only

## 3. Editor

- [x] 3.1 `SurveySectionForm`: fields after `panel_width`, labels, help texts, required=False + clean_* keeping stored values
- [x] 3.2 `section_detail_form.html`: hide the two controls for `form` in `syncLayoutControls()`
- [x] 3.3 New strings in the offered catalogs (+ `.mo`)

## 4. Travel

- [x] 4.1 ZIP export + `_choice()` import of both fields
- [x] 4.2 REST `SectionIn` / `SectionOut`, `forms_bridge.SECTION_FIELDS`, `out.section`; MCP descriptions; regenerate `reference/api.md`, `reference/mcp-tools.md`

## 5. Tests

- [x] 5.1 Rendering: no class by default; each combination's classes and data attributes; `form` ignores; unknown value ignored
- [x] 5.2 Editor POST saves both; POST without them keeps them; live survey edits in place
- [x] 5.3 Draft copy and ZIP round trip carry both; legacy archive defaults; unknown values default
- [x] 5.4 API PATCH + 422 on `content_valign: "bottom"`; MCP `update_section`
- [x] 5.5 Run the touched modules (layout, i18n, help site, API structure, MCP structure, reference freshness)

## 6. Docs

- [x] 6.1 Help `how-to/lay-out-a-section.md`: the two settings and the Senf-style recipe
- [x] 6.2 Extend the epic's card `survey/changelog/2026-10-28-section-layout.html` (no new entry)
- [x] 6.3 CLAUDE.md section-layout paragraph: the two settings
