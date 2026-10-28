## ADDED Requirements

### Requirement: Session geo preview initialises on the surface that renders it
The session detail partial SHALL render its geo preview container whenever the session has at
least one geo answer, and the surface that renders the partial SHALL initialise the map after the
partial is in the DOM and visible. Under `RESPONSES_V2` the initialisation SHALL be triggered by
the drawer body's content swap; on the pre-V2 path it SHALL be triggered by the modal's shown
event. Both paths SHALL call the same initialisation routine, and a previously created map
instance SHALL be disposed before a new one is created.

#### Scenario: Response with geo answers opened in the v2 drawer
- **WHEN** a creator opens a response that has at least one point, line or polygon answer
- **THEN** the preview shows a rendered map fitted to that response's objects, not an empty box

#### Scenario: Walking responses with prev/next
- **WHEN** the creator steps from one response to another without closing the detail surface
- **THEN** the preview re-initialises for the newly loaded response and no previous map instance is left attached

#### Scenario: Response without geo answers
- **WHEN** a response has no geo answers
- **THEN** no preview container is rendered and no map initialisation is attempted

#### Scenario: Kill switch off
- **WHEN** `RESPONSES_V2` is disabled and the session detail modal is opened
- **THEN** the preview initialises as it did before this change

### Requirement: Geo answers are identified per object
Each geo feature emitted for a session's detail view SHALL carry a stable object identifier
derived from the geo answer's primary key, and a display label matching the one shown for that
object's answer row. Existing feature properties (`question`, `type`, `attributes`) SHALL be
preserved unchanged.

#### Scenario: Question with several objects
- **WHEN** a session holds three polygons for one geo question
- **THEN** each emitted feature carries its own object identifier and its own label, and the three labels are distinct

#### Scenario: Existing consumers unaffected
- **WHEN** the feature payload is consumed by behaviour specified in `responses-geo-subanswers`
- **THEN** the previously specified properties are present and unchanged

### Requirement: Geo answer rows show a readable value
A geo answer row in the session detail surface SHALL display the same formatted value the
attribute table uses for that answer — coordinates for a point, vertex count for a line or
polygon — rather than a bare type name. When a question holds several objects, the row SHALL
remain distinguishable from its siblings.

#### Scenario: Point answer
- **WHEN** the detail surface renders a point answer
- **THEN** the row shows the point's coordinates, matching what the attribute table shows for the same answer

#### Scenario: Polygon answer
- **WHEN** the detail surface renders a polygon answer
- **THEN** the row shows the polygon's vertex count

### Requirement: Full-size session map opens from the detail surface
The detail surface SHALL offer a full-size map of the session showing every geo object of that
session across all of its geo questions. It SHALL be reachable both by activating a geo answer
row and by activating the geo preview. The map SHALL be built from the geo data already present
in the detail surface, without an additional request to the server, and SHALL be read-only —
no geometry can be created, moved or deleted from it.

#### Scenario: Opened from the preview
- **WHEN** the creator activates the geo preview
- **THEN** the full-size map opens showing all of the session's geo objects, fitted to their extent

#### Scenario: Opened from a geo answer row
- **WHEN** the creator activates a geo answer row
- **THEN** the full-size map opens with that object in view and its details shown

#### Scenario: Sizing after opening
- **WHEN** the full-size map becomes visible
- **THEN** it fills its container with no unrendered area

#### Scenario: Closing and reopening
- **WHEN** the creator closes the full-size map and opens it again, for the same or another response
- **THEN** it renders correctly and no map instance from a previous opening remains attached

### Requirement: Full-size session map distinguishes questions and shows object attributes
The full-size session map SHALL colour objects per geo question and SHALL present a legend naming
those questions. Activating an object SHALL show that object's label and its sub-answer
name/value pairs, sourced from the feature's `attributes`. Respondent-authored values SHALL be
rendered escaped, and the embedded geo payload SHALL NOT be marked safe.

#### Scenario: Two geo questions in one session
- **WHEN** a session has objects for two different geo questions
- **THEN** the objects are drawn in distinct colours and the legend names both questions

#### Scenario: Object with sub-answers
- **WHEN** the creator activates an object that has sub-answers
- **THEN** its label and its sub-answer name/value pairs are shown

#### Scenario: Respondent text containing markup
- **WHEN** a sub-answer value contains HTML markup
- **THEN** it is displayed as text and is not interpreted as markup

### Requirement: Detail surface and its geo initialiser stay wired together
The project SHALL hold an automated check that the container the session detail partial's geo
initialiser binds to exists in the dashboard template that renders the partial, for the active
`RESPONSES_V2` state.

#### Scenario: Container renamed or removed
- **WHEN** the dashboard template no longer provides the container the initialiser binds to
- **THEN** the check fails
