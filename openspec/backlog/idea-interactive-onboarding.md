# Interactive onboarding (guided first-survey wizard)

**Type**: idea
**Priority**: high
**Area**: frontend
**Epic**: growth
**Created**: 2026-06-10
**Related**: [AI survey-creator agent](idea-ai-survey-creator-chat-agent.md), [Survey template gallery](feature-survey-template-gallery.md), [Funnel monitoring](feature-funnel-monitoring.md)

## Description

A guided, in-product onboarding flow that walks a brand-new registrant from empty account to a published, shareable survey — instead of dropping them into a blank editor. Step-by-step: pick a goal → seed first section/question (from template or AI) → add a geo question → preview → publish → get the share link/QR. Inline tooltips and a visible checklist ("Add your first question", "Publish", "Share").

## Evidence (2026-06-10 activation analysis)

Of 222 real registrations: only **53% create any survey, 38% add a question, 33% get a response**. The leak is concentrated at the very top (register → first survey → first question). A second leak: **74 collected responses but only 42 formally "published"** — people don't know to publish/share. Onboarding targets both: getting to a first built question, and driving the draft→publish→share step.

## Why this may beat a static template gallery

- A gallery still drops the user into a blank-ish editor after cloning; onboarding holds their hand through the whole first loop, including publish + share (the second leak the gallery ignores).
- Onboarding is the natural *wrapper* for the AI agent and the template gallery — it's where both are offered ("Describe your survey to AI" vs "Start from a template" vs "Start blank").

## Relationship to the other activation items (not competitors)

This is the middle layer of a 3-part activation stack — see the [growth epic](epics/growth.md) "Activation stack" section:

1. **Template gallery** — seed library + deterministic fallback.
2. **Interactive onboarding** (this) — the guided wrapper that gets people in and drives publish/share.
3. **[AI survey-creator agent](idea-ai-survey-creator-chat-agent.md)** — the highest-ceiling core; produces a personalized draft.

## Scope

- First-run flow triggered on first login / first empty editor visit.
- Goal picker → branch to AI agent / template / blank.
- Checklist widget persistent until first publish.
- Explicit publish + share step (link + QR — ties to [QR poster generator](feature-qr-code-poster-generator.md)).
- Skippable for power users.

## Notes

- We cannot yet prove onboarding > template > blank on conversion — that needs [funnel monitoring](feature-funnel-monitoring.md) first. Ship instrumentation, then measure each layer's lift.
- Lower build risk/cost than the AI agent; good measured baseline to launch before/with the AI flagship.
