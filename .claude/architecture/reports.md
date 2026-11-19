# Reports module

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**The report as a story (change `reports-story`, #704 part 1; owner direction 2026-11-16)**: Reports is a
STORYTELLING module and v1 is the LINEAR story — one column, text with charts, maps and quotes between the
paragraphs. Acceptance rule: every report made by hand can be opened by its customer in Reports and edited
there. So: (1) **story blocks** — `heading`, `text` (rich, `reports.story.clean_html` = `coerce_creator_html`),
`image`, `numbers` and `quotes` (`ReportBlock.config = {"items": […]}`, typed by the author: typed numbers are
ALLOWED; `reports.story.clean_config` is the one cleaner, the editor posts them as lines `value | label` /
`quote | source`); `ReportBlock.width` `full | half`, two consecutive halves share a row
(`render.story_rows`) — never a container block. (2) **One editor, two ways in**: every view in
`reports/editor_views.py` is written once and exported twice, `on_survey(view)` (the survey's Public results
tab, URL names `editor_public_results_*`) and `on_report(view)` (`/editor/reports/<uuid>/…`, names
`editor_report*`); both set `request.report` / `request.survey` (None for a blank or imported report) and
the template takes EVERY url from the `u` dict (`_urls(request)`) — never `{% url … survey.uuid %}` there.
`may_edit_report` = workspace editor + editor on the home survey when there is one; strangers get 404.
(3) **The report file** (`reports/files.py`): a ZIP with `report.json` (`format: 1`) + `images/`; question
blocks by survey uuid + question CODE, re-bound on import (`data.questions.question_of`) or left out with a
message; an import is always unpublished and `workspace`-only, text re-sanitised. Hand-made HTML reports are
turned into that file by the ops repo's `scripts/report_html_to_file.py` — customers' reports never enter this
repo. (4) The page (`public_results.html`) renders `rows`; a text payload carries `html`, and a snapshot frozen
before this change has only `body`, which the template ESCAPES. A report without a survey has no comment
threads (threads hang on a survey) and no "N responses".
**Live blocks (change `reports-live-blocks`, #704 part 2)**: `crosstab` and `engagement` blocks point at a
`DatasetView` of that kind (`ReportBlock.view`, `VIEW_BLOCK_TYPES`); `services.add_view_block` MAKES the view in
Data (`data.services.create_view`, or reuses an identical one) — Data's refusals are the block's. The payload is
`dataviews.result(view, lang, k=<the REPORT's K>)` plus presentation only (`render._view_payload`): no count is
produced in `reports/`. **A map block may show the marks themselves** — `config = {"marks": true}`, a per-block
switch, off by default (owner decision 2026-11-16: the survey owner's choice and responsibility); the payload is
then `data_type: "marks"`, geometry only. That exception is a report block's ALONE: Site results blocks, grid /
coverage / density views, the Data API and MCP keep the grid (`public-aggregates`). **Live numbers**:
`reports/tokens.py` fills `{responses}` `{opened}` `{finished}` `{marks:CODE}` `{respondents:CODE}` in Text
blocks, key numbers and the opening paragraph from the HOME survey, masked with the report's K; a token that
cannot be filled stays as written; a frozen snapshot stores the filled text (and `intro_body`). The report file
carries all of it (`crosstab` by survey + two codes, `engagement` by survey, a map's `marks`).
**Starting a report (change `reports-start`, #705)**: `/editor/reports/start/` (`reports.views.report_start`,
`reports/start.html`) — one click on a card does its action (each card is the submit button of its own form;
do not add a "choose, then confirm" step). `reports/drafting.py::build_draft(actor, survey, template)` builds a
NEW report by RULES, never a model and never into the survey's first report: key numbers and the engagement
block first, then one block per top-level question that has answers in clean sessions, in respondent order,
section titles as headings; four arrangements (`TEMPLATES`: `summary`, `council`, `update`, `yousaid`) are
small builder functions over `_Draft`. **Hidden instead of placeholder**: prompts ("Write what this part…") and
candidate quotes from free-text questions (≤ 8 recent answers of 30–320 chars) are real blocks with
`is_hidden=True`, so publishing an unfinished draft shows none of them and a quote reaches the page only after
the author un-hides it. `copy_report` = the report file's export + import in memory (a copy cannot keep what an
export would lose). Entry links: Reports list, Responses of a published survey, the responses dataset.
Events `report_entry_seen` / `report_created` carry ids and choice names only. `Report.template` records the
arrangement.
**Before you publish (change `reports-review`, #706)**: `reports/checks.py::run(report)` is the ONE list —
`privacy` (every VISIBLE quote written out, every map with marks, K = 1) and `other` (a block the renderer
returns None for → "Delete the block"; a map without a description; no title; hidden blocks counted). A new
check is a few lines there. `services.set_published(actor, report, publish, ack, visibility, mode)` refuses
`ack_required` when `checks.needs_ack` (a visible quote or a map of marks) and the author did not tick the
box — nothing else blocks, K = 1 is only listed. Every "Publish" button opens the dialog (`prOpenPublish()`,
body `editor/partials/pr_checks.html` fetched by HTMX from the `checks` route each time), which also posts
`visibility` and `mode` (live | frozen). A map block's `content` is its description: shown under the map and
`role="img"` + `aria-label` on the container. The preview pane has phone / computer widths. Comment threads
exist on blocks of a survey's report only (a thread belongs to a survey).
**The PDF of a report (change `reports-pdf`, #707)**: `reports/pdf.py::build_pdf(report, base_url)` lays out
the PAGE'S OWN payload (`render.build_context` → `rows`) on A4 with reportlab — NOT a headless browser — so a
number in the PDF is the number on the page and nothing is counted there; a new block type needs a branch in
`pdf._block` as it does in the template. Maps = `survey.print.static_map` basemap of the block's extent with
cells / marks painted by Pillow (no token or a Mapbox error → plain ground). Every block is `KeepTogether` and a
heading is folded into the block after it. **Never rendered in a web request**: `services.request_pdf` creates
a `ReportPdf` row (private media tier, `report_pdfs/<uuid>.pdf`) and enqueues `reports.tasks.render_report_pdf`,
which claims the row (`queued → running`), so a redelivered message does nothing; the editor's button polls
`editor_report_pdf`. `stamp`: a FROZEN report has one PDF per snapshot, reused and linked from its page
(`/r/<slug>/pdf/`, the page's own visibility guard); a LIVE report gets a new rendering per request and no public
link. No PDF is made at freezing time. Tests patch `survey.print.static_map.fetch_basemap` so no test calls Mapbox.
**A report outside its page (change `reports-embed`, #708)**: embedding REUSES the survey embed mechanism —
`reports.embed.mark(request, report)` sets `request.survey_frame_ancestors` (so `SurveyEmbedMiddleware` applies
`frame-ancestors` from `Report.embed_allowed_hosts`, empty = `*`), the page in `?embed=1` posts the same
`{mapsurvey: "height"}` message and the same `/embed.js` grows the iframe. Only a published `public` /
`unlisted` report is framable; `workspace` keeps `SAMEORIGIN`. One block has its own page,
`/r/<slug>/block/<id>/` (the report's template with ONE row, `single=True`); `/oembed/` answers report and block
links. **CSV and PNG are made from the block's PAYLOAD, never from answers** — `reports/tables.py::rows_of`,
`reports/pictures.py::block_png` (Pillow: bars, a table, `pdf.map_image`) — so a group the page hides is "<K" in
the CSV and its value is not in the file. Public CSV at `/r/<slug>/block/<id>/data.csv`; an editor's CSV / PNG at
`editor_report_block_file`; all blocks as one ZIP = the PDF's worker job with `ReportPdf.kind = 'zip'`
(`reports.tasks.build_zip`). A "Report" block for Sites is not built (a Sites block kind; follow-up).
**The next round (change `reports-reuse`, #711)**: `drafting.copy_report(actor, report, onto=None)` is still the
report file's round trip; `onto` (a survey) goes to `files.import_report(onto=)`, which makes it the home survey
and resolves EVERY data block's survey to it, matching by question code. A block that finds no question is,
with `onto`, kept as a HIDDEN text block naming it (`unmatched()` in `import_report`) and listed in
`copy.copy_notes` (the start page flashes them); a plain import keeps leaving it out with a note. Never drop a
block without a note. `compare` is a block type of its own (not in `QUESTION_BLOCK_TYPES`): `dataset` +
`question_code` as a chart's, `config = {"other": "<survey uuid>"}`; `services.comparable(question, other)` is
the ONE rule for "can be compared" (same code, both chart types, both numeric or both not) used at add time and
at render time; `ReportService._compare_payload` joins two `_choice_data` / `_number_data` aggregations by
option code — shares of the people who answered, masked per round, no share for a masked cell or a round under
K. The page, the PDF and the CSV draw the same `rows`. Event `report_reused` (ids and counts).
**Readers, tags, API and MCP for reports (change `reports-usage-api`, #710)**: `reports/usage.py` counts, per
report and DAY, `view` / `embed` (`?embed=1`, a block's page included) / `pdf` in `ReportUsage` — one row per
day and kind, no visitor stored, a signed-in member of the report's workspace not counted, a failed count never
breaks the page; `usage.summary` feeds the editor's Readers card and the API. Do not add per-visitor rows or a
third-party script to `/r/`. A report takes workspace tags through the Data module's `Tag.reports` and
`data.tags.set_tags` (`services.update_settings(tags=)`). **API and MCP write blocks from plain values through
`reports/blocks.py`** (`add` / `change` / `describe`): a spec dict → the SAME `reports.services` calls the
editor makes; what a block looks like outside the database is `reports.files.entry_of` — the report file and
the API share it, so a new block type is described once. `api/v1/reports.py` holds the routes AND the functions
the MCP tools (`mcp/tools/reports.py`) call (`report_for`, `create`, `save_settings`, `publish`, …); scopes are
the surveys' (`publish` → `surveys:publish`, delete → `surveys:delete`); two gates: `require_pro_api` on the
workspace and, on writes, `reports.gate.use`. REST publishes a report with quotes or marks only with
`confirm: true` (409 `conflict`); MCP `publish_report` / `delete_report` answer `confirmation_required`. Image
blocks are editor-only (no upload in the API).
**Reports is Pro (change `reports-pro`, #709; owner decision 2026-11-16)**: feature `reports` in
`billing/features.py`, in the trial UNCAPPED (the trial's limit is its 90 days). `reports/gate.py` is the one
place: `covered(org)` = plan or a live trial (`Entitlements.covers`, NOT `may` — a report made under the trial
stays alive until the trial ends); `use(org, user)` lets a WRITE through, starting the workspace's trial when it
never had one; `freeze_if_lapsed(report)` freezes a published live report of an uncovered workspace. **Writes are
gated, reading never is**: every POST of the report editor passes `_gated` in the `on_survey` / `on_report`
wrappers, plus `report_create`, `report_start` and `report_import`; the refusal is `editor_views.paywall`
(`billing.gates.feature_required`, or 403 JSON `pro_required` for autosave) and emits `report_paywall_shown`.
The editor's GET, export, PDF and ZIP work on any plan (banner `reports_locked`). **The public routes never
answer 404 or an upgrade page for the plan**: `report_page` and `_guard` (block page, CSV) call
`freeze_if_lapsed` first, so a lapsed or never-Pro workspace's report is its snapshot at the same address.
`manage.py freeze_reports_without_pro [--dry-run]` lists and freezes them all (ship day). The survey's first
report is still drafted for free by `scaffold_report` — the product drafting, not a member writing. A new
write endpoint for reports must go through the wrappers or call `gate.use`.
**Reports (`reports/`, change `reports-object`, #703; epic #712)**: what was the public results
page is a **report** — `reports.models.Report` (a workspace object at `/r/<slug>/`, `survey` = its
HOME survey, nullable and not unique) with ordered `ReportBlock`s. A question block names a
**dataset of the Data module and the question's code**, never a question row (`publish_draft()`
replaces rows): a map block reads the `answers` dataset of (canonical survey, code), chart / objects
/ budget blocks the survey's `responses` dataset. `block.question` is a cached property
(`reports.sources.question_for`; lists go through `attach_questions`), and
`ReportBlock.objects.create(question=q)` fills dataset and code. So one report may read several
surveys, and `ReportService` scopes sessions PER BLOCK (`_scope_of(question)`), not per report.
Rendering is `reports/render.py` (`ReportService`, `render_data`, `freeze_report` /
`unfreeze_report`, `scaffold_report`, `report_for_survey`, `k_for_survey`); every write is
`reports/services.py` with an `Actor`. `SurveyHeader.report` (the survey's oldest report) is what
the Public results tab, the thanks button, Share and the dashboard pill read — never
`Report.objects.get(survey=…)`, a survey may be home to several. The editor is the report builder
below (`reports/editor_views.py`; URL names `editor_public_results_*` through a survey,
`editor_report*` by the report). Aggregates run over CLEAN
sessions only (not deleted, excludes `not_approved`/`on_hold`) across the canonical survey + all
versions. Privacy: k-anonymity masks buckets `<K` (default 3); geo popups expose only
creator-selected `geo_label_fields`; individual free-text answers are not published (hand-picked
quotes arrive with #704). Hybrid `live` (60s cache) vs `frozen` (snapshot) mode. Visibility
`public` (indexed, in sitemap), `unlisted` (noindex) or `workspace` (signed-in members of the
workspace only: anonymous → login, others → 404). "Used by": `data.links.report_places`; a
`DatasetView` a block shows cannot be deleted (`view` is `RESTRICT`), a dataset that disappears
leaves the block empty (`SET_NULL`). The Reports list is `/editor/reports/`. Report config is
intentionally NOT included in survey ZIP export/import. Migration `reports/0002` copied the old
pages WITH their ids (comment anchors, snapshots, `?block=` links).

**Key numbers (change `report-key-numbers`, #744)**: a key number is still `{'value', 'label'}` and a value
that is ONE token (`reports.tokens`) follows the answers — but the author never types or sees a token in
that block. `reports/numbers.py` is the one place: `defaults()` is the set a new block arrives with in a
report of a survey AND the set `drafting` opens a draft with (do not fork the list), `choices()` feeds the
menu (`_number_menu.html`, drawn once per page; `js/report_builder.js` moves it under "Add a number" or a
live number), `is_live()` marks a row `data-live` on the canvas — not a text field, a click opens the menu.
The menu remembers its target by block id + row number, never by node: the shared builder swaps a block's
markup when a save is answered while the caret is elsewhere. A value mixing text and a token, the note and
the opening keep the reveal-the-token-on-focus behaviour. Do not put the token list back into the Key
numbers panel (owner, 2026-11-18: "friendly to the least experienced user").

**Map views (change `report-map-views`, #753)**: a map block is drawn as the maps of the hand-made customer
reports were — `ReportBlock.config = {view, marks, frame}`, cleaned by `story.clean_config('map')`. `view` is
`heat` (a new block's default) | `hotspots` (point questions only; `story.map_view` falls back to heat) |
`squares` | `marks`; no `view` = a block made before (squares, or marks). The payload keeps TWO keys apart:
`data_type` is what it carries (`grid` cells that count respondents, or `marks`), `display` is the look — the
page script, the PDF (`pdf.map_image`), the PNG and the CSV all read `display` and fall back to `data_type`.
Privacy did not move: heat is the K-grid blurred, a hot spot (`data.aggregate.hotspots`, 120 m cells merged
within 150 m, computed in Data) needs K distinct respondents and two marks; `config.marks` ("Use every mark",
the owner's 2026-11-16 switch) builds both from every mark, the Marks view forces it on, and `checks` still asks
for the author's confirmation. `frame` = `[w, s, e, n]`, kept on the canvas by "Keep this view" (the shared
renderer leaves its Leaflet map on the holder as `_rpMap`; `report_builder.js` writes the hidden
`data-input="map_frame"`). The hot-spot list and the legend are written by `reports/_block.html` (translated),
never by the script. The report file carries `view` and `frame` (and a cross-tab's `display`).
**Layers (change `report-map-layers`, same issue)**: a map is a list of layers — the block's own question
(`dataset` + `question_code`, its look at the top level of `config`) is the first and drawn on top;
`config['layers']` holds up to `story.MAX_MAP_LAYERS` other map questions `{id, survey (uuid), code, view, marks,
color, name, opts, fields}` (`services._checked_layers` refuses anything that is not a map question of the
workspace). One function builds every layer, `render._map_layer(question, look, color, label_fields)`; the
block's own sits at the top level of the payload (so the PDF, the CSV and old readers of `cells` / `marks` keep
working), the others under `layers`, plus `legend_rows` / `spot_lists` for the template. A view's settings are
`opts` (`story.MAP_OPTS`, defaults never stored): heat `spread` / `strength`, hot spots `top` / `place` / `list`
/ `shade`, squares `cell`, marks `size` / `solid`. In the panel each layer is a card
(`reports/editor/_map_layer.html`) whose fields carry its prefix (`map_` for the own layer, `L<id>_` for the
others) inside the block's ONE form; the settings of the views not chosen stay in the form, hidden by `:has()`.
A new field of a layer is a key in `clean_map_look` + a line in `editor_views._map_look` + the card. Privacy is
per layer (`marks` on the layer); `checks` looks at every layer. Not built: context layers from Data, areas
shaded by answers, a filter by sub-question, reordering layers, layers / views through REST and MCP.

**Home survey and source surveys (change `report-home-survey`, #739)**: `Report.survey` is a DEFAULT, never
a restriction — blocks name their own dataset, so one report may read several surveys. The block library
has "Charts and maps from" (`source=<uuid>`, posted with the tile; tiles for another survey come from the
`library` route as the `_library_groups.html` fragment). `editor_views._source()` is the one resolver: no
`source` = the home survey exactly as before; a report without one starts on the workspace's only
published survey or asks. The first DATA block added in the editor makes its survey the home survey
(`services.set_home_survey`; editor only — API/MCP name a survey explicitly), and Report settings →
Survey sets, changes or clears it (`report_home`, a plain form that reloads the builder). Both need the
editor role on the survey, because `may_edit_report` would otherwise lock the author out. "New report"
stays one click and blank (#737) — do NOT bring a "choose a survey" step back before the editor. A report
with `created_by` is never auto-drafted by `scaffold_report`. The CTA / thanks-page switches render only
with a home survey; their stored values travel as hidden fields.

**Report builder (change `reports-canvas-editor`, #731)**: the report editor is the Sites canvas
builder for a report — `reports/builder.html` runs on the SAME script and stylesheet as Sites
(`js/site_builder.js`, `css/site_builder.css`, every `lb-` hook) plus `js/report_builder.js` /
`css/report_builder.css` for what only a report has (publish dialog, PDF job, half-width pairs, the
library's two forms). Do not fork a second builder script; a change to `site_builder.js` must keep
both pages working. Left: outline; centre: the report as readers see it, written in place
(`reports/editor/_canvas_block.html`, `_hero.html`); right: ONE context panel — the selected block's
form (`_block_panel.html`, the WHOLE block: what is written on the canvas travels in its hidden
fields) or the report's settings (`_page_panel.html`). `reports/canvas.py` builds one record per
block, hidden and empty ones included, with the `note` saying why readers do not see it; nothing is
cached there. A save posted with `autosave=1` is answered with fragments (`block`, `outline`,
`panel`; settings: `title`, `hero`) computed for THAT block only (`_block_fragments`,
`_shell_context`) — never rebuild the whole canvas in an autosave answer. Key numbers and quotes
post parallel lists behind `rows=1`; the `items` textarea dialect stays for the API-less callers and
tests. Readers' markup is ONE partial, `reports/_block.html`, and ONE stylesheet,
`css/report_public.css`, every rule under `.rp` with the row class `rp-row` (the canvas lives under
Bootstrap, whose `.row` is a flex row): a look changed there changes `/r/`, embeds and the canvas.
A field that shows a live number (`{responses}` in a key number or the opening) carries the token
in `data-raw` and `plainValue()` returns that until the author clicks into it — never save
`innerText` of such a field. A question block's empty title means "the question's name", shown as
the placeholder (`rb-default-title`); `?block=<id>` selects a block (publish checks, comment mail).
Blocks are added from the library (`_library.html`): `block_type`, or `question_id` for a chart /
map, with `after` (`top` | block id) — `_place` renumbers through `reorder_blocks`. A picture block
may be created empty. The builder extends `editor_base.html` (Sites extends `base.html`): through a
survey it is that survey's Public results tab and keeps the survey's title, tab strip and publishing
widget above it — tests hold every survey page to that. The old tab's own mobile status line and
Structure / Edit / Preview bar are gone; on a narrow screen the panel sits under the canvas, as in Sites.
Both builders' side panels are resized by dragging their inner edge (`initPanelResize` in
`site_builder.js`; widths are the `--lb-rail-w` / `--lb-panel-w` variables on `.lb-work`, kept in
`localStorage['msBuilderPanels']`, double click = default) — a new column rule must keep those variables.
A report is deleted from its row in the Reports list or from its settings (`reports/_delete_confirm.html`
holds the dialog's wording for both; `editor_report_delete` takes the POST only). "New report" creates a
blank report in one click; the start page offers the blank card only — the four arrangements and "Copy an
earlier report" are off the page since 2026-11-18 (owner: get the blank report right first), while the view
still takes `kind=draft|copy`.
