## Why

The Publish-space UX audit (P5) and a user report surfaced a conceptual bug in map-block "Geo popup fields". The control offers **all top-level survey questions** and, at render time, fills each point's popup with that respondent's **session-level** answers to the selected questions. Two things are wrong for geospatial data:

1. **Wrong list.** A geo question's real per-point attributes live in its **sub-questions** (`parent_question` / `parent_answer`) — "mark a spot" → "what did you do here?". Those are excluded from the picker (`parent_question_id__isnull=True`), while unrelated form questions are offered instead. Creators see a flat list of every question and can't tell how it relates to the point.
2. **Wrong join.** Popups are filled per *session*, not per *point*: if a respondent marks three points and answers a form question once, all three popups show the same value. Each point should show the attributes the respondent entered *for that point*.

## What Changes

- The "Geo popup fields" picker for a map block SHALL list the **sub-questions of that block's geo question** (excluding free-text), not all top-level questions.
- Point popups SHALL be built **per point** from each geo answer's own sub-answers (`parent_answer`), so different points from the same respondent show their own attributes.
- Free-text sub-answers remain excluded (never published); a geo question with no sub-questions shows an honest empty state ("anonymous geometry only").
- `geo_label_fields` keeps storing question codes (now sub-question codes) — no schema change. Previously-stored top-level codes become inert (no matching sub-answers), degrading gracefully.

## Capabilities

### Modified Capabilities
- `public-results-page`: the anonymous-geo popup model changes from session-join of top-level questions to per-point sub-answers. Privacy guarantees are unchanged or stronger (still creator-opt-in per field, still no free text, still no record identifiers; values are now genuinely the point's own attributes).

## Impact

- `survey/public_results.py`: `_map_payload` builds properties per point from sub-answers; `_collect_label_values` replaced by a per-point sub-answer collector.
- `survey/public_results_editor.py`: config context gains `geo_subquestions` for the selected map block.
- `survey/templates/editor/public_results.html`: geo-popup-fields section iterates sub-questions with an empty state.
- Tests reworked (per-point popup; two points/one session show distinct values) + the anonymity test retained. No migration.
