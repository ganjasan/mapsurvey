## Why

Clicking a tile in the block library of the report (and Sites) builder spun the whole tile icon:
the busy state of a submit button swaps its leading `<i>` for a spinner, and a tile's leading
`<i>` is a 36-px tinted square. The square turning round reads as a glitch, and the top progress
bar already says the page is working.

## What Changes

- New opt-out `data-no-spinner` (on a button or an ancestor) in `loading_feedback.js`: the button
  still gets the busy state (disabled next tick, `aria-busy`, `is-busy`, no second submit), but
  its icon is not swapped and no spinner is prepended.
- Both block libraries (`sites/editor/_library.html`, `reports/editor/_library.html`) carry it;
  the clicked tile keeps its hover highlight with a `progress` cursor (`.lb-tile.is-busy`).

## Impact

- `survey/assets/js/loading_feedback.js`, `survey/assets/css/site_builder.css`, the two library
  templates, `survey/tests/test_creator_loading_feedback.py`.
