# AI brief: "incident reporting / watch map" use case

**Type**: feature
**Priority**: medium
**Area**: backend
**Created**: 2026-08-25

## Description

Add an "incident reporting" use case to the AI generation brief (and a matching draft shape):
one map-centric section with a required geo question plus attribute sub-questions (incident
type, date/time, details, optional photo), and **no** opinion/sentiment sections. Today every
draft comes out in an engagement frame — feelings rating, "what would improve safety"
multichoice, free-text wishes — regardless of the goal.

## Notes

Grounded in the Fallonmaps case (2026-08-25, user 390 — Aubin Dorion, geospatial division
manager at Cabin Resource Management): she ran the generator twice with goals "Suspicious
Activity" and "Crime Watch", and both times deleted 2 of the AI's 3 sections within minutes,
keeping only the map. A professional GIS user wanted an incident-submission form, not a survey
of opinions. Her first attempt at reshaping the draft (repurposing a multichoice into a point
question) is also what triggered the stale-choices 500 (fixed in PR #114) — a purpose-built
template would have avoided the whole path. Details in
`docs/marketing/user-outreach/fallonmaps/profile.md`.

Related segment signal: neighbourhood-watch / watch-map is a recurring self-serve shape
(community observation maps); pairs with epic community-engagement, and the taxonomy she wrote
herself (Suspicious Person / Vehicle Break-In / Property Theft / Drug Use / Other) is a good
seed for the template's default choices.
