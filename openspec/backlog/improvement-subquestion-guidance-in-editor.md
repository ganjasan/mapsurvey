# Editor guidance: attributes of a mapped object belong in sub-questions

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-25

## Description

The editor gives no hint that attributes of a mapped feature (type, date/time, comment, photo)
must be **sub-questions of the geo question** to attach to the point/line/polygon — a top-level
question next to a geo question collects one answer per respondent, not per feature, and never
reaches the GeoJSON properties/export. Add contextual guidance: e.g. when a section already has
a geo question and the creator adds a top-level datetime/text/choice question, suggest "Should
this describe the mapped location? Add it as a sub-question of <geo question> instead", plus a
line in the geo question's card explaining what sub-questions are for.

## Notes

Grounded in the Fallonmaps case (2026-08-25): a professional GIS user built her first survey
with Date/Time, Description and photo as top-level questions beside the point question — the
attributes would never have attached to her observations, and nothing told her. She discovered
the sub-question model only on her second survey, by editing the AI draft's map question
instead of building her own. The AI drafts already model this correctly (geo question with
attribute sub-questions), which is currently the only place a creator can learn the pattern.
See `docs/marketing/user-outreach/fallonmaps/profile.md` and memory
[[architecture-subquestions-geojson]].

Related: **#61 Sub-question Discoverability Testing** (2026-04-14) asks *whether* creators find
the feature at all — only 4 of ~50 active users had ever used it. This item is the concrete
intervention for the same gap, and Fallonmaps is fresh evidence that the answer to #61 is "no":
a 21-year GIS professional missed it on her first survey. Doing this may make #61's test
unnecessary — measure adoption after shipping instead.
