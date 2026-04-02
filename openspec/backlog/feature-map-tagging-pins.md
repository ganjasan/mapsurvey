# Map tagging with categorized pins

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-02

## Description

Allow respondents to place multiple categorized pins on a map within a single question. Each pin has a color-coded category (e.g., "Love this place", "Needs improvement", "Safety concern") and an optional text comment. Enables digital community asset mapping workshops where residents mark places on a shared map with qualitative tags.

## Notes

- See [UC-02: Community Asset Mapping Workshop](../docs/use-cases/uc02-community-asset-mapping.md)
- Extends current point question type: multi-point + category + per-pin comment
- Categories defined by survey creator with custom colors/icons
- Optional max pins per category to prevent flooding
- Export as GeoJSON with category and comment as feature properties
