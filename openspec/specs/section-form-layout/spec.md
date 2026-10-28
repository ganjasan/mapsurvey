# section-form-layout Specification

## Purpose
A survey section can opt out of the map and render as a classic full-width form (Google Forms style). Covers respondent rendering of both layout modes, mode switching across HTMX navigation, the creator-named forward button, and the mutual exclusion of geo questions and form layout.
## Requirements
### Requirement: A form-layout section renders as a full-width classic form
A section's `layout` SHALL name its STAGE — what fills the part of the screen the question
panel does not: `map` (the default), `form` or `image`.

When a section has `layout = "form"`, the respondent page SHALL render that section as a
centered full-width form — questions stacked down the page — with the map and all
map-coupled chrome (draw bar, crosshair, basemap switcher, panel-hide button) hidden.

When a section has `layout = "image"`, the respondent page SHALL render the question panel as
a column beside a picture that fills the rest of the viewport (see "An image stage shows the
section's picture"), with the map and all map-coupled chrome hidden exactly as on a `form`
section. The panel SHALL NOT be hideable on an `image` section (there is nothing to reveal).

Sections with `layout = "map"` (the default, and any unrecognized stored value) SHALL render
exactly as before this change when `panel_side` and `panel_width` keep their defaults.

#### Scenario: Form section hides the map
- **WHEN** a respondent opens a section with `layout = "form"`
- **THEN** the question panel spans the page as a centered column and the map is not visible

#### Scenario: Image section hides the map and keeps the column
- **WHEN** a respondent opens a section with `layout = "image"`
- **THEN** the map, draw bar, crosshair and panel-hide/show buttons are not visible, and the
  question panel is a column beside the picture, not a centered card

#### Scenario: Map section is unchanged
- **WHEN** a respondent opens a section with `layout = "map"`, `panel_side = "left"` and
  `panel_width = "default"`
- **THEN** the panel-beside-map rendering is byte-identical to the pre-change output

### Requirement: Layout mode follows HTMX navigation in both directions
The page SHALL switch mode without a reload and without destroying the persistent map
instance when a respondent navigates between sections of different stages, panel sides or
panel widths: map → form/image hides the map, form/image → map restores it with its previous
state, and the panel side and width classes follow the section being shown.

#### Scenario: Welcome form into map section
- **WHEN** a respondent submits a `form` head section whose next section is `layout = "map"`
- **THEN** the map appears with the survey's start position without a full page load

#### Scenario: Image welcome into map section
- **WHEN** a respondent submits an `image` head section with `panel_side = "right"` whose next
  section is a `map` section with `panel_side = "left"`
- **THEN** the picture disappears, the map appears with the survey's start position, and the
  panel moves to the left without a full page load

#### Scenario: Back navigation restores form mode
- **WHEN** a respondent on a `map` section navigates back to a `form` section
- **THEN** the map is hidden again and the form renders full-width

#### Scenario: Direct load of a form section has no map flash
- **WHEN** a respondent loads a `form` or `image` section's URL directly
- **THEN** the initial server-rendered HTML already carries that section's stage, side and
  width — the map is never visible, not merely hidden after scripts run

### Requirement: Geolocation is not requested on a form section
The browser geolocation prompt SHALL NOT be triggered while a section without a map (`form`
or `image`) is active, even when the survey or section has geolocation enabled.

#### Scenario: Welcome page asks for nothing
- **WHEN** a respondent opens a `form` or `image` head section of a survey with
  `use_geolocation = true`
- **THEN** no geolocation permission prompt appears until a `map` section is shown

### Requirement: The forward button label is the creator's to name
Each section SHALL accept an optional creator-defined forward-button label (with
per-language translations); when set, it SHALL replace the default Next/Finish label for
that section. Empty SHALL mean the existing defaults — no label is ever inferred from the
section's position or layout.

#### Scenario: Welcome page gets a Start button by authorship
- **WHEN** the creator sets the head section's button label to "Start"
- **THEN** the rendered forward button reads "Start"

#### Scenario: No custom label means the old defaults
- **WHEN** a section has no custom label
- **THEN** the button reads "Next" (or "Finish" on the last section) exactly as before

#### Scenario: The label follows the respondent's language
- **WHEN** a section's label has a translation for the respondent's selected language
- **THEN** the translated label renders

### Requirement: Geo questions and form layout exclude each other
A section without a map (`form` or `image`) SHALL NOT contain geo questions (`point`, `line`,
`polygon`, `spraycan`). The system SHALL enforce this at question creation/save time and at
layout-switch time, from ONE definition of the map-less stages shared by the section form,
the question form and the editor's type picker; there is no rendering fallback for a geo
question inside such a section because the state is unreachable through the product.

#### Scenario: Geo question rejected in a form section
- **WHEN** a request tries to save a `point` question into a section with `layout = "form"`
- **THEN** the save is refused with an error

#### Scenario: Geo question rejected in an image section
- **WHEN** a request tries to save a `point` question into a section with `layout = "image"`
- **THEN** the save is refused with the same error

#### Scenario: Spraycan question rejected in a form section
- **WHEN** a request tries to save a `spraycan` question into a section with `layout = "form"`
- **THEN** the save is refused with the same error

#### Scenario: Layout switch refused while geo questions exist
- **WHEN** a creator tries to set `layout = "form"` or `layout = "image"` on a section
  containing a `polygon` question
- **THEN** the change is refused with a message naming the blocking questions

### Requirement: An image stage shows the section's picture
An `image` section SHALL fill its stage with the section's own picture
(`SurveySection.stage_image`) when one is uploaded, else the survey's `cover_image`, scaled
to cover the stage without distortion. When neither exists the stage SHALL render as a plain
tinted area (the survey's accent colour when set, else the page's neutral panel tint) — never
a broken image.

#### Scenario: Section picture wins
- **WHEN** an `image` section has a `stage_image` and the survey has a `cover_image`
- **THEN** the stage shows the section's picture

#### Scenario: Survey cover as the fallback
- **WHEN** an `image` section has no `stage_image` and the survey has a `cover_image`
- **THEN** the stage shows the survey's cover

#### Scenario: No picture at all
- **WHEN** an `image` section has no `stage_image` and the survey has no `cover_image`
- **THEN** the stage is a tinted area and the page contains no `<img>` with an empty source

### Requirement: The creator chooses which side the panel sits on
Each section SHALL carry `panel_side`, `left` (default) or `right`. On a `map` or `image`
section with `panel_side = "right"` the question panel SHALL sit at the right edge of the
viewport, the stage filling the left, and every piece of chrome that makes room for the panel
on the left today (the Leaflet control corner, the panel hide and show buttons and their arrow
direction) SHALL mirror to the other side; hiding the panel slides it off the right edge.
`panel_side` SHALL have no effect on a `form` section.

#### Scenario: Map section with the panel on the right
- **WHEN** a respondent opens a `map` section with `panel_side = "right"`
- **THEN** the panel is at the right edge, the Leaflet controls sit at the left edge of the
  map, and hiding the panel slides it off to the right with the show button at the right edge

#### Scenario: Welcome page, picture left, text right
- **WHEN** a respondent opens an `image` head section with `panel_side = "right"` and
  `next_label = "Start"`
- **THEN** the picture fills the left of the viewport and the panel with the text and a Start
  button fills the right

#### Scenario: Form section ignores the side
- **WHEN** a `form` section has `panel_side = "right"`
- **THEN** it renders as the centered card, unchanged

### Requirement: The creator chooses the panel width from presets
Each section SHALL carry `panel_width`: `default` (today's 420 px), `third` (one third of
the viewport) or `half` (one half). The stage SHALL fill the rest, and chrome that offsets
itself from the panel SHALL offset from the chosen width. No free-form width is accepted; an
unknown stored value renders as `default`. `panel_width` SHALL have no effect on a `form`
section.

#### Scenario: Half-width panel beside the map
- **WHEN** a respondent opens a `map` section with `panel_width = "half"` on a desktop viewport
- **THEN** the panel is half the viewport wide, the map fills the other half and the Leaflet
  controls sit just beyond the panel's edge

#### Scenario: Unknown value renders as the default
- **WHEN** a section's stored `panel_width` is not one of the presets
- **THEN** the page renders the 420 px panel

### Requirement: Side and width mean nothing on a phone; an image stage becomes a band
Below the mobile breakpoint (768 px) the panel SHALL stay the full-width overlay it is today
whatever `panel_side` and `panel_width` say, and a `map` section SHALL render exactly as
before this change. An `image` section SHALL render the picture as a band across the top of
the viewport with the panel content flowing beneath it, scrolling as one column; the map
chrome stays hidden. The editor's Preview pane in the mobile layout SHALL show the same
rendering.

#### Scenario: Right-side, half-width map section on a phone
- **WHEN** a respondent opens a `map` section with `panel_side = "right"` and
  `panel_width = "half"` on a 390 px wide viewport
- **THEN** the panel is the 88 % overlay from the left edge, as for any map section today

#### Scenario: Image welcome on a phone
- **WHEN** a respondent opens an `image` section on a 390 px wide viewport
- **THEN** the picture is a band at the top, the title, text and the forward button follow
  beneath it in one scrolling column, and no map chrome is visible

### Requirement: Layout settings are safe edits and travel with the section
Stage, panel side, panel width and the section picture SHALL be display settings: a change
on a published or closed survey applies in place without "Unpublished changes". The three
values SHALL travel on the draft copy, on duplicate and paste, in the ZIP backup and through
the REST API and MCP tools; the picture file SHALL be shared within one survey family and
copied as a new file across surveys (as `Question.image` is), and SHALL ride the ZIP backup
beside the question images. A ZIP without the new keys SHALL import with the defaults; a ZIP
with an unknown value SHALL import that field as its default.

#### Scenario: Live survey takes the edit in place
- **WHEN** an editor changes a published survey's section from `panel_side = "left"` to
  `"right"`
- **THEN** the save succeeds without a draft and respondents see the panel on the right

#### Scenario: Draft copy keeps the layout
- **WHEN** unpublished changes are started on a survey whose head section is `image`,
  `right`, `half` with a picture
- **THEN** the draft's head section carries the same four values and the same picture

#### Scenario: ZIP round trip
- **WHEN** a survey with an `image` / `right` / `half` section carrying a picture is exported
  and imported
- **THEN** the imported section carries the three values and the picture

#### Scenario: Legacy archive
- **WHEN** a ZIP written before this change is imported
- **THEN** every section imports with `panel_side = "left"`, `panel_width = "default"` and no
  picture

#### Scenario: API refuses an unknown preset
- **WHEN** `PATCH /api/v1/sections/{id}` carries `panel_width: "wide"`
- **THEN** the response is `422 validation` naming `panel_width`

### Requirement: The section modal offers the layout controls where they apply
The section modal SHALL carry a Layout block with the stage, the panel side, the panel width
and the picture upload. Side and width SHALL be shown only for `map` and `image` stages, the
picture upload only for `image`, and the Map position button only for `map`; switching the
stage in the modal SHALL show and hide them without a save. The block SHALL be editable on a
live survey (content controls, not structural ones).

#### Scenario: Picking the image stage reveals the upload
- **WHEN** a creator switches a section's stage from Map to Image in the modal
- **THEN** the picture upload and the side and width controls are visible and the Map position
  button is disabled, before any save

#### Scenario: Form stage hides side and width
- **WHEN** a creator switches the stage to Form
- **THEN** the side, width and picture controls are hidden

