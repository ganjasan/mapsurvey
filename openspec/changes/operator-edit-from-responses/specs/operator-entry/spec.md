## ADDED Requirements

### Requirement: An entered response is edited from Responses
The detail surface SHALL offer, for a session with `source != online` that is not trashed, to a
caller with the `editor` role or above on the survey while the survey's organisation is covered
for `operator_entry`, an **Edit response** action opening the entry form at the session's first
visible section (operator surface), and every answer row's section name SHALL link to the entry
form at that row's section. The full-size map of the response SHALL offer **Edit on the map**,
opening the entry form at the section of the object the map was opened on (else of the first
object), and each object's pop-up SHALL carry the same link for its own section. All these links
SHALL carry the return marker (`return_to=response`, or `return_to=map` from the map). Online
sessions, trashed sessions, `viewer`s and organisations not covered SHALL get none of them; the
entry URLs keep refusing online sessions.

#### Scenario: Paper response shows Edit
- **GIVEN** a paper session entered on a Pro workspace
- **WHEN** an `editor` opens its detail surface
- **THEN** it shows *Edit response* linking to the entry form at the first section with `return_to=response`, and each section name links to its section

#### Scenario: Online response shows no Edit
- **WHEN** an `editor` opens the detail surface of an online session
- **THEN** no entry-form link is rendered, and the entry URL for that session answers 404

#### Scenario: Viewer sees no Edit
- **WHEN** a `viewer` opens the detail surface of a paper session
- **THEN** no entry-form link is rendered

#### Scenario: Lapsed workspace sees no Edit
- **GIVEN** the organisation's subscription has lapsed and no trial covers `operator_entry`
- **WHEN** an `editor` opens the detail surface of a paper session
- **THEN** no entry-form link is rendered

#### Scenario: Map objects carry the edit link of their section
- **GIVEN** a paper session with a point answer in section S2
- **WHEN** an `editor` opens its detail surface
- **THEN** the geo payload's feature for that point carries an `edit_url` to S2 with `return_to=map`

### Requirement: Return mode saves one section and goes back to the response
The entry form SHALL render, on a section URL with `return_to` = `response` or `map`, a **Save
and return to Responses** button beside Back/Next and point *Stop* at the response. Every section URL the form
navigates to while in return mode SHALL keep the marker. Submitting with that button SHALL save
the current section through the same writer as Next and redirect to Responses with
`?session=<id>` (plus `&map=1` for `map`), without marking the session completed. Any other
`return_to` value SHALL be ignored.

#### Scenario: Move a point and come back
- **GIVEN** a paper session with a point in section S2
- **WHEN** the operator opens S2 with `return_to=map`, posts the point at new coordinates with *Save and return*
- **THEN** the point answer holds the new coordinates and the response is a redirect to Responses with `?session=<id>&map=1`

#### Scenario: Next keeps the marker
- **WHEN** the operator submits S1 with Next in return mode
- **THEN** the redirect goes to S2 with the same `return_to`

#### Scenario: Return does not finish an abandoned sheet
- **GIVEN** a paper session without `end_datetime`
- **WHEN** the operator saves a section with *Save and return*
- **THEN** `end_datetime` is still empty

#### Scenario: No marker, no button
- **WHEN** the operator opens an entry section without `return_to`
- **THEN** no *Save and return to Responses* button is rendered

### Requirement: Stored geometry is edited like freshly drawn geometry
The entry form SHALL restore a session's stored geo features as editable features of the same
kind a fresh drawing produces, so that a stored point can be moved, a stored line or polygon
reshaped, a stored feature deleted and its pop-up sub-answers changed; the section save SHALL
store exactly what the form posts. Re-posting a section exactly as the form renders it SHALL keep
every answer value — geometry, choices, text, numbers and geo sub-answers — unchanged.

#### Scenario: Reshape and delete
- **GIVEN** a paper session with a line and a polygon in the same section
- **WHEN** the operator posts the line with a moved vertex and omits the polygon
- **THEN** the line answer holds the new vertices and no polygon answer remains

#### Scenario: Re-label an object
- **GIVEN** a stored point whose pop-up sub-answer "Kind" is "Bench"
- **WHEN** the operator posts the point with "Kind" = "Tree"
- **THEN** the point's sub-answer reads "Tree"

#### Scenario: Unchanged resave keeps every value
- **GIVEN** a stored section with a choice, a text, a point with a sub-answer and a polygon
- **WHEN** the section is re-posted with the values the form renders
- **THEN** every answer value is equal to the stored one

### Requirement: Changes to a finished entered response are audited
The entry form SHALL write one `AuditLog` row, when any section of an operator session whose
`end_datetime` is already set is saved, with action `response_edit`, the survey, the operator as actor, and metadata
`session_id` and `section` (the section code) — no answer content. Saving a section of a session
still being entered for the first time SHALL write no such row.

#### Scenario: Edit of a finished sheet is audited
- **GIVEN** a completed paper session
- **WHEN** an `editor` saves its section S2
- **THEN** one `response_edit` row exists naming the session id and `S2`

#### Scenario: First entry is not an edit
- **WHEN** an operator enters a new sheet section by section up to Finish
- **THEN** no `response_edit` row exists
