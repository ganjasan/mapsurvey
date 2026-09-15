# Empty sessions clutter Responses — hide them and delete them in bulk

**Type**: improvement
**Priority**: high
**Area**: frontend
**Created**: 2026-08-27
**Epic**: survey-analytics
**Related**: [`SurveySession.end_datetime` is never written](bug-session-end-datetime-never-set.md) (#105),
[AI-assisted response triage](feature-ai-response-triage.md) (#95)

## Description

A survey shared into a social feed accumulates far more opened-and-abandoned sessions than
answered ones, and the Responses table shows them all as equal rows. The only remedy today is
deleting the empty rows one by one, by hand.

**Source — Fallonmaps / Aubin Dorion (user 390), 2026-08-26.** Her Crime Watch survey
circulates in a neighbourhood Facebook group; FB's in-app browser opens a session on every tap.
Of 108 sessions, only 18 ever contained an answer. On 2026-08-26 16:17–16:18 UTC she deleted
**63 sessions in two minutes** (Render/PostHog session 16:14–16:22, 217 events in 8 minutes) —
manual data hygiene she has repeated across days. She never reported it as a problem —
[[lesson-authors-workaround-silently]] again: the workaround is just "grind through the delete
buttons".

This is not specific to her: any survey distributed through a social channel produces the same
open-without-answering flood, and every such creator faces the same choice between a cluttered
table and a deletion grind.

## Proposal

- A "hide sessions without answers" filter on the Responses table (likely a sensible default,
  with the count of hidden rows shown so nothing is silently invisible).
- Bulk selection + bulk soft-delete, at minimum a one-click "delete all empty sessions"
  scoped to the current filter. Soft-delete only (`is_deleted`), same semantics as the existing
  per-row delete in `survey/analytics.py`, so the trash/restore flow keeps working.
- "Empty" = no `Answer` rows for the session. Sessions with partial answers are NOT empty and
  must never be swept by the bulk action.

## Notes

- Aggregates already exclude nothing here — empty sessions have no answers to aggregate — but
  they DO inflate session counts on the analytics funnel and the demo-open numbers
  ([[lesson-demo-opens-inflated-by-bots]] is the same phenomenon at the top of our own funnel).
- Pairs with #105: once `end_datetime` exists, "abandoned" becomes distinguishable from
  "in progress", and the filter can get smarter than answer-count.
