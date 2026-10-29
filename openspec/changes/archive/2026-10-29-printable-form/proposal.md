## Why

Consultants take surveys offline for the people who do not answer on a phone: the Baltimore
neighbourhood plan (the platform's largest live survey) printed paper copies in two languages and
laid them out by hand; at the ASLA 2026 workshop every board was a hand-made sheet. Item 1 of epic
#350 (#355) lets the team type those sheets in, but the sheet itself is still outside the product,
so it drifts from the survey, carries no map, and gives items 3 and 4 (photo → prefilled entry,
map marks → coordinates) nothing to read back. Issue #489.

## What Changes

- **Print form** on the Share page: a language of the survey and a paper size (A4 / US Letter),
  one click, a PDF of the whole survey as a paper form. Editor role and up, every plan; a draft
  survey prints with a DRAFT watermark, a closed one prints normally.
- **One source.** The PDF is built from the survey's structure at print time, in respondent order,
  for the `respondent` surface: operator-only items are left out, visibility rules become an
  "Answer only if …" line, groups print as titled blocks. There is never a second print version.
- **A paper shape for every question type**: text lines, number boxes, one box per option with a
  write-in line for "Other", a scale for range and rating, 👍/👎 boxes, a date field, numbered
  blanks for ranking, a note for file questions ("online only"), the body of a Formatted Text
  block, pictures embedded.
- **The map.** A map section with geo questions prints its map as a static image — the section's
  start position, zoom and basemap, else the survey's — with the survey's reference layers drawn
  on top, a scale bar and attribution, and a **marker legend**: each geo question gets a letter and a
  symbol (point ●, line ━, area ▭, spray ░) and the legend names the question, the letter and how
  many marks are allowed. Sub-questions of a geo question print as a small table keyed by mark
  (A1, A2, …); Objects-on-the-map questions print the layer's objects as a table with the
  sub-questions as columns. A Form-layout section prints no map.
- **Machine-readable page.** Four alignment marks in the page corners and a **form code** on every
  page — as text and as a QR — naming the printed form and the page. The form is a `PrintedForm`
  row: survey version, language, paper, the structure hash it was built from and, per page, where
  the map frame sits on the page and which geographic bounds it shows. That row is what item 4
  will read to georeference a photographed mark; the same (version, language, paper, hash) reuses
  the row, so reprints carry the same code.
- **Page 1 extras**: a QR with the survey's online link through a `TrackedLink` (`src=paper`) and an
  "office use" box with a sheet-number blank for item 1's entry form.
- **Event** `form_printed` (`survey_id`, paper, language, page count — never a URL) on the server.
- **Dependencies**: `reportlab` (PDF, pure Python) and, for tests, `pypdf`; the DejaVu Sans fonts
  bundled under `survey/print/fonts/`; the Mapbox Static Images API behind the existing token,
  cached. The print pipeline (`survey/print/`) is where the flyer generator #220 will plug in.

## Capabilities

### New Capabilities
- `printable-form`: the printable form — what is on it, how each question type looks on paper,
  the section map with layers and legend, the form code and alignment marks, the `PrintedForm`
  record, the Share page control, languages and paper sizes, the watermark, the event, and how
  the map image is obtained and what happens when it cannot be.

### Modified Capabilities
- `creator-distribution-events`: `form_printed` joins the sharing actions, captured server-side
  with paper, language and page count.
- `share-page`: the Share page carries a Print section that is not gated behind publish state
  (a form is proofed before publishing and printed after closing).

## Impact

- **New package `survey/print/`**: `pdf.py` (document, page template with marks/code/footer,
  flowables per question type), `static_map.py` (Mapbox Static Images fetch + cache, reference
  layer overlay with Pillow, scale bar), `form_code.py` (code format, QR payload), `fonts/`
  (DejaVu Sans + Bold, licence), `views.py` (download view), `forms.py` (the dialog form).
- **Model**: `PrintedForm` (survey FK to the canonical, `version_number`, `language`, `paper`,
  `structure_hash`, `pages`, `layout` JSON, `tracked_link` FK, `created_by`, `created_at`);
  migration `0112`.
- **Share page**: `survey/share_views.py` context + `editor/survey_share.html` section; URL
  `editor/surveys/<uuid>/print/form/`.
- **Pipfile**: `reportlab`, dev `pypdf`. `Dockerfile` unchanged (no system libraries).
- **Reads, no writes, of**: `visibility.compute_visibility`/`describe_rule`, `groups.group_runs`,
  `layers.layers_for(...).defer(None)` + `normalize_style`/`match_class` (text read once per
  print, never cached on the instance — layer memory rules), `question_types`, translations
  accessors, `SurveySection.start_map_postion/zoom/override_basemap`, `TrackedLink`.
- **Events**: `survey/product_events.py` `FORM_PRINTED`.
- **i18n**: the form's fixed strings ("Answer only if", "Mark on the map", "Office use", …) are
  rendered in the FORM's language through the respondent catalogs (75 languages), the dialog's
  strings in the creator catalogs (10).
- **Help**: `how-to/print-a-paper-form.md` + `help_links` key `print_form`; linked from the dialog
  and from the entry form's help page.
- **Tests**: `survey/tests/test_printable_form.py` (new capability), deltas in
  `test_share_page.py` and `test_creator_distribution_events.py`; Mapbox is mocked everywhere.
- **Out of scope**: reading a photo back (item 3), marks → coordinates (item 4), flyers (#220),
  two languages on one sheet, custom logos, API/MCP access to the PDF (follow-up in epic #408).
