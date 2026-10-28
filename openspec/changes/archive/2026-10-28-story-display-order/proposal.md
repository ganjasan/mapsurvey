## Why

The owner wants to choose which customer stories lead the landing carousel and /stories/
(2026-10-01: Olney, Whitehouse, Remington first), not leave it to publication dates.

## What Changes

- `Story.position` (nullable small integer, migration 0089), editable in the admin list.
- One ordering everywhere stories are listed: `Story.in_showcase_order()` — position ascending,
  stories without a position after them, newest first. The admin list uses it too.
- `seed_story` never touches `position`, so a re-seed keeps the admin's order.

## Impact

`survey/models.py`, migration, `survey/views.py` (landing, stories index), `survey/admin.py`, tests.
