## 1. Picker

- [x] 1.1 `attach()`: one trigger button, hidden value input, `setValue()` as the single write path
- [x] 1.2 Panel: search + Remove icon, chips, "Use <value>" row, "No icon" first cell while browsing; Enter applies a typed value and never submits
- [x] 1.3 `place()`: fixed placement below/above/roomier side with max-height, horizontal clamp, re-run after grid render, on resize and capturing scroll; cleared under 768px
- [x] 1.4 CSS in `editor_base.html`: trigger, 560×520 panel, 48px cells, remove/use styles, bottom sheet under 768px

## 2. Editor

- [x] 2.1 Modal strings (Choose an icon, Remove icon, No icon, Use); Icon column narrowed to the button; the row input is a bare value carrier

## 3. Verify

- [x] 3.1 Targeted tests (icon grid, write-in, catalog) green
- [x] 3.2 Browser: one control per row; panel 560×520 placed without covering its button at three scroll positions; remove / no icon / use-typed set the value; bottom sheet at 390px
- [x] 3.3 One full `./run_tests.sh survey` run (Ran 2677, OK)
- [x] 3.4 `openspec validate icon-picker-one-button --strict`
