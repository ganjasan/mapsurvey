## Why

Step 2 of 4 of epic #348 (#577). Every landing page shown at the ASLA 2026 workshop offered
downloads — the stakeholder input summary, the open-house boards, the draft plan — and showed
where the project is. After #576 a creator can only link to files hosted elsewhere and has no
map on the page.

## What Changes

- **Documents block**: files uploaded to the landing (PDF and common office / text formats,
  ≤ 25 MB each, ≤ 20 per block), each with a title; the page lists them with type and size.
  Stored on the public media tier under random keys (`landing_files/<uuid>.<ext>`), checked by
  extension AND by the file's first bytes, so an HTML or SVG renamed `.pdf` never lands on our
  media host.
- **Map block**: the project area from an uploaded GeoJSON file (≤ 1 MB, ≤ 500 features,
  WGS84), normalised on save (geometry + optional name only, 6-decimal coordinates), drawn
  read-only with Leaflet on one of the workspace's base maps, fitted to the area, with a colour
  and a caption.
- Both kinds join the picker; document titles are screened like the rest of the landing.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `survey-landings`: two block kinds added to the closed set (the requirement "Blocks are a
  closed set validated by one function" grows), plus a requirement each for documents and the
  map.

## Impact

- Model + migration: `LandingFile` (block FK, file, title, size, content type, order);
  `LandingBlock.kind` choices gain `documents`, `map`.
- `survey/landings.py` (cleaners, file checks, GeoJSON normaliser), `survey/landing_views.py`
  (file add / rename / remove inside the block save), templates `landings/blocks/documents.html`,
  `landings/blocks/map.html`, form fields, `landing_public.css`, Leaflet on the public page only
  when a map block exists, `content_screening.collect_landing_text`, help page, translations.
