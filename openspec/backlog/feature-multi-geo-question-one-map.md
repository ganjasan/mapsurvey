# Several geo questions on one map, each with its own colour and icon

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-08-26

## Description

PARTIMAP's drawing slide offers three labelled buttons over a single map — "I like this
place" (green pin), "I don't like this place" (red pin), "my favourite walking route" (a
line) — and everything the respondent places lands in one "Your features" list, colour-coded
by which question it answered
([screenshot](../../docs/marketing/competitors/partimap/10-draw-with-bounds.jpg)).

Two things we do not have: several geo questions sharing one map surface, and per-question
styling of what the respondent draws.

## Why it matters

Like/dislike mapping is the single most common participatory format there is, and today it
costs a respondent two separate map sections with the map re-centring in between. The
comparison is lost — the whole point is seeing your likes and dislikes on the same picture.

Per-question styling matters on its own: at export and on any results map, "which question
did this point answer" is currently only recoverable from the file it landed in.

## What it needs

- A section layout where several geo questions bind to one map instance, and a mode selector
  choosing which one the next placement answers.
- Style on the question: colour, and an icon for point questions.
- A combined "your features" list per section, grouped or coloured by question, each row
  editable and deletable — we have per-question equivalents already.
- The mode selector has to coexist with tap-to-place on mobile without stealing the tap. The
  respondent flow is deliberately still the legacy panel/crosshair layout (CLAUDE.md); a
  bottom sheet was built, reviewed and removed in 2026-08. This needs an approved respondent
  mockup, not a fresh improvisation.
- Colour must survive into export and into any map rendering of results, otherwise it is
  decoration.

## Notes

- Adjacent to but not the same as
  [#103](improvement-multi-geometry-discoverability.md) — that item is about one geo question
  already accepting many features and nobody knowing it. This is many *questions* on one map.
  Worth solving the discoverability wording once, for both.
- Epic: community-engagement
