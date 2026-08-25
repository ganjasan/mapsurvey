# Proposal: preview-shows-reference-layers

## Why

The editor's live preview renders the respondent page without reference overlay layers,
so a creator who has just uploaded a zone layer sees an empty map and concludes the
upload failed. Reported immediately after the feature reached production (2026-08-25).

`editor_section_preview` renders the same `survey_section.html` shell as the respondent
view but builds its own context, and reference layers were only added to the respondent
path. The shell's `{{ map_layers|json_script:"ref-layers-data" }}` therefore receives
nothing, and the widget script correctly does nothing with an empty list.

This is the general hazard of two views rendering one template from two hand-built
contexts: anything added to one silently disappears from the other, and only a human
looking at the preview notices.

## What Changes

- The section preview passes the survey's layer metadata and the section's hidden-layer
  list, so the preview map shows exactly what a respondent would see, including
  per-section visibility.
- A test asserts the preview carries layer config, so the next context key added to one
  path and not the other has a chance of being caught here.

## Capabilities

### Modified Capabilities

- `reference-overlay-layers`: the editor preview SHALL render the same layers, with the
  same per-section visibility, as the respondent page.

## Impact

- `survey/editor_views.py` — `editor_section_preview` context.
- `survey/tests.py` — preview rendering test.
- No migration, no model change.
