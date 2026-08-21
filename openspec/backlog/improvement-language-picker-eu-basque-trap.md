# Language picker: `eu` (Basque) reads as "EU / European" and gets picked by mistake

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-17

## Description

In the survey-content language picker (75 languages), Basque's ISO code `eu` reads as
"EU = European Union / European English". Observed in production 2026-08-17: the first real
AI-draft user (user 371, a UK student surveying Horley residents about Gatwick Airport)
selected `en` + `eu` and published a British neighbourhood-safety survey fully translated
into **Basque** ("Horleyn bizitzea", "Segurtasun Mapa"). Nothing in the flow made the
mistake visible; the user almost certainly has not noticed.

On the AI path the mistake also costs real money and latency: the second language nearly
doubled output tokens (1817 → 3180) and generation time (11.8 s → 20.5 s) for a translation
nobody will read.

## Why it matters

- Every extra language multiplies the respondent-facing surface where the error shows.
- `eu` is a uniquely bad case (collides with the continent's abbreviation), but the general
  failure — codes shown more prominently than names, or names alone without a native-name
  hint — affects other pairs too (`sv` Swedish vs "SV", `id` Indonesian vs "ID").

## Fix sketch

- Show language names with native names ("Basque — euskara"), never the bare code as the
  primary label; if codes are displayed, keep them visually secondary.
- On the AI brief form, after generation, or on publish: surface a one-line summary
  "This survey will be offered in: English, Basque (euskara)" — the word "Basque" alone
  would have stopped this user.
- Optionally sort/group by likelihood (UI language, browser locale, previously used) so a
  UK creator is not scanning an alphabet-ordered ISO list where `eu` sits temptingly early.
