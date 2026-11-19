## ADDED Requirements

### Requirement: Map and cross-tab settings through the API and MCP
The system SHALL let REST API v1 (`POST /api/v1/reports/{uuid}/blocks`,
`PATCH /api/v1/reports/{uuid}/blocks/{id}`) and the MCP tools `add_report_block` and
`update_report_block` write every setting of a map block the report editor writes — `view`
(heat | hotspots | squares | marks), the view's `opts`, `color`, `name`, `frame`
([west, south, east, north]; `null` clears it), `legend`, `scale`, `toggle`, `basemap`,
`popup_fields` and `layers` (the whole list of the other map questions on the same map, at most
3, each with its own survey, question, view, marks, colour, name, options and popup fields) — and
the `display` of a cross-tab block (`view` bars | stacked | ranking | table, `values` percent |
count, `sort`). Every write SHALL go through the editor's block service, so what is stored is what
the editor would store.

Where the editor drops a value it cannot use, the API SHALL refuse with `422 validation` naming
the field: an unknown view or option value; hot spots on a question that is not a point question;
a layer that is not a map question of the report's workspace, that is the block's own question, or
that comes twice; more than 3 layers; a frame outside the world; a basemap the workspace does not
offer; a popup field that is not a non-text sub-question of the layer's question; the Marks view
with `show_marks` false. A refused write SHALL change nothing.

A layer without a survey SHALL read the block's own survey. The server SHALL assign a new layer
its id, and a layer sent with the id it already has SHALL keep it. A layer SHALL be accepted with
the names `get_report` returns (`code`, `marks`, `fields`) as well as with the block's input names
(`question`, `show_marks`, `popup_fields`). A free-text sub-question SHALL NOT reach a map popup
through the API or the editor.

#### Scenario: An agent rebuilds a map of two layers
- **WHEN** a token adds a map block of a point question with `view` hotspots, `opts` {top: 10}, a frame, `toggle` true and one layer of a line question of the same survey with `view` squares and colour `#0f766e`
- **THEN** the block's config holds those values, the layer has a server-assigned id, and `get_report` returns them

#### Scenario: Sending back what was read
- **WHEN** the token sends the `layers` list exactly as `get_report` returned it, plus a changed `name` on the first layer
- **THEN** the layer keeps its id and its other settings, and its name is the new one

#### Scenario: Clearing the frame
- **WHEN** the token patches a map block with `frame: null`
- **THEN** the block has no kept frame and its other settings are unchanged

#### Scenario: Strict where the editor is forgiving
- **WHEN** the token sends hot spots for a line question, a layer naming a question code the survey lacks, the block's own question as a layer, four layers, an unknown `opts.spread`, a frame with west greater than east, or a text sub-question as a popup field
- **THEN** each answer is 422 naming the field, and the block is as it was

#### Scenario: A cross-tab's look
- **WHEN** the token patches a cross-tab block with `display` {view: ranking, values: count}
- **THEN** the block is drawn as a ranking of counts and `get_report` returns that display

#### Scenario: The same through MCP
- **WHEN** an agent calls `update_report_block` with `view` heat and `opts` {spread: wide, strength: 5}
- **THEN** the block's config holds them, and `tools/list` describes the map settings on both block tools
