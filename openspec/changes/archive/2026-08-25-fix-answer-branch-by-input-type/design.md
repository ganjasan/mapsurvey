# Design

## D1. `input_type` is the only dispatcher

`input_type` is the single field that defines what a question collects; `choices` is
configuration for some types. Every arm of the storage code (top-level and sub-question) now
selects on `input_type` alone, so no data shape in `choices` can reroute a payload into the wrong
parser. Per-type behavior is preserved exactly, with two deliberate changes:

- `datetime` (both levels) stores its raw `datetime-local` string in `answer.text` — the format
  prepopulation already reads back. Previously the value was dropped and an empty row saved.
- `range` gains the same empty-value guard `number` already had (`float('')` could 500).

## D2. Three layers, because each fails differently

1. **Dispatch fix** — makes poisoned rows harmless immediately, including rows this deploy
   doesn't know about (future imports, manual DB edits).
2. **Editor + import normalization** — stops new poisoned rows at both write paths. The editor
   clears `choices` for non-choice types even when `choices_json` was posted, because the
   choices widget keeps its hidden field populated across a type switch (that is the poisoning
   mechanism observed in production).
3. **Data migration** — repairs the 10 existing rows so exports, previews and any future code
   that reads `choices` see clean data, not a live trap.

## D3. `CHOICE_TYPES` lives in `question_types.py`

The set `('choice', 'multichoice', 'range', 'rating', 'ranking')` existed only as an inline
tuple in one editor branch. It now sits next to `GEO_TYPES`/`DISPLAY_BLOCK_TYPES` and is imported
by the editor, the import path and the migration, so the three layers cannot drift apart.
`ranking` is included (its items are the choices list); the import-time "requires choices"
validation set is narrower on purpose and unchanged.

## D4. Migration is a plain UPDATE, no reverse

`0060` filters `input_type NOT IN CHOICE_TYPES, choices IS NOT NULL` and sets `choices = None`.
Reverse is a no-op: the cleared lists are garbage by definition of the bug. Runs in pre-deploy
like every other migration; the commit carries no schema change, so the two-deploy trap from
[[lesson-render-predeploy-no-shell]] does not apply.
