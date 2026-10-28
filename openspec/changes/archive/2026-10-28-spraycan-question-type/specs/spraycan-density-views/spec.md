## ADDED Requirements

### Requirement: The Responses map shows spray clouds as an agreement surface

On the Responses Map pane each `spraycan` question in scope SHALL be one layer of the
`LayerManager`, rendered as an AGREEMENT surface over the clouds of every session in scope: for
every geographic cell, the share of respondents whose cloud touches it, drawn exactly as the
public results page draws its grid: crisp square cells in the layer's colour, opacity growing
with that share, cells sized by the clouds' extent (about 40 across the longer side, never finer
than 20 m) and anchored to the world so they do not slide when the map pans
(`L.SprayAgreementLayer`, style `grid`, one canvas). A heat-ramp rendering of the same share
(style `heat`) exists as an option, not the default. Darker means "more respondents painted
here", never "one person dwelt here". Each
respondent SHALL count once whatever their dot count, so a respondent who dwelt longer does not
outweigh one who sprayed briefly; a lone respondent paints a flat full-strength area; the surface
SHALL follow the page's session filter. The layer SHALL carry no per-dot popups. Hover/selection behaviour that other geo layers get from the
`SelectionManager` SHALL treat the whole cloud as the selectable unit (one session), never a
single dot. The Overview thumbnail SHALL draw the same agreement surface, non-interactive, never one marker
per dot. The Map pane
SHALL render when a survey's only geo question is a spraycan question.

#### Scenario: Agreement surface per spraycan question
- **WHEN** a survey has one spraycan question and five sessions with clouds
- **THEN** the Map pane lists one layer for that question and renders one surface over all five
  clouds, darkest where all five painted

#### Scenario: Equal weight per respondent
- **WHEN** session A sprayed 2000 dots over the centre and session B sprayed 50 dots over the
  park
- **THEN** a cell painted only by A and a cell painted only by B have the same opacity

#### Scenario: Only spraycan, still a map
- **WHEN** a survey's only geo question is a spraycan question and it has answers
- **THEN** the Map pane and the Overview thumbnail render the density surface instead of the
  "no geo questions" empty state

### Requirement: A single response shows its own cloud as paint

The per-response map modal and the Responses detail drawer SHALL render that session's spray cloud
as airbrush paint in the question's colour, using the same canvas renderer the respondent map
uses, with the sub-question answers listed under the question like the other geo types. The
session detail and the attribute table SHALL state the dot count and the painted extent
("394 dots · 0.8 km²", the convex hull area; no area for fewer than three dots).

#### Scenario: Response modal draws the cloud
- **WHEN** a creator opens the map modal of a session that sprayed 300 dots
- **THEN** the modal shows the 300-dot cloud as airbrush paint in the question's colour and the
  sub-question answers under the question name, with "300 dots · <area>" in the detail

### Requirement: Public results publish a density grid, never a respondent's dots

A public results **map** block over a `spraycan` question SHALL publish a server-side grid
instead of features: square cells in Web Mercator sized so the clouds' bounding box is about 40
cells across its longer side (never finer than 20 m), each cell carrying the number of DISTINCT
clean sessions with at least one dot inside it. Cells whose count is below the page's k-anonymity
threshold SHALL be omitted from the payload entirely (not shown as "<K", because the cell's
location is the sensitive fact); a threshold of 1 keeps every cell. The payload SHALL contain no
dot coordinates, no per-session data and no cell with a count of zero. The public page SHALL draw
the cells as a choropleth whose opacity grows with the count and SHALL show the total number of
respondents; popup label fields SHALL NOT apply to spraycan blocks. The snapshot format version
SHALL be bumped so a frozen page from before this change shows the re-freeze notice rather than
an empty map.

#### Scenario: Cells below K are omitted
- **WHEN** the threshold is 3 and a cell was touched by two respondents
- **THEN** the published payload has no entry for that cell

#### Scenario: Cells count respondents, not dots
- **WHEN** one respondent sprayed 400 dots into one cell and three others sprayed 5 dots each
  into it
- **THEN** the cell's count is 4

#### Scenario: No raw dots in the payload
- **WHEN** a visitor inspects the data served for a spraycan map block
- **THEN** it holds cell polygons with counts only — no MultiPoint, no session identifiers

#### Scenario: Stale snapshot asks for a re-freeze
- **WHEN** a frozen page was snapshotted before this change and contains a spraycan block
- **THEN** the page shows the re-freeze notice for that block instead of rendering it

### Requirement: A cloud is the same colour everywhere

Every read surface SHALL draw a spraycan question's clouds in the colour the creator chose for
the question (`Question.color`, the paint the respondent used): the Responses Map pane and
Overview thumbnail, the response drawer and modal, and the public grid. Only when the creator
left the default black SHALL Responses fall back to its legend palette and the public page to its
default pink.

#### Scenario: Pink for the respondent, pink for the creator and the public
- **WHEN** a spraycan question's colour is `#d6336c`
- **THEN** the respondent paints in `#d6336c`, the Responses map and Overview draw its cells in
  `#d6336c`, and the public grid's cells are `#d6336c`

### Requirement: Density is a reading convention, not a second data source

Every creator-facing density surface (Responses map, Overview thumbnail, public grid) SHALL be
computed from `Answer.multipoint` rows of the sessions the surface's page already scopes
(clean sessions for public results, the Responses page's own session filter for the Map pane);
no table SHALL cache a density surface.

#### Scenario: Trashed session leaves the surface
- **WHEN** a session with a spray cloud is moved to the trash
- **THEN** the Responses heat surface and the public grid no longer include its dots on the next
  render
