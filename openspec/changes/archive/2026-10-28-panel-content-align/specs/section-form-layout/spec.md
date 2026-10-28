## ADDED Requirements

### Requirement: The creator may centre the panel's content, horizontally and vertically
Each section SHALL carry two independent content-alignment settings, both defaulting to
today's rendering:

- `content_width`: `full` (default — the content spans the panel) or `column` (the content —
  title, progress, subheading, questions and the Back/Next buttons — is a column of reading
  width, at most 640 px, centred horizontally in the panel);
- `content_valign`: `top` (default — the content starts at the panel's top) or `middle`
  (content shorter than the panel is centred vertically in it; content taller than the panel
  starts at the top and scrolls, never clipped, the forward button always reachable).

On a `map` or `image` section on a desktop viewport the page SHALL apply both settings in any
combination, whatever the panel side and width. The panel's close button SHALL keep its
corner and the footer (Made with Mapsurvey, abuse notice) SHALL stay at the bottom of the
panel. A `form` section and every viewport below the mobile breakpoint (768 px) SHALL ignore
both settings and render exactly as before. Unknown stored values SHALL render as the
defaults. The settings SHALL follow HTMX navigation like the other layout settings, and a
direct load SHALL carry them in the first HTML.

#### Scenario: Defaults change nothing
- **WHEN** a respondent opens a `map` section with `content_width = "full"` and
  `content_valign = "top"`
- **THEN** the page carries no content-alignment class and renders as before this change

#### Scenario: Senf-style section
- **WHEN** a respondent on a desktop opens a `map` section with the panel on the right at half
  width, `content_width = "column"` and `content_valign = "middle"`
- **THEN** the title, text, options and Back/Next sit in a column of at most 640 px in the
  middle of the right half, centred vertically, the close button in the panel's corner

#### Scenario: Column at the top
- **WHEN** a section has `content_width = "column"` and `content_valign = "top"`
- **THEN** the content is a centred column that starts at the top of the panel

#### Scenario: Long content scrolls from the top
- **WHEN** a `content_valign = "middle"` section holds more questions than fit the screen
- **THEN** the panel shows its title first and scrolls down to the forward button; nothing is
  cut off above the title

#### Scenario: Navigating to a section without centring
- **WHEN** a respondent moves from a `column` / `middle` section to a `full` / `top` section
- **THEN** the content goes back to the full panel width and the top, without a page load

#### Scenario: Form section and phones ignore the settings
- **WHEN** a `form` section, or any section on a 390 px viewport, has `column` / `middle`
- **THEN** it renders as it did before this change

## MODIFIED Requirements

### Requirement: Layout settings are safe edits and travel with the section
The layout settings SHALL be display settings — stage, panel side, panel width, content width,
content vertical alignment and the section picture: a change on a published or closed survey applies in place
without "Unpublished changes". The five values SHALL travel on the draft copy, on duplicate
and paste, in the ZIP backup and through the REST API and MCP tools; the picture file SHALL be
shared within one survey family and copied as a new file across surveys (as `Question.image`
is), and SHALL ride the ZIP backup beside the question images. A ZIP without the new keys SHALL
import with the defaults; a ZIP with an unknown value SHALL import that field as its default.

#### Scenario: Live survey takes the edit in place
- **WHEN** an editor changes a published survey's section from `panel_side = "left"` to
  `"right"`, or from `content_valign = "top"` to `"middle"`
- **THEN** the save succeeds without a draft and respondents see the change

#### Scenario: Draft copy keeps the layout
- **WHEN** unpublished changes are started on a survey whose head section is `image`,
  `right`, `half`, `column`, `middle` with a picture
- **THEN** the draft's head section carries the same six values and the same picture

#### Scenario: ZIP round trip
- **WHEN** a survey with an `image` / `right` / `half` / `column` / `middle` section carrying a
  picture is exported and imported
- **THEN** the imported section carries the five values and the picture

#### Scenario: Legacy archive
- **WHEN** a ZIP written before these settings existed is imported
- **THEN** every section imports with `panel_side = "left"`, `panel_width = "default"`,
  `content_width = "full"`, `content_valign = "top"` and no picture

#### Scenario: API refuses an unknown preset
- **WHEN** `PATCH /api/v1/sections/{id}` carries `panel_width: "wide"` or
  `content_valign: "bottom"`
- **THEN** the response is `422 validation` naming that field

### Requirement: The section modal offers the layout controls where they apply
The section modal SHALL carry a Layout block with the stage, the panel side, the panel width,
the content width, the content vertical alignment and the picture upload. Side, width and the
two content settings SHALL be shown only for `map` and `image` stages, the picture upload only
for `image`, and the Map position button only for `map`; switching the stage in the modal
SHALL show and hide them without a save. The block SHALL be editable on a live survey (content
controls, not structural ones).

#### Scenario: Picking the image stage reveals the upload
- **WHEN** a creator switches a section's stage from Map to Image in the modal
- **THEN** the picture upload, the side and width controls and the two content controls are
  visible and the Map position button is hidden, before any save

#### Scenario: Form stage hides side and width
- **WHEN** a creator switches the stage to Form
- **THEN** the side, width, content and picture controls are hidden
