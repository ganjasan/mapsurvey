# Share flow dead-ends: published-but-private surveys with no respondent path

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-17

## Description

Observed with the first real AI-draft user (user 371, 2026-08-17): both of their published
surveys (457, 459) ended the session as `status = published`, `visibility = private`, with
zero external responses. The user visited `/editor/surveys/<uuid>/share/` three times,
produced 4 dead clicks there (on the UTM fields), and left. The only recorded sessions are
their own preview runs.

The observable outcome: a motivated creator — who generated, reviewed, self-tested and
published two surveys in 29 minutes — never got a link into a respondent's hands. Whether
the blocker was visibility semantics ("published" vs "private" is not an obvious pair), the
share page's information layout (UTM builder is prominent; the actual respondent URL and
"who can open this" state less so), or simply session end, the share page is where the
funnel stopped.

## Why it matters

- The service-model hypothesis (2026-07-23) already flagged response-collection as the
  bottleneck: every profiled lead builds and publishes but gets ~0 external responses. This
  session is the same pattern reproduced end-to-end under telemetry.
- The AI draft path compresses build time to minutes, which makes the share step the first
  real wall a new user hits — and the wall is currently silent.

## Fix sketch

- On the share page, lead with the respondent link and an explicit state line: "Anyone with
  this link can respond" / "Only collaborators can open this — your survey is private";
  move the UTM builder below.
- If `visibility = private` blocks respondents in practice, say so at publish time, not
  implicitly.
- Instrument the share page (link copied, QR downloaded) so "published but never shared"
  becomes a measurable funnel stage instead of a forensic reconstruction.

## Open question

First verify what `visibility = private` + `status = published` actually means for a
respondent following the link — whether this is a UX-comprehension issue or a real
access dead-end determines the fix.
