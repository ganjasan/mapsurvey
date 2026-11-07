## Why

The style editor's *Print* tab showed the frame in colour, with greyscale behind an "As a photocopy"
toggle. The owner pointed out (2026-11-07) that a paper form is printed in black and white or
photocopied, which is also what every contrast warning in the editor measures. The tab should show
that by default.

## What Changes

- The *Print* frame starts greyscale (the same luminance the contrast warnings use).
- The toggle becomes "In colour", unchecked, for a creator who prints on a colour printer.

## Capabilities

### New Capabilities

### Modified Capabilities
- `map-style-editor`: the print tab defaults to black and white.

## Impact

`org/map_style_editor.html`, `js/map_style_editor.js`, ten creator catalogs, one test. The printed
PDF itself is unchanged: it still carries the colour frame, and the printer decides.
