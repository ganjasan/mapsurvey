## Why

On the dev stand the owner pressed "Add a cover picture" on the page head and nothing happened: the button only selected the page, whose settings were already open, and the file input sat in the panel. By the rule adopted in `landing-inline-editing` the cover is the page head's primary action and belongs on the canvas.

## What Changes

- "Add / Change the cover picture" on the page head opens the file chooser and saves at once; a picture dropped on the head does the same; a × beside it removes the cover.
- The page panel keeps the cover's description only; its file input is a hidden carrier.

## Capabilities

### Modified Capabilities
- `survey-landings`: the cover picture joins the primary actions done on the canvas.

## Impact

`landings/editor/_hero.html`, `_page_panel.html`, `js/landing_builder.js`, `css/landing_builder.css`, one test, one creator string.
