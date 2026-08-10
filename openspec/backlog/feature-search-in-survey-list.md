# Search in survey list

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-25

## Description

Add a search input on the editor dashboard (`/editor/`) and the public survey list (`/surveys/`) that filters surveys by name (and optionally status / language). Becomes important once a user has more than ~5 surveys — currently they must scroll the full list.

## Notes

- Editor dashboard need: power users like Galanthus (multiple "Galanthus locations" versions), bisqunours (several "L'accès aux transports" versions), lrbenedict12 (Power Paper March/April), and admin (lots of `demo_city_feedback` versions) already have crowded lists from versioning.
- Public `/surveys/` list grows unboundedly across all users — search there is more pressing as the platform scales.
- Implementation: HTMX-driven server-side filter (matches the existing editor stack); client-side substring filter is acceptable for v1 if list size is small.
- Filter scope to consider: name, status (draft/testing/published/closed/archived), and "owned by me" vs "all".
- **2026-08-10 — partially shipped.** The editor dashboard has a search box (`survey/templates/editor.html:213-215,478-505`). The public `/surveys/` list still has none — `survey/views.py:544` returns an unfiltered queryset. That is what is left.
