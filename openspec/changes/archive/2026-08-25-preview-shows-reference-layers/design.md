# Design: preview-shows-reference-layers

## Context

Two views render `survey_section.html`: `views.survey_section` (respondent) and
`editor_views.editor_section_preview` (iframe in the editor). Each assembles its own
context dictionary. `_build_map_layers_metadata(survey)` was added to the first only.

## Decisions

### D1. Share the helper, not the whole context

The preview imports `_build_map_layers_metadata` from `views` rather than growing its
own copy. One function decides what a layer looks like on the page, so the kill switch
and the URL shape cannot drift between the two surfaces.

Rejected: a context processor. It would run for every request including surfaces with
no map, and it would hide the coupling instead of naming it.

### D2. The preview honours per-section visibility

A layer hidden on this section is hidden in its preview too — otherwise the preview
answers a different question than the one the creator is asking ("what will people see
here?"). Same `hidden_layers_json` shape the respondent partial uses.

### D3. Access to the geometry endpoint is already correct

The preview iframe fetches `/surveys/<uuid>/layers/<id>.geojson` like the respondent
page. Editors and owners bypass `check_survey_access`, so a draft survey's layers load
in the preview while staying invisible to the public. No change needed — worth stating
because the endpoint's 404-on-denial makes a permissions mistake look like a missing
layer.

## Risks / Trade-offs

The preview now issues the same layer fetches as a respondent page; for a large layer
that is one extra download per preview render. Acceptable: the alternative is a preview
that lies.

## Open Questions

None.
