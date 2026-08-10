# Inline Editing: geo answers (redraw polygon/point/line)

**Type**: feature
**Priority**: low
**Area**: frontend
**Epic**: data-management
**Created**: 2026-04-05

## Description

The data-management epic shipped inline editing for text, choice and number answers. Geometry
was deliberately left out: a reviewer who spots a polygon drawn in the wrong place, a point
dropped in the sea, or a line traced along the wrong street can flag the session but cannot
correct the shape.

This item is the geometry half — open the answer's geometry on a map in the analytics panel,
redraw or drag it, and save, with the same audit trail and permissions the text-level inline
editing already uses.

## Current behaviour

Geometry is refused on purpose, in two places:

- `survey/analytics.py:701` — the `editable` flag excludes `point`, `line` and `polygon`.
- `survey/analytics_views.py:314-339` — `analytics_answer_edit` returns 400 for those types.

## Scope

- Redraw / drag a stored geometry from the attribute table or the map panel.
- Reuse the respondent-side Leaflet draw widgets rather than building a second editor.
- Write an `AuditLog` entry per edit, as the basic inline editing does.
- Respect validation status: editing a trashed or `not_approved` session should behave the same
  way it does for text answers.

## Notes

- Filed as part of the data-management epic on 2026-04-05. This file was reconstructed on
  2026-08-10: the index carried a row for the item but the file had never been committed.
- Related: [Audit Trail (edit history log)](feature-audit-trail.md).
