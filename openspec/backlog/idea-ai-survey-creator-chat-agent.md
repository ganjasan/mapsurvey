# AI agent that creates surveys from chat description

**Type**: idea
**Priority**: high
**Area**: frontend
**Epic**: growth
**Tier**: **Pro**
**Created**: 2026-04-25
**Updated**: 2026-07-29 — assigned to the Pro tier (marginal LLM cost makes a free tier untenable)
**Related**: [Interactive onboarding](idea-interactive-onboarding.md), [Survey template gallery](feature-survey-template-gallery.md), [Funnel monitoring](feature-funnel-monitoring.md), [Reduce geo-input friction](improvement-reduce-geo-input-friction.md)

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

## Data grounding (2026-06-10 analysis)

- Activation funnel quantified: of 222 real registrations only **53% create a survey, 38% add a question, 33% get a response**. The empty-editor top-of-funnel is the biggest leak — exactly what this agent targets. The highest-ceiling activation bet.
- **Geo-quality is the make-or-break constraint**: geo questions are already the most-skipped type for respondents (point 32%, line 31%, polygon 16.5% answer-rate vs 40–48% non-geo — see [reduce geo-input friction](improvement-reduce-geo-input-friction.md)). The agent must bias to `point` and use `polygon` sparingly, or it will generate high-friction surveys that look done but don't collect. Generation quality is judged on downstream completion, not just "a survey was produced".

## Evidence from a paying-capable buyer (call, 2026-07-31)

ThINK Jena — a climate consultancy, exactly the persona we want. Three signals from one
call, all pointing here:

- **He never engaged with building a survey.** Marcus registered, made a test survey, and
  came to the call without having worked through the editor. This is the dormant-account
  pattern from the funnel data above, but observed live in a buyer who *does* have real
  projects — so the empty editor is not only a hobbyist problem.
- **He asked whether AI could filter irrelevant answers** — unprompted, before any pitch.
  His interest starts *after* collection, not at authoring. See
  [AI response triage](feature-ai-response-triage.md) (#95).
- **He had never heard of MCP.** Worth recording because it kills a tempting shortcut:
  exposing Mapsurvey as an MCP server and letting users bring Claude/ChatGPT is not a
  product for this segment. They will not assemble a toolchain. The assistant has to be
  inside the product, with no external account, or it does not exist for them.

## Activation stack (not a competitor to onboarding/templates)

This is the **core** of a 3-layer activation stack (see [growth epic](epics/growth.md) "Activation stack"):
1. [Template gallery](feature-survey-template-gallery.md) — seed/few-shot library the agent draws from + deterministic fallback when generation fails or is cost-capped.
2. [Interactive onboarding](idea-interactive-onboarding.md) — the wrapper that offers the agent and drives draft→publish→share.
3. **This agent** — produces the personalized draft.

## Risks to design for

- **LLM cost + abuse vector**: generation is expensive; bots could trigger costly calls. Gate behind onboarding + Turnstile + rate-limit (see [abuse-prevention](epics/abuse-prevention.md)); cap free generations per account.
- **Hallucinated "looks-done-but-empty" surveys** — must validate the generated blob (≥1 answerable question, sane geo usage) before handing off.
- **Multilingual correctness** — the platform supports 75 content languages; generated questions/choices must be coherent in the requested language.
- **Latency / streaming UX** — first useful output fast, or users bail mid-generation.

## Sequencing / measurement

- Prerequisite: [funnel monitoring](feature-funnel-monitoring.md) — we cannot prove AI > onboarding > template on conversion without it. Ship instrumentation + the cheap template/onboarding baseline first, then launch the agent as flagship and measure lift against that baseline.
- Use the latest, most capable Claude model for generation (AI-native product; quality of the first draft is the whole value prop).

## Tier tension (2026-07-29)

Assigned to **Pro** — generation has real marginal cost, and the abuse vector above makes
an unlimited free tier untenable. But this feature was justified as an *activation* lever
for free users, and paywalling it removes it from exactly the funnel stage it was meant to
fix. Resolution: keep a small free generation allowance per account (enough for a first
survey, which is the activation event), and sell volume plus the higher-quality/multilingual
path in Pro. Shares model plumbing with [AI analytics](feature-ai-analytics.md) (#92) —
build the infrastructure once. See [epics/pro-tier.md](epics/pro-tier.md).
