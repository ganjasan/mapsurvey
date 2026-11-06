## Why

An operator who typed in a paper sheet (or whose sheet was imported from scans) cannot correct it
from Responses (#527, epic #350). The response drawer and the per-response map modal are
read-only and nothing links back to the entry form. The concrete case: points, lines and polygons
transcribed from paper maps land a few metres off or on the wrong question, and the operator needs
to move, reshape, delete or re-label them while looking at the scan.

The entry form itself already does the job: addressed by URL
(`/editor/surveys/<uuid>/responses/enter/<session_id>/<section>/`) it opens an existing operator
session with every saved answer, geo features and their pop-up sub-answers included, and
re-saving a section unchanged keeps them unchanged. Only the way in, and the way back, are missing.

## What Changes

- **Edit from the drawer.** On an operator session (`source != 'online'`), for an `editor`+ while
  the workspace holds `operator_entry`, the drawer header gets **Edit response**, which opens the
  entry form at the session's first visible section; every answer row's section name links to the
  entry form at that section. Online sessions show neither.
- **Edit from the map.** The per-response map modal gets **Edit on the map** in its header (the
  section of the object it was opened on, else of the first object), and each object's pop-up
  carries the same link for its own section.
- **Return mode.** An entry URL opened from Responses carries `?return_to=response|map`. The form
  then shows **Save and return to Responses** next to Back/Next, keeps the marker on every
  section it navigates to, and points *Stop* back at the response. The button saves the current
  section only and lands on Responses with that response open in the drawer
  (`?session=<id>`), and for `map` with its full-size map open again.
- **Responses opens a response by URL.** `?session=<id>` on the Responses page opens that
  response in the drawer on load (the comment deep link already produced such URLs; only the
  `#thread-` form was honoured).
- **Audit.** Saving a section of an operator session that is already completed writes
  `AuditLog(action='response_edit')` with the session id and section — ids only. A first entry is
  not an edit and writes nothing new.
- **Tests** pin the geometry edits the form makes on features that came from the database —
  moved point, reshaped line and polygon, deleted feature, changed pop-up sub-answer — and that a
  section re-posted exactly as the form renders it keeps every answer value.

## Capabilities

### New Capabilities

### Modified Capabilities
- `operator-entry`: ways into the entry form from the drawer and the map modal, return mode,
  the edit audit, and the guarantees about editing stored geometry.
- `responses-detail-drawer`: the Responses page opens a response from `?session=<id>`.

## Impact

- `survey/operator_entry_views.py` — return mode (`return_to`), `nav_direction=return`,
  `response_edit` audit, `edit_links()` for the drawer.
- `survey/analytics_views.py::analytics_session_detail` — edit URLs on rows and geo features.
- Templates: `analytics_session_detail.html`, `analytics_dashboard_v2.html` (map modal button,
  pop-up link, `?session=` opener), `partials/survey_section_partial.html` (return button),
  `editor/operator_entry/_entry_bar.html` (unchanged markup, new href).
- `AuditLog.ACTION_CHOICES` + `response_edit` → migration `0114` (choices only).
- Catalogs: four new creator strings in every maintained catalog.
- No change to the respondent page, the section writer or any respondent-facing behaviour.
- Overlaps PR #511 (paper-photo-entry) in `operator_entry_views.py` and the drawer template; the
  edits are additive and that PR's migration `0113_paper_photo_entry` already has to renumber.
