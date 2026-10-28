## Why

On a phone the respondent panel covers 88 % of the map. Opening another respondent's mark
(or a creator's object) from the list flies the map to it and opens the popup — behind the
panel. The draw flow already slides the panel away; the objects flow did not (found in the
mobile layout pass on 2026-09-05, after #156/#157 shipped).

## What Changes

- Opening an object from the list on a mobile viewport hides the panel (same `toggleInfo`
  the draw flow uses) and shows it again when the popup closes.

- The layers control with a legend auto-expands on desktop only; on a phone it overlapped the
  popup.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `layer-objects-question`: the "Opening an object uses the map popup" requirement gains the
  mobile rule (delta written against the `overlay-features` text; archive that first).

## Impact

`survey/templates/partials/layer_objects_block.html` only; browser-verified at 390×844.
