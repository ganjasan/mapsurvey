## Context

`survey_header` redirects to `survey.start_section()` (the head row). `survey_section` creates a
session, computes the respondent visibility map, and redirects a hidden section back to the entry.
Since change `operator-entry` a section can be hidden by audience alone, so an operators-only head
section closes the loop. The middle of the chain was never affected: navigation walks
`vmap.visible_sections`.

## Decisions

- **One helper in the engine.** `visibility.respondent_entry_section(survey)` =
  `compute_visibility(survey, {}, surface=respondent).visible_sections[0]` or None. With no answers
  the head can only be hidden by audience (a head rule has no earlier controller, so it is broken
  and fails open); a later section with a rule on an operators-only controller is hidden too, which
  is the engine's existing verdict. Entry, language picker and the editor banner all call it, so
  they cannot disagree with navigation.
- **No loop guard in `survey_section`.** Once the entry never points at a hidden section, the
  section view's existing `redirect('survey')` ends at a section the respondent sees or at the
  nothing-to-fill page. A direct hit on a hidden section still creates one empty session (it did
  before); the loop's twenty per visit are gone.
- **The nothing-to-fill page is a 200, noindex, no session**, rendered in `survey_header` after
  access control (so draft/held/closed keep their own responses) and before the language picker
  (choosing a language would lead nowhere). Collaborators are recognised with
  `get_effective_survey_role`; they get the cause and an editor link, respondents do not.
- **Banner, not a publish 409.** A 409 in `editor_survey_transition` would have to travel through
  the lifecycle service, REST and MCP like `translation_gaps`; the banner is visible before
  publishing and after, on every plan, and needs no API change. The 409 is a follow-up.

## Risks

- `compute_visibility` per entry hit loads the section structure once: the same queries the
  section view runs a redirect later.
