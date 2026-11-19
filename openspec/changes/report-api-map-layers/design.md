## Context

`reports.blocks` turns an API/MCP spec dict into the calls the editor makes on
`reports.services`. For a map it passes only `show_marks` and the description, although
`services.update_block` already takes `map_display` (view, frame, color, name, opts, legend,
scale, toggle, layers) and `crosstab_display`, and `story.clean_config` cleans them. The editor is
forgiving by design — a bad value is dropped, `_checked_layers` drops a layer it cannot resolve —
because a form never sends anything the panel did not offer. An API client can send anything, and
a silently dropped value is a bug the agent cannot see.

## Goals / Non-Goals

**Goals:** every key `files.entry_of` writes for a map or cross-tab is writable; one write path
with the editor; one rule for "a layer this map may have"; refusals that name the field.

**Non-Goals:** changing what `get_report` returns or the report file; context layers from Data;
filters by sub-question; image uploads.

## Decisions

1. **Schema validation first, rule checks second, the service last.** Value domains (views,
   option values, colour pattern, frame length, ≤ 3 layers) are pydantic `Literal`s and
   constraints on new `MapOptsIn` / `MapLayerIn` / `CrosstabDisplayIn` schemas — ninja already
   turns them into `422 validation` naming the field, and MCP inlines the same schemas. What needs
   the database (question types, workspace, sub-questions, basemaps) is checked in
   `reports.blocks._map_settings(block, spec)` before any write; it raises `BlockRefused(field)`.
   Only then is `services.update_block(map_display=…)` called, so a refusal writes nothing. On
   `add`, a refused map spec deletes the just-made block (the existing rollback in `blocks.add`).

2. **One rule for a layer.** `services.layer_refusal(block, layer, seen)` returns
   `(message, key, question)`: it is what `_checked_layers` already did inline (map question of the
   workspace, by canonical survey + code, never the block's own, never twice). `_checked_layers`
   keeps dropping on a refusal (editor); `blocks` raises it (API). The hot-spots-needs-a-point
   rule (`story.map_view`'s fallback) is checked in `blocks` for the block's own question and each
   layer.

3. **Layer names.** The block's input already says `question` / `show_marks` (and now
   `popup_fields`), while the report file — hence `get_report` — says `code` / `marks` / `fields`
   inside `layers`. `MapLayerIn` uses the input names and accepts the file names as
   `AliasChoices`, so reading a map and writing it back works without a translation step on the
   agent's side. `blocks` converts to the config dialect (`code`, `marks`, `fields`).

4. **Ids.** A layer with an `id` that is one of the block's current layer ids keeps it; any other
   layer (no id, or an unknown one) gets the first free id of `a…h`, as the editor's "add layer"
   does. A layer without `view` gets `heat`, the editor's default for an added layer.

5. **Replace, not merge.** `opts` and `layers` replace what is stored, as the editor's form does;
   the tool descriptions say so ("send the whole set; read it from get_report"). Keys of the map
   left out of a PATCH stay, because `update_block` only touches the keys `map_display` names.

6. **Popup fields.** The non-text sub-questions a popup may show move from
   `editor_views._geo_subquestions` to `reports.sources.popup_subquestions(question_ids)`; the
   editor imports it, `blocks` validates `popup_fields` (block and layers) against it. Free text
   stays out of popups on both surfaces.

7. **Basemap.** Validated against `survey.basemaps.choices_for(organization)` and passed with
   `valid_basemaps`, as the editor does.

## Risks / Trade-offs

- [Aliases in a strict schema] → covered by a round-trip test (send `get_report`'s `layers` back).
- [MCP `args_model` inlining nested schemas with aliases] → MCP test calls the tool with nested
  `opts` and `layers`; `tools/list` snapshot via the generated reference.
