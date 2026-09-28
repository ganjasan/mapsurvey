## Context

Two UIs edit an answer inline: the session detail rows (`row.editable`, already type-gated) and the
legacy Responses table (`startCellEdit`, not gated). Both POST to `analytics_answer_edit`.

## Decisions

- **Gate on type first, in the view.** The endpoint is the boundary; the UI gate is convenience. A
  400 before any query means no stray empty rows and no dependence on how many rows exist.
- **One list.** The detail rows and the view disagreed (`thumbs`); the table had no list at all.
  `EDITABLE_ANSWER_TYPES` is the single source.
- **Tolerate duplicates for editable types** with `order_by('id').first()` rather than
  `get_or_create`: production has none today, but an edit must never 500 on data shape.

## Non-Goals

- Editing geo/file answers inline, or locking the section POST against concurrent submits (no
  evidence of the race in production data).
