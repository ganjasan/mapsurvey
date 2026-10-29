## Context

Nothing in the stack writes PDFs today (#220 says reportlab/WeasyPrint "are in the stack" — they
are not; `Pipfile` has Pillow 11 and `segno` for QR). Static maps exist only as a report tool
(`scripts/report_tools/maplib.py`: headless Chromium over Leaflet, Mapbox satellite tiles) — fine
for a laptop, not for a gunicorn worker. The respondent map is Leaflet with three basemaps
(`streets` = Mapbox Streets, `satellite` = Esri World Imagery, `topo` = Mapbox Outdoors); a section
may override position, zoom and basemap, else the survey's apply. Reference layers are
`SurveyMapLayer` rows with gzip-compressed GeoJSON text (up to 10 MB; the memory-diet rules say
who may read it) and one validated style (`normalize_style`, `match_class`, `legend_for`).
Everything about what a respondent sees — order, groups, rules, audience — is decided by
`compute_visibility` and `group_runs`; item 1 added the `respondent`/`operator` surfaces.

## Goals / Non-Goals

**Goals:**
- A form that is the survey: same order, same wording, same options, in the chosen language, built
  at print time from the live structure.
- Maps on paper that a respondent can mark and a machine can later read: a legible basemap with
  the creator's layers, a legend of letters/symbols, and a recorded geography per map frame.
- Pages that identify themselves: alignment marks and a form code on every page.
- No new system dependency in the Docker image; no headless browser in production.

**Non-Goals:**
- Pixel-perfect typography, custom branding, two-language sheets.
- Reading anything back (items 3, 4): this change only records what item 4 will need.
- A generic reporting/print framework; #220 reuses the page template and the static map, nothing more.

## Decisions

### D1. reportlab, not WeasyPrint
WeasyPrint needs pango/cairo/gobject in `python:3.12-slim` (apt packages, ~100 MB, and a second
HTML renderer to keep looking like the first). reportlab is pure Python over Pillow, renders in a
worker thread in well under a second per page, and its platypus flowables are exactly "a question
is a block that must not split". Price: layout is code, not a template. Fonts: reportlab's built-in
fonts are Latin-1; the form prints survey text in any of 75 languages, so DejaVu Sans + Bold
(Bitstream Vera licence, ~1.4 MB) ship in `survey/print/fonts/`. CJK scripts fall back to boxes —
documented limitation, Noto CJK is 20 MB and a later addition.

### D2. One builder over the respondent structure
`survey/print/pdf.py::build_form(survey, language, paper)` walks sections → `group_runs` → questions
exactly as the respondent page does, with `compute_visibility(survey, {}, surface='respondent')`
to drop operator-only items and `describe_rule` to print "Answer only if <controller> = <options>".
Hidden-by-rule items print (a paper respondent cannot be shown a branch dynamically); the note
carries the condition. Every question type maps to one flowable factory in `QUESTION_SHAPES`
(dict keyed by `input_type`, like `DISPLAY_STYLES_BY_TYPE`); an unknown type prints its name and
text lines so a new type never silently vanishes from paper.

### D3. The map is a static image from Mapbox + a Pillow overlay
`static_map.py::render_section_map(section, language, size_px)`:
1. Centre/zoom = section's `start_map_postion`/`start_map_zoom`, else the survey's, else the
   bbox of the survey's reference layers, else world zoom 1 with a note.
2. Basemap = section `override_basemap`, else survey `default_basemap`, else first of `basemaps`:
   `streets` → `mapbox/streets-v12`, `topo` → `mapbox/outdoors-v12`, `satellite` →
   `mapbox/satellite-streets-v12` (the respondent's Esri imagery has no static endpoint; the
   nearest look with street names, which paper needs more than a screen does). Fetched from the
   Static Images API at `@2x` (max 1280×1280 logical), `attribution=false&logo=false` and the
   attribution text printed under the frame instead ("© Mapbox © OpenStreetMap"), token =
   `MAPBOX_ACCESS_TOKEN`. Cached in the default cache 24 h by (style, centre, zoom, size).
3. Reference layers of the survey (`layers_for(survey).defer(None)`, read once, text never kept
   on the instance) are projected to Web Mercator pixels at that zoom and drawn with Pillow:
   polygons filled at the style's opacity, lines stroked, points as circles, colour from
   `normalize_style` + `match_class`, labels from `label_field` for layers that have one.
   Features outside the frame are skipped; a layer over 20 000 features draws its first 20 000
   and the legend says so.
4. Scale bar from zoom and latitude; a 10 mm white frame margin for the respondent's hand.
**Alternative rejected**: tiles stitched by us (no static endpoint for Esri; more requests, more
code) and headless Chromium (a browser per worker in production).

### D4. Fail-soft map
No token, a Mapbox error or a timeout (5 s) prints the frame empty with a 10 mm grid and the text
"Map unavailable — attach a printed map here", and the `PrintedForm.layout` entry records
`basemap: null`. The form is still usable; the creator sees the gap on page 1 of the PDF.
Nothing raises past the view.

