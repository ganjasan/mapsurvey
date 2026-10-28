## ADDED Requirements

### Requirement: The creator may keep the panel open while respondents place on the map
Each section SHALL carry `keep_panel_open`, off by default. When it is off, every placement
SHALL behave exactly as before this setting existed. When it is on, on a `map` section on a
desktop viewport:

- starting a placement or a drawing — the point crosshair, a line, an area, a spray cloud,
  editing or moving a placed feature, and tap-to-place — SHALL NOT hide the question panel;
- the crosshair, the point Apply places, the crosshair's Cancel/Apply buttons and the draw
  bar SHALL be centred on the visible map area: the viewport minus the open panel, on
  whichever side the panel sits and whatever its width;
- moving a placed point SHALL bring it to the centre of the visible map area, not of the
  viewport.

When the respondent hides the panel by hand, the whole viewport SHALL be the visible area.
Viewports below the mobile breakpoint (768 px) and `image` / `form` sections SHALL ignore the
setting. The setting SHALL follow HTMX navigation and be present in the first HTML of a
direct load.

#### Scenario: Default behaviour is unchanged
- **WHEN** a respondent on a desktop presses a point question on a section with
  `keep_panel_open` off
- **THEN** the panel slides away and the crosshair is centred on the viewport, as before

#### Scenario: Placing a point beside a right-hand panel
- **WHEN** a respondent on a desktop presses a point question on a section with
  `keep_panel_open` on and the panel on the right at half width, and presses Apply
- **THEN** the panel stays open, the crosshair sits in the middle of the left half, and the
  stored point is the map position under the crosshair's tip

#### Scenario: Drawing a line beside a left-hand panel
- **WHEN** a respondent presses a line question with `keep_panel_open` on and the default
  left panel
- **THEN** the panel stays open and the draw bar is centred on the map to the right of it

#### Scenario: Phones ignore it
- **WHEN** the same section is answered on a 390 px viewport
- **THEN** the panel slides away and the crosshair is centred on the screen, as before

### Requirement: Sub-question pop-ups open clear of the panel on either side
On a desktop viewport with the panel open, a sub-question pop-up's auto-pan SHALL keep the
pop-up clear of the panel on the side the panel sits (`panel_side`), whatever
`keep_panel_open` says.

#### Scenario: Pop-up beside a right-hand panel
- **WHEN** a respondent places a feature near the right edge of the map on a section with the
  panel on the right, and its sub-question pop-up opens
- **THEN** the map pans so the pop-up is fully left of the panel

## MODIFIED Requirements

### Requirement: Layout settings are safe edits and travel with the section
The layout settings SHALL be display settings — stage, panel side, panel width, content width,
content vertical alignment, keep-panel-open and the section picture: a change on a published or
closed survey applies in place without "Unpublished changes". The six values SHALL travel on
the draft copy, on duplicate and paste, in the ZIP backup and through the REST API and MCP
tools; the picture file SHALL be shared within one survey family and copied as a new file
across surveys (as `Question.image` is), and SHALL ride the ZIP backup beside the question
images. A ZIP without the new keys SHALL import with the defaults; a ZIP with an unknown value
SHALL import that field as its default.

#### Scenario: Live survey takes the edit in place
- **WHEN** an editor changes a published survey's section from `panel_side = "left"` to
  `"right"`, from `content_valign = "top"` to `"middle"`, or turns `keep_panel_open` on
- **THEN** the save succeeds without a draft and respondents see the change

#### Scenario: Draft copy keeps the layout
- **WHEN** unpublished changes are started on a survey whose head section is `image`,
  `right`, `half`, `column`, `middle` with a picture
- **THEN** the draft's head section carries the same six values and the same picture

#### Scenario: ZIP round trip
- **WHEN** a survey with an `image` / `right` / `half` / `column` / `middle` section carrying a
  picture, and a map section with `keep_panel_open` on, is exported and imported
- **THEN** the imported sections carry the six values and the picture

#### Scenario: Legacy archive
- **WHEN** a ZIP written before these settings existed is imported
- **THEN** every section imports with `panel_side = "left"`, `panel_width = "default"`,
  `content_width = "full"`, `content_valign = "top"`, `keep_panel_open` off and no picture

#### Scenario: API refuses an unknown preset
- **WHEN** `PATCH /api/v1/sections/{id}` carries `panel_width: "wide"` or
  `content_valign: "bottom"`
- **THEN** the response is `422 validation` naming that field

### Requirement: The section modal offers the layout controls where they apply
The section modal SHALL carry a Layout block with the stage, the panel side, the panel width,
the content width, the content vertical alignment, the keep-panel-open switch and the picture
upload. Side, width and the two content settings SHALL be shown only for `map` and `image`
stages, the keep-panel-open switch and the Map position button only for `map`, the picture
upload only for `image`; switching the stage in the modal SHALL show and hide them without a
save. The block SHALL be editable on a live survey (content controls, not structural ones).

#### Scenario: Picking the image stage reveals the upload
- **WHEN** a creator switches a section's stage from Map to Image in the modal
- **THEN** the picture upload, the side and width controls and the two content controls are
  visible, and the Map position button and the keep-panel-open switch are hidden, before any
  save

#### Scenario: Form stage hides side and width
- **WHEN** a creator switches the stage to Form
- **THEN** the side, width, content, keep-panel-open and picture controls are hidden
