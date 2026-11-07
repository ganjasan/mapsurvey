## 1. Controls

- [x] 1.1 `controls.py`: base states (empty colours, roads `base`, place names 17 = no limit, buildings minzoom 15), removals written only as `False`, halo only with label colours, Custom roads kept
- [x] 1.2 `generator.py`: drop place-dot icons only when label colours are set

## 2. Editor page

- [x] 2.1 Colour code as a native picker; an unset colour shows the base's own colour (`base_colours`), ↺ returns to it
- [x] 2.2 Buildings zoom slider (13–17), hidden when buildings are off
- [x] 2.3 "Custom" road option when the triple matches no preset
- [x] 2.4 Place search in the preview bar through a MapLibre adapter; Print follows the searched place

## 3. Tests and strings

- [x] 3.1 Tests: Streets copy round-trip, Paper B round-trip, buildings zoom, Custom roads, picker + slider + search on the page
- [x] 3.2 New strings in the ten creator catalogs, compiled
- [x] 3.3 Full suite green
