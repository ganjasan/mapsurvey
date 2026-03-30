# Pinned point disappears in subsequent survey sections

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-03-26

## Description

After a respondent marks a point on the map in one section, the pin is not visible on the map in subsequent sections. The user loses visual context of where they placed their marker while answering follow-up questions about that location.

## Notes

- Source: Marijana Jericevic (Galanthus) — "when the user marks the spot, the point is not visible on the map when you continue with answering questions"
- Her survey flow: section 1 = place a point, sections 2-5 = answer questions about that point
- Related to existing `existing_geo_answers_json` mechanism — may need to pass previous section's geo answers forward
- Reported 2026-03-26
