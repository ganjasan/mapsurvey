## ADDED Requirements

### Requirement: A layer is shown by its placement on the map
A reference layer SHALL appear on a map-layout section's map if and only if the survey has a
placement of that layer covering the section. A placement SHALL belong to the canonical survey,
name one layer at most once, and carry a scope: `all` (every map section, including sections added
later) or `sections` (a list of section references `<code>` or `<code>#<n>`, the n-th section with
that code counted from 0 in creation order, as the translation table counts; `<code>` and `<code>#0`
name the same section). Draft copies, archived versions and restored versions SHALL read the canonical
survey's placements; no copy, publish or restore path SHALL copy them. Layers SHALL render in
placement order. Every placed layer SHALL start switched on in the section's layers control and
legend each time a section loads; the respondent MAY switch it off. Form-layout sections render no
map and therefore no layers, and a placement with scope `all` SHALL NOT count them.

#### Scenario: Every section, now and later
- **WHEN** a layer is placed with scope `all` on a survey with two map sections and the creator adds a third map section
- **THEN** the layer renders on all three sections' maps

#### Scenario: A layer set in Survey settings
- **GIVEN** a survey with sections 1 and 3 on a map and section 2 a form
- **WHEN** the owner adds "Study area boundary" in Survey settings
- **THEN** sections 1 and 3 show it switched on in the layers control and the legend, and section 2 shows no map

#### Scenario: Switched off by the respondent
- **WHEN** a respondent switches a placed layer off on section 1 and goes on to section 3
- **THEN** section 3 shows the layer switched on

#### Scenario: Only picked sections
- **WHEN** a layer is placed with scope `sections` naming section 2
- **THEN** it renders on section 2's map and not on section 1's

#### Scenario: Repeated section codes
- **WHEN** two sections share the code `S1` and the placement names `S1#1`
- **THEN** the layer renders only on the second of them

#### Scenario: A draft copy shows the same layers
- **WHEN** the survey has unpublished changes and the creator previews a section of the draft copy
- **THEN** the preview shows the layers placed on the canonical survey for that section

### Requirement: The Map card places layers from Build
A map-layout section's panel in Build SHALL open with a *Map* card listing the survey's study area
(when set) and the layers placed on that section, each with its swatch, object count, use ("Asked
in section N" when an Objects question asks about it, "From Data" for a dataset of another origin)
and scope. *+ Layer* SHALL offer *Upload a file*, *From Data* and *Draw on the map*; a new layer SHALL
default to scope `all`. Changing a layer's scope or unticking it for the section SHALL save at once.
Placement edits SHALL apply in place on a published survey and SHALL be available to the `editor`
role and above; adding a layer to the survey (upload, From Data) and removing it stay with the owner,
as in Survey settings.

#### Scenario: Upload from the Map card
- **WHEN** the creator uploads a GeoJSON of 24 points from the Map card and closes the dialog
- **THEN** the layer is placed with scope `all`, the card lists it, and the live preview shows it, with no question added

#### Scenario: Placement on a live survey
- **WHEN** an editor places a layer on a published survey
- **THEN** respondents see it on their next page load and no unpublished changes are created

#### Scenario: Viewer cannot place
- **WHEN** a collaborator with the `viewer` role posts a placement
- **THEN** the request is refused

### Requirement: The map's legend comes from placements
The respondent panel of a map section SHALL show an "On this map" legend listing the section's
placed layers in placement order (swatch or rule legend, layer name, on/off toggle wired to the
layers control). The legend SHALL NOT depend on questions. The editor preview SHALL render exactly
the placements of the previewed section through the respondent metadata builder.

#### Scenario: Legend without questions
- **WHEN** a section has two placed layers and no Objects question
- **THEN** the panel shows both in the legend and the toggles hide and show them on the map

### Requirement: The publish check lists what the map shows
The publish confirmation and "Publish changes" SHALL list the study area (source, size, fog,
refusal) and every layer linked to the survey with its use and scope, and SHALL flag a linked layer
that is placed on no map section with inline actions *Show on every section* and *Remove*. Warnings
SHALL NOT block publishing. When the survey opens later (`opens_at` in the future), the dialog SHALL
say that the public link shows the "opens on" page until then and SHALL offer *Preview as a
respondent*.

#### Scenario: A layer on no map
- **WHEN** a survey links "Bike lanes" but places it on no section and the owner opens Publish
- **THEN** the dialog flags "Bike lanes — on no map" with *Show on every section* and *Remove*, and *Publish* stays enabled

#### Scenario: Scheduled survey
- **WHEN** the survey opens on December 10 and the owner publishes on November 24
- **THEN** the dialog says the public link shows the "opens on" page until December 10 and links the respondent preview

### Requirement: Legend-only questions become placements
A data migration SHALL turn every top-level `layer_objects` question of a canonical survey's map
section into a placement of its layer covering that section (scope `all` when the layer then covers
every map section of the survey), in the layers' own position order (the stacking order maps drew
them in until now).
Respondents SHALL see the same layers on the same sections after the migration. A follow-up release
SHALL delete the `layer_objects` questions without sub-questions in every header and drop
`Question.panel_mode` and `SurveySection.hidden_layers`; until then such questions SHALL be hidden in
the editor and render nothing for respondents.

#### Scenario: A boundary shown on every section
- **WHEN** a survey has a legend-only question bound to "Study Area" in each of its three map sections
- **THEN** after the migration it has one placement of "Study Area" with scope `all` and the respondent maps are unchanged

#### Scenario: A question that asks keeps working
- **WHEN** an Objects question with two sub-questions is bound to "Proposed crossings" in section 2
- **THEN** after the migration section 2 has a placement of that layer and the question still asks about each object

### Requirement: Placements are writable through every surface
Placing, unplacing, changing scope and reordering SHALL go through one service
(`survey/services/placements.py`) called by the editor, REST v1 and the MCP server, with the
survey-role and Pro gates of each surface. Creator events SHALL record `layer_added` (source,
surface) and `layer_placed` (scope, automatic or not); no event SHALL fire on respondent pages.

#### Scenario: Place through the API
- **WHEN** a Pro token with write scope POSTs a placement with scope `all` for a linked layer
- **THEN** the layer renders on every map section and the editor's Map card shows the same placement

#### Scenario: Place a layer that is not linked
- **WHEN** a client places a layer that the survey does not link
- **THEN** the request is refused with a validation error naming the layer
