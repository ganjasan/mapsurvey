# "Place at my location" — GPS button for geo questions

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-23

## Description

Next to the draw button, a one-tap action that drops the feature at the device's current
position instead of requiring the respondent to find and tap the exact spot on the map.

For a field collector standing at the thing they are recording, tapping the map is the
slower and less accurate path — they must locate themselves first, then aim. Geolocation is
already wired for centring the map; this reuses it as an input.

## Notes

- Show accuracy before committing ("±8 m — use this?") and let the respondent nudge the
  point afterwards; a blind drop with 300 m accuracy is worse than a tap.
- Pairs with GPS metadata (FD-9): if we place from GPS we should store what the GPS said.
- Epic: field-data-collection (FD-5)
