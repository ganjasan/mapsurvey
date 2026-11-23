## Why

A survey whose first section is "Operators only" cannot be opened from its public link: the entry
view redirects to `start_section()` without asking the audience, the section view hides that
section on the respondent surface and redirects back to the entry, and the browser gives up with
`ERR_TOO_MANY_REDIRECTS` (#776). In production a new creator concluded publishing had failed (53
empty sessions in ten minutes), and a second survey with a single operators-only section has been
unreachable for twelve days (105 external sessions, 0 answers). Nothing in the editor says why.

## What Changes

- The respondent entry (`survey_header`) and the language picker send a respondent to the first
  section the **respondent surface** shows, computed by the visibility engine, instead of the head
  section. Operators-only sections at the start of the chain are skipped exactly as navigation
  already skips them in the middle.
- When a survey has sections but none is shown on the public link, the entry renders a calm page
  ("This survey has nothing to fill in yet", 200, noindex, no session) instead of redirecting. A
  signed-in collaborator also sees why (every section is "Operators only") and a link to the editor.
- The Build pane shows a warning banner while no section reaches the public link, so the creator
  learns it before sharing the link.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `question-audience`: adds the requirement that the public link starts at the first
  respondent-visible section, never loops, and that the editor warns when no section is shown to
  respondents.

## Impact

- `survey/visibility.py` — one helper, `respondent_entry_section(survey)`.
- `survey/views.py` — `survey_header`, `survey_language_select` use it; new template
  `survey_no_public_pages.html`.
- `survey/editor_views.py`, `editor/survey_detail.html` — the banner.
- Locale catalogs — the new strings in every offered language.
- No model, migration, API or MCP change. The pre-publish 409 warning (the `translation_gaps`
  pattern, which would touch the lifecycle service, REST and MCP) is a follow-up.
