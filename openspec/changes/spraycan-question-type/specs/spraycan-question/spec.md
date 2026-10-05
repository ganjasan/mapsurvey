## ADDED Requirements

### Requirement: The spraycan input type stores one cloud of dots per respondent

The system SHALL offer a geo question type `spraycan`. A respondent's answer to a `spraycan`
question SHALL be exactly one `Answer` row per session whose geometry is a `MultiPoint` (WGS 84)
in a dedicated `Answer.multipoint` column — one dot per sprayed point, in spray order. `spraycan`
SHALL be a member of every geo-type set the code consults (`GEO_INPUT_TYPES` and the sets that
decide map rendering, geo validation, popup sub-questions, form-layout exclusion, export), so a
feature that enumerates geo types treats a spray cloud as a geo answer unless this spec says
otherwise. A spray cloud SHALL have no `point`, `line` or `polygon` value.

#### Scenario: Submitting a spray stores a MultiPoint
- **WHEN** a respondent finishes a spray of 120 dots and submits the section
- **THEN** one `Answer` row exists for that session and question with `multipoint` holding
  120 points in spray order and `point`, `line`, `polygon` all null

#### Scenario: Re-submitting replaces the cloud
- **WHEN** a respondent returns to the section, erases part of the cloud and submits again
- **THEN** the session has one `Answer` row for the question holding the edited cloud, and
  sub-question answers attached to the previous row are carried over as the section POST does
  for other geo types

#### Scenario: Geo-type sets include spraycan
- **WHEN** code asks whether `spraycan` is a geo type
- **THEN** every geo-type set in `survey/models.py` answers yes, and a test asserts the
  membership so a new set cannot omit it silently

### Requirement: Spray clouds are unbounded by default, capped only by the creator

The system SHALL NOT limit how much a respondent paints unless the creator sets **Max dots per
respondent** on the question (`validation_settings.max_dots`, empty by default). The section POST SHALL normalise every cloud it stores: dots snapped to a one-metre grid with
duplicates dropped, first occurrence kept, so the stored count is a function of painted area and
dwell rather than of the pointer's event rate (paint saturates at one dot per square metre, as
it does in a graphics editor). When a cap is set, the widget SHALL stop emitting dots at it and
say so unobtrusively, and the section POST SHALL keep the first `max_dots` normalised dots of a
longer cloud. With no cap the POST SHALL keep every dot
up to a hard ceiling (`SPRAY_HARD_CEILING`, 100 000) that exists only to bound a scripted request
and is unreachable by hand. The POST SHALL discard a cloud whose coordinates are not finite WGS 84
longitude/latitude pairs the way it discards an unreadable polygon chunk — a logged warning,
nothing stored for that question, the section still advances (the section POST has no
error-render path; `required` is enforced client-side for every geo type). A `required` spraycan
question SHALL be satisfied by at least one dot; `min_features`/`max_features` SHALL NOT apply
(one cloud per respondent).

#### Scenario: Paint saturates at one dot per metre
- **WHEN** a request posts 50 dots inside one square metre and 3 dots far apart
- **THEN** the stored cloud has 4 dots

#### Scenario: No cap by default
- **WHEN** a respondent sprays 5000 dots on a question with no Max dots setting
- **THEN** every dot is stored and the widget carries no cap

#### Scenario: Creator cap reached in the browser
- **WHEN** the creator set Max dots to 1000 and a respondent keeps spraying past it
- **THEN** no further dots appear and the action bar shows a short "brush is empty" hint

#### Scenario: Creator cap in the POST
- **WHEN** Max dots is 100 and a request posts a MultiPoint of 150 dots
- **THEN** the stored cloud has the first 100 dots

#### Scenario: Required spraycan with no dots
- **WHEN** a respondent submits a section where a required spraycan question has no dots
- **THEN** the section does not advance and the question is marked as missing, the same way a
  required point question with no marker is

#### Scenario: Malformed coordinates are discarded
- **WHEN** a request posts a MultiPoint containing `[200, 95]`
- **THEN** the POST logs a warning naming the question, stores nothing for it, and responds with
  the normal redirect — exactly as it treats an unreadable polygon chunk

### Requirement: The respondent paints in an explicit paint mode

Pressing a spraycan question's button SHALL enter paint mode on the map: the map stops panning
under the pointer, a brush cursor of the question's brush size follows the pointer, and holding
the pointer (mouse button or finger) sprays dots scattered uniformly within the brush radius
around the pointer. Paint accumulates: moving the pointer slowly or dwelling in one place adds
more dots than passing quickly, so density carries the respondent's confidence. The bottom action
bar (`#drawbar`, shared with polygon/line drawing) SHALL show a tool switch — **Spray**,
**Erase**, **Move map** — plus **Clear**, **Cancel** and **Finish**. **Erase** removes dots
within the brush radius of the pointer; **Move map** re-enables panning and zooming for the
duration; **Clear** empties the cloud; **Cancel** leaves paint mode without changing the stored
answer; **Finish** is enabled once at least one dot exists and completes the feature. Zooming in
paint mode SHALL keep dots at their geographic positions; the brush radius is a screen-pixel
size, so zooming in paints finer. No other draw or crosshair mode SHALL be active at the same
time.

#### Scenario: Entering paint mode
- **WHEN** a respondent presses the button of a spraycan question
- **THEN** the map shows a brush cursor in the question's colour, the action bar shows
  Spray / Erase / Move map, Clear, Cancel and a disabled Finish, and dragging on the map paints
  instead of panning

#### Scenario: Dwelling adds paint
- **WHEN** a respondent holds the pointer still in Spray mode for one second
- **THEN** the number of dots under the brush grows over that second

