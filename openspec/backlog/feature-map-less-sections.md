# Sections without a map — classic form layout

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-08-23

## Description

A section can declare that it has no map, and then renders as an ordinary web form —
questions stacked full-width down the page, Google Forms style — instead of the panel
beside a map that every section uses today.

Real surveys are mixed: the mapping part is the heart, but around it sit demographics,
consent, contact details, "how did you hear about us", free-text feedback. Rendering those
in a narrow side panel next to an irrelevant map wastes the screen, confuses respondents
(the map invites interaction that does nothing), and makes us look like a tool that can
only do one thing.

Olney's own survey has two such sections in disguise: the intro (area choice) and the
closing route-conditions question, both currently squeezed into the map layout.

## Notes

- Implementation shape: a flag on SurveySection; the respondent template picks a layout,
  the section panel becomes the page body at full width.
- Geo questions in a map-less section must be prevented in the editor rather than failing
  at render — the type picker already knows how to hide types by context.
- Mobile is where the win is largest: the map currently eats half the viewport even when
  no question needs it.
- Enables the welcome page (#144) and a proper closing/feedback section, and matters beyond
  this epic — it is the difference between "map survey tool" and "survey tool with maps".
- Epic: field-data-collection (FD-16)
