# Survey name is silently truncated at 45 characters

**Type**: bug
**Priority**: high
**Area**: backend
**Created**: 2026-08-17

## Description

`SurveyHeader.name` is `varchar(45)`. Anything longer is cut off with no warning — neither
the manual create form nor the AI-draft brief form surfaces the limit, and the AI
materialize path (`header_overrides_from_form`) passes the form value straight through.

Observed in production 2026-08-17: the first real AI-draft user (user 371) titled their
survey with their research question and got a survey publicly named

> **"To what extent does the presence of Gatwick A"**

— cut mid-word. The name is what respondents see at the top of every section and in the
shared link preview. The user published without noticing; a student sharing this with
survey respondents (or a consultant with a client) looks careless through no fault of
their own.

## Why it matters

- The AI-draft flow actively invites long names: the brief form asks for a project
  description, and research-question-shaped titles ("To what extent does…") are the natural
  input for the academic segment.
- Silent data loss on the single most visible field of the product.

## Fix options (not exclusive)

1. `maxlength="45"` + live counter on both create forms — honest, zero migration.
2. Widen the column (Django default for such fields elsewhere in the codebase is 100–250);
   45 chars is an inherited constraint nobody defends.
3. For the AI path specifically: let the generator produce a short display name from the
   brief instead of reusing the raw brief name verbatim.

Option 2 + 1 together is the likely end state; check template/CSS truncation behaviour on
long names before widening.
