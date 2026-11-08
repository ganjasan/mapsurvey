## Why

Owner review of the canvas builder (2026-11-08, epic #348, #594): an empty Image block said "Upload a
picture in the settings on the right", and the file field in the panel was clipped. The owner set a
rule for every block editor: **a block's primary actions happen inside the block; only secondary
options live in Settings.**

## What Changes

- Every block kind gets its primary controls on the canvas, shown in the block (empty state, or when the
  block is selected):
  - **Image** — drop zone / *Choose a picture* in the block; *Replace picture* over a set picture.
    Settings: description for screen readers.
  - **Video** — the YouTube/Vimeo link field in the block. Settings: nothing but the caption stays on the canvas.
  - **Button** — label on the canvas (as before) and the link field under the button. Settings: style.
  - **Documents** — the file list in the block: titles edited in place, × to remove, a drop zone to add.
  - **Map** — GeoJSON drop zone in the block; *Replace area* over a set map. Settings: colour, base map.
  - **FAQ** — questions and answers edited in the block, rows added and removed there.
  - **Timeline** — phases (when, title, text) edited in the block, *Now* toggled on the phase, rows added and removed there.
  - **Survey card** — the survey picked in the block while empty. Settings: change the survey.
  - **Results** — the question picked in the block while empty. Settings: chart style, base map, change the question.
  - **Event** — date, start, end and place in the block. Settings: time zone, seats, registration switch, attendees.
- No placeholder ever says "…in the settings on the right".
- The panel's file input no longer clips (the `form-control-sm` height).
- Server, data and the public page are unchanged: the canvas controls feed the same panel form, which
  stays the one serialisation of a block.

## Capabilities

### Modified Capabilities
- `survey-landings`: the builder requirement states the rule and the per-kind split.

## Impact

`survey/templates/landings/editor/_canvas_block.html`, new `landings/editor/_inline.html`,
`_block_form.html` (primary fields become hidden carriers), `js/landing_builder.js` (inline inputs,
drop zones, rows), `css/landing_builder.css`, tests, help, translations.
