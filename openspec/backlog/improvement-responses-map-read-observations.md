# Reading the observations off the Responses map without GIS software

**Type**: improvement
**Priority**: high
**Area**: frontend
**Created**: 2026-08-24
**Epic**: survey-analytics
**Related**: [Interactive Analytics Map](feature-interactive-analytics-map.md) (#116, shipped),
[One geo question already accepts many features](improvement-multi-geometry-discoverability.md) (#103),
[Shapefile and GeoPackage export](feature-shapefile-geopackage-export.md) (#8)

## Description

A creator with no GIS background cannot read their own map answers in the product. The
markings are on the Responses map, the comments attached to them are in the GeoJSON, and
nothing joins the two on screen.

**Source — a Nordic municipal customer, 2026-08-24** (details in the private outreach notes).
Running a light-pollution study for the municipality: demographics plus a `point` question with
sub-questions for the observations.

Her account, in summary: she assumed the data could not be exported in a form reviewable without
GIS software, and used an LLM to assemble a compilation showing **every map marking placed and
the comments attached to it**.

She did not report this as a problem. She concluded the feature did not exist, rebuilt it by hand
in a third-party tool, and mentioned it in passing as already solved — the pattern in
[[lesson-authors-workaround-silently]]. Her role is municipal communications, which is the modal
buyer persona, not an edge case.

## What is actually there today

`survey/templates/editor/partials/analytics_geo_map.html`:

- Clicking a feature does **nothing visible** in the default `pointer` tool mode — it sets the
  cross-filter selection. To see any content you must first find the ⓘ button in the map
  toolbar and switch `window.geoToolMode` to `details` (line 102). A creator who clicks a pin
  expecting to see what that pin says gets silence.
- Even in `details` mode the modal is per **session** (`openSessionDetailModal` → global
  `loadSessionDetail`, line 370), not per **feature**. When one session placed several markings —
  which one geo question fully supports (#103) — the modal cannot say which pin was clicked or
  what that pin's own sub-answers were. That is precisely the marking→comment join Maria wanted.
- No popup, no tooltip, no hover state. `featureLayer` binds only a click handler.
- No flat list of features anywhere. The Responses table is per session; the map is per feature;
  neither shows a marking next to its comments.

On the export side the same gap is structural rather than cosmetic: `EXPORT_GEOMETRY_TYPES`
(`survey/views.py:1211`) sends geometry out **only** as GeoJSON layers, "never as a cell", so
the CSV a non-GIS creator opens holds every answer except the ones the survey exists to collect.

## What it needs

1. **A popup on the feature itself.** Click a marking in the default pointer mode and get its own
   sub-answers, in the creator's own question wording, without a mode switch. Selection and
   inspection both being bound to plain click is the conflict to resolve — Ctrl+click already
   means "add to selection", so plain click can reasonably become "inspect".
2. **Per-feature identity in the detail view.** When a session has several markings, the detail
   view must open on the one clicked and let you page through the rest of that session's.
3. **A feature list beside the map.** One row per marking: layer, lat/lon, sub-answers, session.
   Filtered by the map selection so a rectangle-select yields a readable list of what is inside it.
4. **CSV of that list.** The one-click version of what she assembled by hand. This is the piece
   that closes the "not reviewable without GIS software" complaint at its root, and it belongs
   next to the list, not buried in the ZIP export.

## Notes

- Point 4 overlaps the export epic but is deliberately scoped here: she never wanted a GIS file
  in a better format (#8), she wanted a table she could read. Shapefile/GeoPackage serve the GIS
  professionals; this serves everyone else.
- #116 shipped layer toggles, heat, rectangle/polygon spatial filtering and zoom-to-layer — the
  analysis half of "feature inspection". The reading half was specified in that item ("click a
  point or geometry to view all answers from that session") and landed as a session modal behind
  a tool mode, which is why the gap survived a shipped feature.
- Sequencing: 1 and 2 are small and inside one template; 3 and 4 need an endpoint that flattens
  features to rows, which is the same shape the CSV needs. Do 1+2 first — that alone would have
  changed her experience.
- The customer has offered fuller feedback once her survey closes. Worth asking specifically what
  her hand-built compilation looked like before designing the list columns.
