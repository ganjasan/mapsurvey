# AI agent that creates surveys from chat description

**Type**: idea
**Priority**: high
**Area**: frontend
**Created**: 2026-04-25

## Description

Conversational AI agent that builds a complete survey from a user's natural-language description. The user describes their goal in chat ("I want to ask Treviglio residents where the worst traffic is"); the agent asks clarifying follow-ups (target audience, languages, age brackets, what to map), then generates a fully populated survey — sections, questions with correct input types (text/choice/multichoice/range/point/line/polygon/image), choice options, and basic logic. The user lands in the editor with a working draft instead of an empty canvas.

## Notes

- Goal: dramatically increase registration → first-published-survey conversion. Empty editor is the biggest drop-off point in the funnel today (most users register, create one empty draft, never return).
- Funnel context: see related backlog item on funnel monitoring — needed to measure the lift from this feature.
- Strong fit for our DB activity: most institutional users (NYU, Alexandria, TU Dortmund, Michael Baker) register, create an untitled "Test" draft, and disappear within minutes.
- Implementation sketch:
  - Chat panel inside `/editor/surveys/new/` (HTMX + streaming).
  - Backend uses Claude API with tool use to call internal `create_section`, `create_question`, `set_choices` actions against the existing editor models.
  - Pre-built templates per use case (urban planning, citizen science, school routes, event mapping) help steer early conversations.
  - Question-type selection is the high-leverage decision: agent should default to `point` whenever a location is implied.
- Privacy: chat content goes to Claude API — must show clear notice; consider self-hostable variant via local model later.
- Reuses the survey serialization format (export/import) — agent produces a JSON survey blob, which is imported via `/editor/import/`.
