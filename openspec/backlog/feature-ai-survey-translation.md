# AI translation of survey content

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: pro-tier
**Tier**: **Pro** (real marginal cost)
**Created**: 2026-08-31

## Description

The translation interface exists; every second language is typed by hand. Maptionnaire
ships "AI translations" in every tier and lists "AI-powered translation for 50+ languages"
in its structured data. For a German consultancy that must offer the survey in German and
English (or a Swiss one in three languages) hand-translation is the cost that makes them
skip the second language, and a monolingual survey is the one that under-collects.

## Scope Sketch

- "Translate from <primary>" action on a survey language: fills every untranslated field
  (question names, subtexts, choices, section headings, thanks page) through the existing
  AI provider (Gemini, see memory `project_ai_provider_gemini`), marks them as
  machine-translated until a human edits them.
- Rich-text fields go through `coerce_creator_html` on the way back in — same rule as
  every other writer of `subtext`/`subheading`.
- Per-workspace usage accounting (same meter `#92` needs).
- Never overwrite a human translation without an explicit "retranslate".

## Notes

Cheap to build on top of `ai-survey-generator`; the expensive part is the edit-state UX.
