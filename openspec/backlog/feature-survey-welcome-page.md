# Survey welcome page — a real first screen, not a fake question

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-08-23

## Description

A first-class intro screen shown before the first section: title, cover image, a paragraph
of instructions, who is running the survey and why, how long it takes, and one Start
button. Today the only way to get one is what we did for Olney on 2026-08-23 — a Formatted
Text block faked into the first section, with the map sitting uselessly beside it and a
"question" that asks nothing.

A field campaign needs this more than an opinion survey does: a volunteer opening the link
on count morning must learn the procedure ("tap the animal, then tap the map, repeat")
before they see a map, and the organiser needs somewhere to put the thank-you, the contact
and the safety note.

## Notes

- The map should be absent or decorative here — the welcome screen is the one place in a
  map survey where the map is not the point.
- Overlaps with the existing thanks page (`thanks_html`, its own editor panel): welcome is
  its mirror at the other end, so reuse that editor and its sanitisation rather than
  inventing a second rich-text path.
- Must be optional and off by default — an extra click before a one-question survey is a
  drop-off, not a feature.
- Related: map-less sections (#145) — a welcome page is the degenerate case of one.
- Epic: field-data-collection (FD-15)
