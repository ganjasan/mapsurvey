## Context

The attribute table's `get_table_page()` already computes a `cell_map = {session_id: {question_id: formatted_value}}` and `session_issues` for session-level flags. Answer linting adds a parallel `lint_map = {session_id: {question_id: ['error_type']}}` that the template uses to decorate individual cells.

PostGIS/GEOS provides `GEOSGeometry.valid` (bool) and `GEOSGeometry.valid_reason` (string) for geometry validation. Django exposes this via `answer.polygon.valid`.

## Goals / Non-Goals

**Goals:**
- Self-intersection detection for polygon answers
- Empty required detection per-answer-cell (required question, session visited the section, no answer)
- Error icon + cell highlight in table
- `has_errors` in issues filter

**Non-Goals:**
- Geo bbox validation (deferred to #51)
- Warning-level lints (deferred to #50)
- Line/point specific rules

## Decisions

### 1. `compute_answer_lints()` returns `{session_id: {str(question_id): [error_types]}}`

Parallel structure to `cell_map`. Template checks `lint_map[session_id][col.key]` when rendering each cell.

### 2. Self-intersection check requires loading geometry objects

`Answer.polygon.valid` requires the actual GEOS geometry. We already load answers in `get_table_page()` via `answer_qs`. We can check `.valid` during the cell_map pivot loop — no extra query needed.

### 3. Empty required reuses logic from `compute_session_issues()`

The visited-sections and required-questions computation from #43 can be reused. Instead of flagging sessions, we flag individual `(session_id, question_id)` pairs.

### 4. `has_errors` filter integrates with existing issues_filter mechanism

Add `has_errors` as a new option. When active, filter rows to those where `lint_map[session_id]` has at least one entry.
