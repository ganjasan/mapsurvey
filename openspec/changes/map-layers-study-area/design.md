# Design: map-layers-study-area

Journey board (owner's, private canvas): https://claude.ai/artifact/Qhx8vmePxSEEZuYqW2hHgi —
journey map, six screens (Map card, Add layer, Study area editor, Objects question, Publish
check, respondent phone) and the "Where things live" model. Issue #779; absorbs #303 and the UX
part of #232.

## Context

Today, after `layers-by-question` (shipped, not archived):

- A reference layer is a `SurveyMapLayer` owned by the canonical survey (`layer.survey`) and
  borrowed by draft copies and versions (`layer_owner()`); `layers_for(survey)` also returns
  public datasets linked "From Data" (`DatasetLink`, change `data-links`) — zero such links exist
  in production.
- A layer is on a section's map only when a top-level `layer_objects` question of that section
  binds it (`section_layer_ids`, D1 "Visibility = binding"). `panel_mode` (`list`/`legend`) decides
  whether the question lists objects or shows one legend line.
- Production (2026-11-24): 87 uploaded layers in 61 surveys, 39 of them with ≤3 objects
  (boundaries); 503 legend-only vs 102 list Objects questions; 12 layers on no map; 18 live surveys
  in 11 workspaces carry a hand-made study-area boundary.
- Every layer is mirrored as a Data registry row (`data/datasets.py::sync`): survey layers as
  `public`, workspace uploads (`layer.survey IS NULL`, `layer.organization`) as `private` until
  released. The Data import (`data/imports.py`, `data/tasks.py`) already reads GeoPackage, zipped
  shapefile, KML, GeoJSON and CSV and reprojects; the survey upload path does not and refuses a
  projected file.
- The Wizard geocoder (`survey/ai/geocode.py`) is Photon: a point and a zoom, no boundary.
- Section codes repeat within a survey; the translation table addresses sections as
  `section:<code>[#n]`.

## Goals / Non-Goals

**Goals**
- One source of truth per purpose: **placement shows**, **the Objects question asks**, **the study
  area bounds the survey**.
- A layer needed on every section is ONE setting, and sections added later get it.
- Uploading a layer from the survey ends with the layer visible in the preview, in one dialog.
- A study area from a place name in under a minute, edited on the map; optional refusal of map
  answers outside, enforced on the server.
- Layers live in Data: one copy, referenced, listed under "Used by".
- No visible change for respondents of existing surveys on deploy day (except where a creator
  later turns on fog or refusal).

**Non-Goals**
- Hard pan lock (`maxBounds`), several study areas per survey or per section.
- Style rules in the object editor; the Responses map (already shows every layer).
- Connected open sources and the Mapsurvey catalogue (platform v2).
- A map in form-layout sections (owner, 2026-11-24: a section without a map shows none; "every
  section" means every map section).
- A "starts hidden" option per layer: every placed layer starts switched on.

## Decisions

### D1. Placement is its own row, keyed like the translation table
`LayerPlacement(survey → canonical SurveyHeader, layer → SurveyMapLayer, scope: 'all' | 'sections',
sections: JSON list of section refs "<code>" or "<code>#<n>", position)`; unique (survey, layer).
`section_layer_ids(section)` becomes: placements of `layer_owner(section.survey_header)` whose scope
is `all`, or whose `sections` contains this section's ref — ordered by `position`. Form sections
still get nothing. A placed layer starts switched on in the layers control and the legend on every
section load (the respondent's toggle is not carried to the next section); a layer added in Survey
settings is placed with scope `all` — that is the "set it once, it is on every map" path. Keying by canonical survey + section ref (not FK) means draft copies, publish
and restore need no copying, exactly like `TranslationSource` and comment anchors.

*Alternatives:* per-section M2M rows copied with sections (rejected: every draft/publish path must
copy them — #329 was a dropped field on that path); a flag on the layer (rejected: cannot express
"only sections 1 and 3").

### D2. Placement is a SAFE edit on a live survey
Showing a layer collects nothing and puts no answer at risk, so place / unplace / scope / order
apply in place on a published survey (`_check_content_edit_allowed`), like a layer object edit
today. While unpublished changes exist, the placement still lives on the canonical survey and is
shared by both — stated in the Map card. *Alternative:* structural edit through the draft
(rejected: a boundary should not need "Publish changes").

### D3. The Objects question asks; picking a layer places it
`layer_objects` keeps `layer`, `min_objects`, `objects_search` and its sub-questions. Saving it with
a layer not placed on its section creates (or extends) the placement — through the same service
call — so `section_layer_ids` reads placements only. Deleting the question never removes a
placement. `panel_mode` is retired: the object list is the question's body; the legend line moves
to the map's legend (D6). A question with no sub-questions saves (a creator builds top-down) and
shows "The layer already shows from the Map card — add a sub-question to ask about each object".

Shared-map (`source='question'`) layers keep their lifetime rule with "reader" = a placement OR an
Objects question in any header: deleting the last reader deletes the layer.

### D4. Layers live in Data
- An upload from the survey (Map card or Settings) is read synchronously up to the survey cap
  (10 MB / 5,000 objects) and creates a workspace layer (`layer.survey = NULL`,
  `layer.organization = org`), its Data row as `public`, a `DatasetLink(survey=canonical)` and a
  placement. A GeoJSON in WGS 84 keeps the survey's own parser (its properties stay JSON values,
  as every existing layer was built); a projected GeoJSON and GPKG / zipped SHP / KML / CSV go
  through the Data import's reader (`data.imports.open_source`, reprojected). Nothing above the
  survey cap can be linked into a survey anyway, so there is no background path from the survey
  (implementation note, 2026-11-24).
- `layers_for(survey)` becomes links (any `public` layer dataset) + the survey's own
  `source='question'` layers. Upload layers are no longer survey-owned.
- Settings card → **"Layers used here"**: name, objects, where shown, *Open in Data*, *Remove from
  this survey* (unlinks and unplaces; the dataset stays). Style and object editing open the same
  editors as today, now addressed through the dataset.
- Deleting a survey no longer deletes its uploaded layers; they stay in Data with an empty "Used
  by". The survey delete confirmation says so.

*Alternative:* keep survey ownership and only mirror in Data (rejected by the owner, 2026-11-24:
"слои живут в Data").

### D5. The study area is a survey-level object
`StudyArea(survey → canonical SurveyHeader, one-to-one; geometry MultiPolygon 4326; source:
'place' | 'upload' | 'layer' | 'draw'; place_name; osm_ref; fog bool default true;
refuse_outside bool default false; message TextField; refused_marks counter)`. It is never a
`SurveyMapLayer` and never in `layers_for`. Edits apply in place on a live survey (D2's reasoning;
turning `refuse_outside` on affects only answers submitted afterwards). The message is creator
text: plain, escaped on render, and an occurrence in the translation table
(`survey:study_area_message`). Geometry is simplified to ≤2,000 vertices
(`ST_SimplifyPreserveTopology`) on save.

### D6. Respondent map: open on the area, fog outside, legend from placements
- Metadata gains `study_area` (GeoJSON, fog, refuse, message) next to the layer list; it is small
  enough to inline (≤2,000 vertices), unlike layer geometry.
- First view: a section whose saved start position lies inside the area keeps it; otherwise the
  map fits the area. The map-start chain for a NEW survey gets a `study_area` rung first.
- Fog: an inverted polygon (world ring minus the area) in its own pane above tiles and below
  reference layers, near-opaque light fill (≈0.85) with a soft edge; the area outline on top.
- Legend: the panel's "On this map" block lists the section's placed layers (swatch, name,
  toggle wired to the layers control), in placement order — replacing legend-only questions.

### D7. Refusing answers outside
- Browser: the draw/crosshair handlers test the candidate geometry against the area
  (`turf`-free: point-in-polygon and segment checks in a small `study_area.js`); outside → nothing
  is placed and the message shows. Spray dots outside the area are dropped as they are painted.
- Server: in the section POST, when `refuse_outside` is on, a point must be within the area, a
  line or polygon covered by the area buffered 5 m (snapping tolerance), checked in PostGIS
  (`ST_CoveredBy` on geography-buffered area, one query per section). A refused chunk is skipped
  like an unreadable one, logged with the question code, and counted on `refused_marks`; spray
  clouds are clipped, not refused. Layer-object answers are not checked (the creator placed them).

### D8. Boundary from a place name
Editor-only endpoint `editor_study_area_lookup(q)` → Nominatim `search?format=jsonv2&
polygon_geojson=1&polygon_threshold=0.0005&limit=5` with the project User-Agent, server-side,
cached 30 days by query, behind `limits.hit(user, 'study_area_lookup')` (Nominatim policy: ≤1
request/s, no bulk). Up to five candidates are offered (name, type, area). What a candidate
becomes depends on the geometry Nominatim returns (owner, 2026-11-24):
- Polygon / MultiPolygon → used as is.
- LineString / MultiLineString (a street, river, rail line) → a corridor: `ST_Buffer` on
  geography by the picked width (50 / 100 / 200 m, default 100 m) with round ends and joins,
  simplified like any boundary. Width changes rebuild the polygon through the same endpoint
  (`?osm_ref=…&width=…`, served from the cache). A street that OpenStreetMap splits into several
  ways comes back as the matched way only; the creator extends it by editing vertices (the
  candidate says "one segment of the street" when the way is shorter than 300 m).
- Point → a rectangle: the Nominatim `boundingbox` when it is larger than 100 m across, otherwise
  500 × 500 m centred on the point; labelled "no boundary in OpenStreetMap".
The chosen polygon goes into the editor (Leaflet.draw edit mode: move, add, remove vertices) and is
saved only on Done. Attribution "© OpenStreetMap contributors" shows in the editor. Respondent
pages never call it.

### D8a. The outline on Responses and Reports (owner, 2026-11-24: in this change, outline only)
- Responses map (`analytics_geo_map.html`): the outline is a non-interactive Leaflet layer under the
  answers, styled by the study-area style token (no fog), listed "Study area" in the layers control.
  Geometry comes from the gated study-area endpoint, not inlined (map-layers rule).
- Reports: `render` adds `payload['study_area']` (simplified GeoJSON, ≤2,000 vertices) when the
  block's own question's canonical survey has an area and `config.study_area` is not `False`;
  `story.clean_config('map')` keeps the key (default never stored). The shared renderer draws it
  under every layer; `pdf.map_image` paints it after the basemap and before the layers; the PNG goes
  through `map_image`. It does not take part in `_extent` (the frame stays the data's or the kept
  one) or in `checks`. REST/MCP `update_block` accept `study_area` (bool) under the same strict rule;
  `get_report` returns it. The study area of other layers' surveys is not drawn (one outline per map).

### D8b. The Wizard sets the study area (owner, 2026-11-24: always, with handles)
- Create page: after the map is aimed at a place (brief prefill or a search result) the page asks
  an org-level endpoint `editor_place_boundary(q)` — the same `study_area_lookup.search` +
  `candidate_outline` the study area editor uses, rate-limited the same way — for the first
  candidate's outline, and draws it on the create map with the respondent's fog. A "Study area"
  strip under the map names the place and holds the handles: *Edit outline* (Leaflet.draw vertex
  editing on the create map), corridor width for a street, *Allowed / Not allowed* outside, and
  *Remove*. Hidden fields carry `study_area_mode` (`auto` | `set` | `off`), `study_area_geometry`
  (GeoJSON), `study_area_place`, `study_area_osm_ref`, `study_area_refuse`.
- Prefill: every capitalised candidate is geocoded (Photon, in parallel) and the best-ranked type
  wins (country > state > city/town > district > street > anything else), not the first hit:
  "Снега" (a point near Arkhyz) no longer beats "Санкт-Петербург".
- Generation (`generate_survey_draft(…, study_area=…)`): `set` → the posted outline; `auto` → the
  model's `location` looked up (first candidate; a street as a 100 m corridor, a point as a
  rectangle); `off` → nothing. The lookup runs outside the materialize transaction; the area is
  set after it through `services.study_area.set_area(actor=None…)`; any failure is logged and
  ignored. The empty-survey path of the same page applies `set` the same way.

### D9. Publish check
The publish confirmation (and "Publish changes") lists the study area (source, area, rules) and
each linked layer (use: shown / asked in section N, scope), and flags a layer that is linked but on
no map with inline *Show on every section* / *Remove*. Warnings never block publishing. When the
survey has `opens_at` in the future, the dialog says the public link shows the "opens on" page and
offers *Preview as a respondent* (the editor preview, which ignores the schedule).

### D10. Parity and events
Services: `survey/services/placements.py` (place, unplace, set_scope, reorder) and
`survey/services/study_area.py` (set, update, clear); editor views, REST v1
(`/surveys/{uuid}/layers/{id}/placement`, `/surveys/{uuid}/study-area`) and MCP tools
(`place_layer`, `unplace_layer`, `get_study_area`, `set_study_area`, `clear_study_area`) call them.
Creator events: `layer_added {source, surface}`, `layer_placed {scope, auto}`,
`study_area_set {source, edited, refuse_outside, fog}`, `publish_check_shown {layer_warnings}`.
Nothing on respondent pages.

## Risks / Trade-offs

- [Two in-flight changes touch the same requirements] → archive `layers-by-question` first
  (its 6 open tasks: 0.1/0.2 done in practice, 1.4 `hidden_layers` drop and 4.1 move into this
  change); otherwise our MODIFIED headers will not apply (archive trap).
- [Ownership move of 87 layers] → done by a data migration that creates the `DatasetLink`s in the
  same transaction, so old code in the deploy window still finds every layer through
  `layers_for`'s link branch.
- [Deleting legend-only questions while old code runs] → two releases: PR 1 creates placements
  and stops reading `panel_mode`/legend questions (they stay in the DB, hidden); PR 2 deletes them
  and drops `panel_mode` and `hidden_layers`.
- [Nominatim availability / policy] → creator-initiated, cached, rate-limited; failure shows "Could
  not reach OpenStreetMap — upload or draw instead". No respondent dependency.
- [A strict server check refuses honest marks on the boundary] → 5 m tolerance, and the client
  check uses the same rule so the respondent sees the refusal before submitting.
- [Surveys deleted keep their layers in Data] → stated in the delete dialog; Data shows "Used by:
  nothing" and offers delete.
- [Progress / required semantics] → legend-only questions never counted (no sub-questions), so
  progress is unchanged.

## Migration Plan

1. Archive `layers-by-question` (sync its deltas into main specs).
2. **PR 1** — models `LayerPlacement`, `StudyArea`; data migration: (a) every top-level
   `layer_objects` question of a canonical map section → placement of its layer on that section
   (scope `all` when the layer ends up on every map section); (b) upload layers move to the
   workspace with a `DatasetLink` per canonical survey and a `public` Data row; code reads
   placements, links and the study area; Map card, study area editor, publish check, API/MCP, help
   pages, changelog card.
3. **PR 2** (next release) — delete legend-only Objects questions in every header; drop
   `Question.panel_mode` and `SurveySection.hidden_layers`.
4. Rollback of PR 1: revert; placements and study areas are ignored by old code, legend-only
   questions still exist, links keep layers reachable.

## Open Questions

1. ~~A place with no OSM polygon~~ — decided 2026-11-24: a line result becomes a buffered
   corridor, a point result a rectangle around the point (D8).
2. ~~A map in form sections~~ — decided 2026-11-24: no; a section without a map shows no map,
   scope `all` covers map sections only, placed layers start switched on.
3. ~~Study area on Responses and Reports~~ — decided 2026-11-24: in this change, outline only (D8a).
