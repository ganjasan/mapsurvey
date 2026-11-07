## Context

`controls.form_values` turned a settings document into flat form values and `clean_settings` turned
them back. Both assumed every key was always set, which holds for Paper A/B and nothing else.

## Decisions

- **Missing = base, explicit = override.** `form_values` renders '' / `base` / 17 / 15 for keys the
  document lacks; `clean_settings` writes a key only when a control leaves its base state. A removal
  is written only as `False`; a missing removal means "keep". Round-trip invariants tested: `{}` →
  `{}`, Paper A and Paper B → themselves.
- **Label halo travels with label colours.** The halo is written only when a label colour is set, so
  a Streets copy keeps Streets' halos.
- **Custom roads** rather than snapping an unknown triple to Medium: snapping silently restyled Paper B.
- **Native colour picker** overlaid on the code: no library, keyboard and mobile pickers for free.
- **Search reuses the shared control** via an adapter (`getCenter`, `fitBounds` with Leaflet's
  `[[s, w], [n, e]]`, `flyTo([lat, lng], zoom)`), so the editor gets the Mapbox + OSM fallback, the
  debounce and the cache without a second implementation. Print follows the searched place; picking
  a survey frame clears it.

## Risks

- Styles saved before this change with Paper-A-like defaults keep them; they are explicit now and
  show as overrides. Re-saving does not undo it; the owner can press ↺ per colour.