#### Scenario: Finish enables with the first dot
- **WHEN** the first dot is sprayed
- **THEN** Finish becomes enabled

#### Scenario: Erase removes nearby dots only
- **WHEN** the respondent switches to Erase and drags across part of the cloud
- **THEN** dots within the brush radius of the drag path are removed and the rest stay

#### Scenario: Move map does not paint
- **WHEN** the respondent switches to Move map and drags
- **THEN** the map pans, no dots are added or removed, and switching back to Spray paints again

#### Scenario: Cancel keeps the previous answer
- **WHEN** a respondent who already has a stored cloud enters paint mode, sprays more and presses
  Cancel
- **THEN** the map shows the previously stored cloud unchanged

#### Scenario: Touch painting does not scroll or pan
- **WHEN** a respondent on a phone drags a finger across the map in Spray mode
- **THEN** the page does not scroll, the map does not pan and dots are painted along the drag

#### Scenario: Only one mode at a time
- **WHEN** paint mode is active and the respondent presses another geo question's button
- **THEN** paint mode is cancelled first, exactly as polygon drawing is cancelled today

### Requirement: The cloud is drawn as paint, and is one feature of the question

The spray cloud SHALL be rendered on the respondent map by a canvas layer that STAMPS every dot
with one pre-rendered airbrush sprite in the question's colour — a soft radial halo that fades to
transparent with a near-opaque grain at its centre — so overlapping dots accumulate into solid
paint, the edge of a cloud stays soft and the grain reads as spray; the brush SHALL scatter new
dots with a Gaussian centred on the pointer (dense centre, thin edge), clipped to the brush ring.
Only newly sprayed dots SHALL be drawn during a stroke, and the layer SHALL NOT redraw while the
map is being dragged (it redraws when the move or zoom ends); the
system SHALL NOT create one Leaflet marker per dot, nor draw a dot with a path operation when a
sprite blit will do. After **Finish** the cloud is the question's
single placed feature: the question's button is disabled (one cloud per respondent — the
counter chip stays hidden, as it does for every single-feature question); clicking the cloud on the map opens the same feature popup the other geo
types use, with the sub-question form when the question has sub-questions, **Edit** (re-enters
paint mode with the current dots) and **Delete** (removes the cloud and re-enables the button).
When the question has sub-questions, **Finish** SHALL open that popup immediately, as finishing a
polygon does. The popup SHALL anchor at the cloud's centroid.

#### Scenario: Finish with sub-questions opens the popup
- **WHEN** a spraycan question has a sub-question and the respondent presses Finish
- **THEN** the feature popup opens at the cloud's centroid with the sub-question form and the
  apply button, and saving it returns the respondent to the section panel

#### Scenario: One cloud per question
- **WHEN** a respondent has finished a cloud
- **THEN** the question's button is disabled and the cloud is clickable on the map

#### Scenario: Edit re-enters paint mode with the dots
- **WHEN** the respondent opens the cloud's popup and presses Edit
- **THEN** paint mode starts with the existing dots in place and Finish enabled

#### Scenario: Delete revives the button
- **WHEN** the respondent deletes the cloud from its popup
- **THEN** the cloud disappears and the button is enabled

#### Scenario: Restored session shows the cloud
- **WHEN** a respondent returns to a section whose spraycan answer was submitted earlier
- **THEN** the cloud is drawn and the button is disabled, like a restored polygon at its
  maximum

### Requirement: Creators configure the default brush size and colour, nothing else

The question editor SHALL offer for `spraycan` the question colour (existing field) and a
**Brush size** choice — `small`, `medium` (default), `large` — stored on `Question` and mapped to
a screen-pixel radius in one place in the code. That size is the DEFAULT: the paint toolbar
SHALL let the respondent switch between the three sizes while painting (the stored answer does
not record the size). It SHALL hide the marker icon picker and the min/max features fields for
this type, because neither applies. The live preview SHALL render the question as the
respondent sees it, including the brush size.

#### Scenario: Brush size offered for spraycan only
- **WHEN** a creator picks `spraycan` in the question modal
- **THEN** a Brush size control appears with `medium` selected, and the icon picker and the
  min/max features fields are hidden

#### Scenario: Brush size persists as the default
- **WHEN** a creator saves a spraycan question with Brush size `large`
- **THEN** the respondent's brush cursor starts with the large radius and the toolbar's
  size switch shows `large` selected

#### Scenario: Respondent switches the brush
- **WHEN** a respondent in paint mode picks the small size
- **THEN** the brush ring shrinks and new dots scatter within the small radius; dots already
  sprayed stay

### Requirement: Spraycan is a geo type to every feature that enumerates geo types

A `spraycan` question SHALL be accepted as a parent of sub-questions (`PARENT_TYPES`), SHALL be
refused in a `form`-layout section like the other geo types, SHALL be duplicated and pasted with
its brush setting, SHALL be hideable by a visibility rule but never offered as a controller, and
SHALL NOT be offered as the source question of a shared-map (`question`-sourced) reference layer
— the shared-map source picker lists `point`/`line`/`polygon` only and materialisation ignores
spray clouds.

#### Scenario: Sub-questions allowed
- **WHEN** a creator opens "+ Add Sub-question" under a spraycan question
- **THEN** the sub-question modal opens with the same type restrictions as under a polygon

#### Scenario: Not a shared-map source
- **WHEN** a creator configures a shared-map layer
- **THEN** the source-question picker does not list spraycan questions

#### Scenario: Duplicate keeps the brush
- **WHEN** a creator duplicates a section containing a spraycan question with Brush size `small`
- **THEN** the copy's question is `spraycan` with Brush size `small`
