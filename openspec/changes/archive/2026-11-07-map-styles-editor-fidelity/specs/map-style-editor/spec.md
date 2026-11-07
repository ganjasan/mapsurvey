## MODIFIED Requirements

### Requirement: The editor page edits a workspace style with bounded controls
`/org/<slug>/map-styles/<uuid>/edit/` SHALL open for owners, admins and editors of the workspace that owns the style, SHALL answer 404 for a preset or another workspace's style, and SHALL render exactly the controls of `survey/map_styles/controls.py`: removals (POI, paths, shields, relief, regions), buildings with a "show from zoom" slider (13–17), land / park / water / boundary and label colours as swatch palettes whose code opens a colour picker, road look presets, bold street names, place-name zoom limit, greyscale. Every control SHALL have a base state that leaves the base style as it is — an empty colour (whose code shows, muted, the colour the base itself draws for that role), roads "As base", place names "no limit", buildings from zoom 15 — and the form SHALL show a style exactly as its settings document says, so a copy of Streets shows Streets. A road triple matching no preset SHALL show as a checked "Custom" option and SHALL be kept. A posted settings document SHALL be cleaned against the same schema: unknown keys dropped, colours `#rrggbb` only, enumerations enforced, and a control in its base state SHALL add no key. The preview bar SHALL carry the shared place search; a chosen place SHALL move the preview and the Print frame until another survey frame is picked.

#### Scenario: Editor opens for an editor
- **WHEN** a member with the editor role opens the editor of the workspace's style
- **THEN** the page renders the style's name and every control with the values of the latest version's settings

#### Scenario: Presets and foreign styles have no editor
- **WHEN** the editor URL names a preset or a style of another workspace
- **THEN** the response is 404

#### Scenario: Settings are cleaned
- **WHEN** a save posts `{"park": "red", "foo": 1, "roads": "strong", "place_names_maxzoom": 40}`
- **THEN** `park` is refused with a field error, `foo` is dropped, `roads` becomes the strong preset's triple and `place_names_maxzoom` is clamped to "no limit", which writes no key

#### Scenario: Streets copy stays Streets
- **WHEN** a style whose settings document is empty is opened and saved untouched
- **THEN** every colour code shows the base's own colour, muted, roads are "As base", place names "no limit", and the saved document is empty

#### Scenario: Buildings from a chosen zoom
- **WHEN** the creator moves the buildings slider to 13 on an otherwise untouched style
- **THEN** the document is `{"buildings": {"minzoom": 13}}` and the generator starts the building layer at 13 with the base's colours

#### Scenario: Custom roads are kept
- **WHEN** a style whose roads match no preset (Paper B's) is opened and saved
- **THEN** a checked "Custom" road option is shown and the triple is saved unchanged

#### Scenario: Colour code is a picker and the bar has a search
- **WHEN** the editor page renders
- **THEN** each colour code is an `<input type="color">` and the preview bar carries the place search control