### D5. Letters and symbols, never icons
Marker icons (Font Awesome classes, Maki/Temaki SVG sprites) would need an SVG rasteriser and
would not survive a photocopy. Each geo question of a section gets a letter in survey order and a
symbol by type: point ● (draw a dot and write the letter), line ━ (draw the line, write the
letter at its start), area ▭ (outline the area, write the letter inside), spray ░ (shade the
area, write the letter). The legend row: symbol, letter, question name, "up to N" from
`max_features`/`min_features`, the question's colour as a small swatch for colour prints.
Sub-questions print under the legend as a table whose first column is the mark (A1, A2, A3 — as
many rows as `max_features`, else 3) and whose columns are the sub-questions, choice sub-questions
as boxes. Objects-on-the-map questions print the layer's objects (title, key) as a table with the
sub-questions as columns, capped at 60 rows with a note.

### D6. `PrintedForm` is the form's identity, the code names it
A page must say which survey version, language and paper it came from and where its map frame
is — and wording edits on a live survey (no new version) move frames by a few millimetres, so a
deterministic re-render is not an identity. `PrintedForm(survey=canonical, version_number,
language, paper, structure_hash, pages, layout, tracked_link, created_by, created_at)` is written
once per distinct (version, language, paper, hash) and reused on re-download, so a reprint has the
same code. `layout` = `{page: {"map": {"x_mm","y_mm","w_mm","h_mm","bbox":[w,s,e,n],"zoom",
"basemap","section_code"}}}` for pages with a frame, recorded by a flowable that reports its drawn
rectangle. The code is `MS-<id in base32>-<page>` as text in the footer and `ms:form:<id>:<page>:
<pages>` in a 16 mm QR at the bottom right; the survey uuid is not in the code (the row has it; a
photo of a page should not leak the survey's public key). `structure_hash` = sha256 over the
rendered item list (codes, types, option codes, wording, language) so a changed survey gets a
new form.

### D7. Alignment marks
Four filled black 6 × 6 mm squares, 8 mm from the page corners, on every page; the map frame has
no marks of its own — its position is in `layout`, relative to the page's marks. Item 4
registers the page by the four squares, then the frame by `layout`.

### D8. Where it lives and who may print
A **Print a paper form** section at the end of the Share page, outside the publish gate so it
shows for every status (the public-link sections stay gated): language select when the survey has more than one,
paper radio (A4 default, Letter when the creator's browser locale is `en-US`/`en-CA`), a
"Download PDF" link = GET `/editor/surveys/<uuid>/print/form/?lang=&paper=` (`editor` role, no
Pro gate — paper is how answers reach the Pro entry form). Draft and testing surveys get a
diagonal "DRAFT — not for distribution" watermark; closed ones print clean. The page-1 online QR
is a `TrackedLink(utm_source='paper', utm_medium='print_form')` per survey, created on first print
and reused, so Perf shows how many answered online from a sheet.

### D9. Server event only
`form_printed` is emitted from the view (`pe.emit`, `survey_id`, `paper`, `language`, `pages`,
`map_pages`) — the download is a navigation, so a browser capture would race it.

### D10. i18n in two catalogs
Fixed form strings use `translation.override(language)` around the build: they come from the
respondent catalogs (75 languages, `test_every_respondent_string_is_translated_in_every_catalog`
extended to walk a printed form). Dialog strings are creator strings (10 catalogs).

## Risks / Trade-offs

- [Mapbox Static Images is a paid API after 50 000/month] → one request per distinct map frame,
  cached 24 h; a `PrintedForm` reuse does not re-render; the Static API is a separate SKU, noted
  in `billing/README.md`'s cost list.
- [Reference layers of 10 MB decompressed in a web worker] → same budget the layer endpoint and
  the ZIP export already take; read once, drawn, dropped; `LayerMemoryDietTest` pattern: a test
  asserts `.defer(None)` is the only text read and that the instance is not cached.
- [reportlab layout code grows] → every shape is one small function in `QUESTION_SHAPES`; the
  page template is one class; #220 adds its own document over the same template.
- [A photocopied sheet has no unique id] → by design: identity is the form, the sheet number is
  the "office use" blank item 1 fills; item 3 pairs a photo to a form by the QR.
- [Respondents mark a point with the wrong letter] → the legend is next to the map on the same
  page; the symbol differs by type; item 3 shows the crop for review anyway.
- [Fonts without CJK] → boxes; a warning line in the dialog when the chosen language is
  `zh`/`ja`/`ko`, Noto CJK as a follow-up.

## Migration Plan

Additive: new model + migration `0112_printedform`, two packages added to the Pipfile (the shared
venv gets `uv pip install reportlab pypdf`), fonts committed. No kill switch; the section is one
include on the Share page. Rollback = revert.

## Open Questions

- Two languages on one sheet (Amanda's Spanish copies): a second column or a second form? Default
  here: one form per language; the dialog prints each separately.
- Should the online QR go on every page or page 1 only? Page 1 only here.
