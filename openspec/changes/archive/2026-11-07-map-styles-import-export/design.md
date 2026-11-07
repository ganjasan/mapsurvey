## Context

`MapStyleVersion.settings` is the generator's document; `survey/map_styles/controls.py::clean_settings(form_values(settings))` turns any document into the bounded one the editor allows. Duplicate (#542) already creates a workspace style from a settings document and publishes it in the background. Export and import are that path with a file in between.

## Goals / Non-Goals

**Goals**: a one-file format that survives a round trip and carries nothing environment-specific; import that cannot widen what the editor allows; the same background publishing and Pro rules as Duplicate.

**Non-Goals**: bulk import, importing Mapbox Studio styles, API/MCP endpoints (v1.1), the catalogue (v2.0).

## Decisions

### D1. Format
```json
{"format": "mapsurvey-map-style", "version": 1, "name": "House style",
 "base": "mapbox/streets-v12", "settings": {…}, "exported_at": "2026-11-07T03:40:00Z"}
```
`format` and `version` let a later reader refuse or upgrade; `base` names the style the settings apply to (only `mapbox/streets-v12` today, so an import with another base is refused rather than silently rebased); `settings` is the generator's document as stored. No `uuid`, no `mapbox_style_id`, no workspace: the file means the same thing everywhere. Pretty-printed, sorted keys, so a diff between two exports reads.

### D2. Import normalises through the control schema
`io.parse_document(bytes)` → `(name, base, settings)` or a list of errors: size ≤ 64 KB, JSON object, `format` exact, `version` ≤ 1, `name` non-empty ≤ 120, `base` supported, `settings` an object. The settings are then passed through `controls.clean_settings(controls.form_values(settings))`: keys the editor does not know are dropped, colours and enumerations enforced. A hand-edited file that tries `"layers": [...]` loses that key quietly; a bad colour is an error the page names.

### D3. Names
`io.unique_name(org, name)`: the name as is when free, else `name (2)`, `name (3)`, … against the workspace's non-archived styles.

### D4. Gates and events
Import = `trial.use(org, 'map_styles')` at the moment the row is created (a created style, like Duplicate); export = `trial.may(org, 'map_styles')` (the feature in force, nothing spent). Roles owner/admin/editor for both. Events `map_style_imported` (`{organization_id, style_id}`), `map_style_exported` (`{organization_id, style_id, preset}`), ids only.

### D5. Export of presets
Streets, Paper A and Paper B export (their settings documents are what the script publishes them from); Satellite and Topo answer 404 like Duplicate hides them. A preset's export carries `"preset": "paper"` so a reader knows where it came from; import ignores the key.

## Risks / Trade-offs

- [Someone imports hundreds of files] → each is one Pro trial use or a Pro workspace's own quota of Mapbox writes; the queue paces publishing at 40/min.
- [A future format version] → `version` > 1 is refused with a clear message; readers upgrade documents when the time comes.

## Migration Plan

None.
