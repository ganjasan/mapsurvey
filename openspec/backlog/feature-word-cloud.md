# Word cloud for open-text answers

**Type**: feature
**Priority**: low
**Area**: frontend
**Epic**: survey-analytics
**Created**: 2026-08-31

## Description

The cheapest visible "analysis" of free text, and one every comparison table has a row
for (Maptionnaire: all tiers, with a stop-word exclusion list). It is not insight — `#92`
is — but it is a demo moment and a slide in every planner's council presentation.

## Scope Sketch

- Chart type `wordcloud` for `text` / `text_line` questions in the Charts panel, driven by
  the same filter/selection as every other chart.
- Server-side tokenising with per-language stop-word lists for the survey's languages;
  creator can add exclusions per question.
- Reusable as a public-results block, subject to k-anonymity: never show a token that
  appears in fewer than K sessions (a rare word can identify a respondent).
