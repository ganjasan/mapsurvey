# map-style-library Specification

## Purpose
Workspace map styles as rows (epic #545, ADR 0001): the `MapStyle` / `MapStyleVersion` model with immutable published versions, the five presets as rows, the one resolver (`survey/basemaps.py`) and provider table every map surface reads, version pinning on publish, the library page under *Library* in the sidebar with duplicate / rename / delete, the `map_styles` Pro gate on creating a style, and background publishing to Mapbox on the `styles` Celery queue.
## Requirements
### Requirement: A map style is a workspace row with immutable versions
The system SHALL store map styles as `MapStyle` rows owned by a workspace, or owned by nobody for the five system presets (`streets`, `satellite`, `topo`, `paper`, `paper_b`), each with one or more `MapStyleVersion` rows. A version SHALL carry the settings document it was built from, its provider (`mapbox` or `xyz`), the hosted Mapbox style id or the raw tile URL, the style id used for print, and a status of `pending`, `ready` or `failed`. A `ready` version SHALL never be changed; a new look is a new version.

#### Scenario: Presets exist after migration
- **WHEN** the migration has run on an empty database
- **THEN** five preset styles exist with no workspace, each with version 1 `ready`, and `streets` resolves to `mapbox/streets-v12`, `topo` to `mapbox/outdoors-v12`, `satellite` to the Esri World Imagery tile URL with `static_style` `mapbox/satellite-streets-v12`

#### Scenario: A version is not edited
- **WHEN** code attempts to save a `ready` version with a changed `settings` or `mapbox_style_id`
- **THEN** the save is refused with a validation error

### Requirement: One resolver and one provider table
A basemap key SHALL be a preset key or `style:<uuid>` of a workspace style. `survey/basemaps.py` SHALL be the only place a key is turned into a provider: tile URL template, `tileSize`, `zoomOffset`, `maxZoom`, attribution and the print style id. Every surface that draws a base map SHALL build its Leaflet layers from the table this module emits for the survey's workspace, and no template under `survey/templates/` SHALL contain a Mapbox style id or a Mapbox tile URL.

#### Scenario: Workspace style on the respondent page
- **WHEN** a survey enables `style:<uuid>` of its workspace's style whose latest version is `ready`
- **THEN** the respondent page's provider table has that key with the version's hosted tile URL, `tileSize: 512`, `zoomOffset: -1`, and the layer switcher lists the style under its name

#### Scenario: Another workspace's style does not resolve
- **WHEN** a survey's `basemaps` names `style:<uuid>` of a style owned by a different workspace
- **THEN** the key is absent from the table and the page falls back to the first enabled key that resolves, else `streets`

#### Scenario: No template holds a Mapbox URL
- **WHEN** every template under `survey/templates/` is scanned
- **THEN** none contains `api.mapbox.com/styles/v1/` or a literal Mapbox style id; the only tile URL literal left is Esri's, in the migration that seeds the satellite preset

#### Scenario: Print resolves the same key
- **WHEN** a section's printed frame is built for a survey whose default basemap is `style:<uuid>`
- **THEN** the Static Images request names that version's Mapbox style id, and the layout entry records the key

### Requirement: Published surveys pin the version they were published with
`SurveyHeader.basemap_pins` SHALL map each referenced workspace style to a version number. Publishing (the draft → published transition and `publish_draft`) SHALL set every pin to the style's latest `ready` version; a draft copy SHALL carry no pins and resolve to the latest version. The resolver SHALL honour a pin that names a `ready` version.

#### Scenario: A new version does not change a live survey
- **WHEN** a published survey pins version 1 of a style and version 2 becomes `ready`
- **THEN** the respondent page keeps version 1's tile URL until the survey is published again, after which it shows version 2

#### Scenario: Draft shows the latest
- **WHEN** a draft copy is created from that survey
- **THEN** the draft's `basemap_pins` is empty and its preview uses version 2

#### Scenario: Pins travel to the archived version
- **WHEN** `publish_draft` archives the current structure
- **THEN** the archived header carries the pins, `basemaps` and `default_basemap` the published survey had

### Requirement: The library page lists presets and workspace styles
`/org/<slug>/map-styles/` SHALL be reachable by every member of the workspace and SHALL show, as cards: the five presets marked *Preset*, then the workspace's non-archived styles, each with a preview image, its base, the number of surveys of the workspace that reference it in `basemaps`, `default_basemap`, a section override or a results block, and its status while a version is `pending` or `failed`.

#### Scenario: Usage count
- **WHEN** a workspace has three surveys and two of them enable `style:<uuid>`, one as a section override only
- **THEN** the card says it is used in 2 surveys

#### Scenario: Pending version is visible
- **WHEN** a style's latest version is `pending`
- **THEN** its card shows a *Publishing…* chip, the page re-polls every few seconds, and the style is absent from survey pickers until the version is `ready`

### Requirement: Duplicate, rename and delete
Owners, admins and editors SHALL be able to duplicate any style whose base the generator supports (`mapbox/streets-v12`): the copy is a workspace style named "<name> copy" with version 1 `pending`, published by a background task, and the response SHALL open the copy in the editor; open a workspace style in the editor, where its name is changed; delete a workspace style no survey references. Deleting a style that a survey references SHALL be refused with a message naming the surveys. Presets SHALL NOT be renamed, edited or deleted. Satellite and Topo SHALL show no *Duplicate*.

#### Scenario: Duplicate publishes in the background
- **WHEN** an editor duplicates Paper A
- **THEN** a new `MapStyle` of the workspace exists with version 1 `pending` carrying Paper A's settings, `publish_map_style_version` is enqueued on the `styles` queue, the response redirects to the copy's editor, and after the task runs the version is `ready` with a Mapbox id different from Paper A's

#### Scenario: Delete refused while in use
- **WHEN** an editor deletes a style one survey enables
- **THEN** nothing changes and the response names that survey

#### Scenario: Delete of an unused style
- **WHEN** an editor deletes a style no survey references
- **THEN** `archived_at` is set, the style leaves the page and the pickers, and a delete of its Mapbox style is enqueued

#### Scenario: Viewer cannot act
- **WHEN** a member with the `viewer` role posts to duplicate, rename or delete
- **THEN** the response is 403 and nothing changes

#### Scenario: Workspace card links to the editor
- **WHEN** the library renders a workspace style
- **THEN** its card carries *Edit* linking to the editor and no separate rename form; a preset's card carries no *Edit*

### Requirement: Creating a style is a Pro feature; using one is not
`billing/features.py` SHALL declare `map_styles` for `PLAN_PRO` with a trial allowance of 2. The duplicate view SHALL pass `require_feature('map_styles')` and count a use through `billing.trial.use` when the row is created. Rename, delete, the library page itself and selecting any existing style in a survey SHALL NOT be gated.

#### Scenario: Free workspace, trial spent
- **WHEN** a Free workspace whose trial allowance for `map_styles` is exhausted posts a duplicate
- **THEN** the response is the Pro-required page and no row is created

#### Scenario: Lapsed workspace keeps its maps
- **WHEN** a workspace's subscription lapses while a survey shows `style:<uuid>`
- **THEN** respondents still get that style's tiles and the settings panel still lists it

### Requirement: Survey pickers and imports validate against the workspace's keys
The survey settings form, the section map picker, the create wizard and the public results block editor SHALL offer `choices_for(workspace)` — presets first, then the workspace's `ready` styles — and refuse any other key. ZIP import SHALL replace a `style:` key the importing workspace cannot resolve with `streets` and add a report line; the REST API and MCP SHALL accept any key the form accepts.

#### Scenario: Settings offer the workspace's styles
- **WHEN** an editor opens survey settings in a workspace with one ready style
- **THEN** *Base maps* lists the five presets and that style, and saving `basemaps=['streets','style:<uuid>']` with `default_basemap='style:<uuid>'` succeeds

#### Scenario: Import into another workspace
- **WHEN** a ZIP exported with `default_basemap='style:<uuid>'` is imported into a workspace that has no such style
- **THEN** the survey is created with `default_basemap='streets'` and the import report says the style was not available here

### Requirement: Publishing runs in Celery on its own queue
`publish_map_style_version` and `delete_mapbox_style` SHALL be routed to the `styles` queue with a rate limit below the Styles API write limit, SHALL read the secret token on the worker only, and SHALL record failure on the version (`failed`, `error`) instead of raising to the caller.

#### Scenario: Mapbox refuses
- **WHEN** the Styles API answers 429 or 5xx to a create
- **THEN** the task retries up to its limit and then marks the version `failed` with the response in `error`; the card shows *Failed* and offers *Try again*

#### Scenario: Token stays on the worker
- **WHEN** templates and the `mapbox` context processor are scanned
- **THEN** none references `MAPBOX_STYLES_TOKEN`

### Requirement: New style starts from a preset and opens the editor
The library SHALL offer owners, admins and editors a *New style* button whose menu lists the presets the generator can rebuild (Streets, Paper A, Paper B) with their preview tiles. Choosing one SHALL create a workspace style named "New style" — with ` (2)`, ` (3)` … when the name is taken — whose version 1 is `pending` with that preset's settings, enqueue its publication, count one `map_styles` use, and redirect to the new style's editor.

#### Scenario: New style from Paper B
- **WHEN** an editor of a Pro workspace chooses *New style* → Paper B
- **THEN** a workspace style "New style" exists with version 1 `pending` carrying Paper B's settings, the publish task is enqueued, and the response redirects to its editor

#### Scenario: Second new style
- **WHEN** "New style" already exists and another is created
- **THEN** the new one is named "New style (2)"

#### Scenario: Menu lists rebuildable presets only
- **WHEN** an editor opens the library
- **THEN** the *New style* menu offers Streets, Paper A and Paper B and not Satellite or Topo; a viewer sees no *New style*

#### Scenario: Spent trial
- **WHEN** a Free workspace whose `map_styles` allowance is spent chooses *New style*
- **THEN** the Pro-required page answers and nothing is created

