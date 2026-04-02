# Repeatable question groups

**Type**: feature
**Priority**: low
**Area**: backend
**Created**: 2026-04-02

## Description

Allow a group of questions to be answered multiple times within a single survey session. For example, in narrative mapping, an interviewer records multiple stories — each with a map point, title, text, and category. Currently, each question maps to one answer per session. This feature enables one-to-many answer sets per question group.

## Notes

- See [UC-05: Narrative Mapping Interview](../docs/use-cases/uc05-narrative-mapping.md)
- Data model impact: needs a grouping mechanism for Answer records (e.g., `answer_group_index`)
- UI: "Add another" button to repeat the group
- Export: each repetition becomes a separate row in CSV / separate feature in GeoJSON
- Prerequisite for narrative mapping feature
