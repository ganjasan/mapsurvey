## ADDED Requirements

### Requirement: The object editor is a full-page screen per layer
The editor SHALL provide a page at `/editor/surveys/<uuid>/layers/<id>/` for owners,
reachable from the Reference layers card's "Open editor" action, laid out as an object
list, a map with drawing tools and an object card editor. It SHALL return 404 when
`MAP_REFERENCE_LAYERS` is off and refuse non-owners.

#### Scenario: Owner opens the editor
- **WHEN** an owner clicks "Open editor" on a layer card
- **THEN** the page shows that layer's objects in the list, on the map, and an empty card panel

#### Scenario: Collaborator without owner role
- **WHEN** a viewer-role collaborator requests the page
- **THEN** the request is refused

### Requirement: Objects can be drawn on the map
The map SHALL offer Leaflet.draw tools for point, line and polygon plus edit and delete. A
finished drawing SHALL create an object with an auto-generated key and a placeholder title,
select it and open its card. Editing geometry on the map SHALL save through the object's
geometry endpoint.

#### Scenario: Draw a point
- **WHEN** the owner selects the point tool and clicks the map
- **THEN** an object is created at that location, appears in the list and its card opens with the title focused

#### Scenario: Move an object
- **WHEN** the owner uses the edit tool to drag an existing point and confirms
- **THEN** the object's geometry is updated and the layer's derived GeoJSON changes

### Requirement: Three import paths into objects
The editor SHALL import objects from a GeoJSON file (with a mapping of properties to title,
category, description, link and key, previewed as a dry-run report), from a CSV with
latitude/longitude columns, and SHALL import content from a CSV without coordinates matched
to existing objects by key, then by title. Rows that match nothing SHALL be reported, not
silently dropped.

#### Scenario: GeoJSON import with mapping
- **WHEN** the owner imports a 214-feature GeoJSON mapping `name→title`, `line→category`, `id→key`
- **THEN** the dry-run reports 214 objects to create and 0 collisions, and confirming creates them

#### Scenario: CSV with coordinates
- **WHEN** the owner imports a CSV with `title, lat, lng, category` columns
- **THEN** one point object per row is created with those fields

#### Scenario: Content CSV matched by title
- **WHEN** the owner imports a CSV with `title, description, link` for objects that already exist
- **THEN** matching objects receive the description and link, and unmatched rows are listed in the report

### Requirement: Photo folder import matched by filename
The editor SHALL accept a multi-file image upload and attach each file to the object whose
key, then title, equals the filename stem (case-insensitive, extension ignored), reporting
unmatched files.

#### Scenario: Match by key
- **WHEN** the owner drops `m-034.jpg` and `m-035.jpg`
- **THEN** each becomes an image asset of the object with that key, as cover if the object had none

#### Scenario: Unmatched file reported
- **WHEN** a dropped file's stem matches no key and no title
- **THEN** it is not stored and the report names it

### Requirement: The list is built for hundreds of objects
The list SHALL filter instantly by search text, category chips, and problem chips ("no
photo", "no text"); SHALL support multi-select with bulk "set category" and "delete"; SHALL
move selection with ↑/↓ and open with Enter; and the map SHALL follow the selection. The
list SHALL render 1000 objects without visible lag by virtualising rows.

#### Scenario: Problem chip
- **WHEN** the owner activates the "no photo" chip on a 214-object layer with 37 objects lacking images
- **THEN** the list shows those 37, the map dims the others, and the count reads 37

#### Scenario: Bulk category
- **WHEN** the owner selects three objects and applies "Set category → Метро"
- **THEN** all three objects carry that category and the chips' counts update

#### Scenario: Keyboard navigation
- **WHEN** the owner presses ↓ with an object selected
- **THEN** the next visible object is selected, its card loads, and the map pans to it

### Requirement: Object card editor with autosave
The card SHALL edit title, category (pick or type), key (read-only after creation), link,
rich-text description (Quill with image upload), ordered attachments with cover marking,
and geometry ("move on map"). Field edits SHALL autosave with a saved/saving/error
indicator; description SHALL pass `coerce_creator_html` on save. Prev/Next SHALL move
through the currently filtered list.

#### Scenario: Autosave a title
- **WHEN** the owner edits the title and pauses
- **THEN** a PATCH is sent, the list row updates, and the indicator shows "Saved"

#### Scenario: Reorder attachments
- **WHEN** the owner drags an image above the current cover
- **THEN** it becomes the cover in the list thumbnail and the card preview

#### Scenario: Delete an object that has answers
- **WHEN** the owner deletes an object that respondents have answered about
- **THEN** a confirmation states the number of answers that will be removed before proceeding

### Requirement: Empty layer offers the three ways in
A layer with no objects SHALL show an empty state offering "Draw on the map", "Import
GeoJSON" and "Import CSV with coordinates".

#### Scenario: New layer
- **WHEN** the owner opens the editor of a layer with zero objects
- **THEN** the empty-state panel with the three entry points is shown over the map
