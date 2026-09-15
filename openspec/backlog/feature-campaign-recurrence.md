# Campaign recurrence — run the same survey again next season

**Type**: feature
**Priority**: medium
**Area**: backend
**Created**: 2026-08-23

## Description

One action that starts a new round of an existing campaign (new version, same structure,
same zones, same volunteer links where wanted) and keeps the previous rounds queryable
side by side for trend comparison.

Recurring counts are the shape of this market: Olney has 47 annual rounds and its headline
metric is a year-over-year ratio; Audubon-style counts, seasonal inspections and school
travel surveys all repeat. Versioning and cross-version analytics exist but are framed
around "I edited a published survey", not "it is October again".

## Notes

- Needs a round/season dimension in analytics filters, not just version numbers.
- Multi-year charting can stay out of scope at first — export + their spreadsheet is
  acceptable, as it is what they do today.
- Epic: field-data-collection (FD-6)
