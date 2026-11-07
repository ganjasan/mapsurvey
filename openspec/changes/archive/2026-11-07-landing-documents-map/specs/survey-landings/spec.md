## MODIFIED Requirements

### Requirement: Blocks are a closed set validated by one function
A landing SHALL hold an ordered list of blocks of the kinds `text`, `image`, `button`, `video`, `faq`, `timeline`, `survey`, `documents` and `map`, each with an optional title. Every write of a block SHALL pass `landings.clean_block(kind, data)`: rich text through `coerce_creator_html`, plain fields trimmed and capped, button URLs absolute `http(s)` only, video URLs accepted only when `layer_assets.embed_url` turns them into a YouTube or Vimeo player URL, FAQ 1–30 items, timeline 1–12 phases with an optional current phase, survey cards only for a survey linked to the same landing, map colours `#rrggbb` only and base maps only keys the workspace resolves. Unknown keys SHALL be dropped. Blocks SHALL be reordered by posting the full id list; ids of another landing SHALL be refused.

#### Scenario: Rich text is sanitised
- **WHEN** a text block is saved with `<p>Hello</p><script>alert(1)</script>`
- **THEN** the stored body is `<p>Hello</p>` without the script

#### Scenario: Unsafe button link refused
- **WHEN** a button block is saved with URL `javascript:alert(1)`
- **THEN** the save is refused with a field error naming the URL

#### Scenario: Video only from YouTube or Vimeo
- **WHEN** a video block is saved with `https://youtu.be/dQw4w9WgXcQ`
- **THEN** the stored embed is the YouTube player URL for that video, and a URL from another host is refused

#### Scenario: Reorder
- **WHEN** the builder posts the block ids in a new order
- **THEN** the blocks' order is 0..N in that order, and a list containing another landing's block id is refused with 400

## ADDED Requirements

### Requirement: A documents block offers files for download
A documents block SHALL hold 1–20 files uploaded by the creator, each with a title (default: the file name without its extension), stored on the public media tier under a random key. A file SHALL be accepted only when its extension is one of `pdf docx xlsx pptx odt ods odp doc xls ppt csv txt`, it is at most 25 MB, and its first bytes match its family (PDF header, zip header for OOXML/ODF, OLE header for legacy Office, UTF-8 text without HTML markup for csv/txt). Saving the block SHALL rename, remove and add files in one post; a block left without files SHALL be refused. The public page SHALL list each file with its title, type and size, linking to the file. File titles SHALL be screened with the landing's text.

#### Scenario: PDF added
- **WHEN** an editor adds a documents block with `summary.pdf` starting with `%PDF-`
- **THEN** a file titled "summary" is stored under `landing_files/` with a random name and the page lists it as PDF with its size

#### Scenario: Disguised HTML refused
- **WHEN** a file named `boards.pdf` whose content starts with `<html>` is uploaded
- **THEN** the save is refused with an error naming the file and nothing is stored

#### Scenario: Rename and remove in one save
- **WHEN** the block is saved with a new title for one file and the remove box ticked for another
- **THEN** the first keeps its file under the new title and the second is deleted

### Requirement: A map block shows the project area
A map block SHALL hold a FeatureCollection built from an uploaded GeoJSON file (FeatureCollection, Feature or geometry; at most 1 MB and 500 features; Point, LineString, Polygon or their Multi-forms; valid geometries within WGS84 bounds), keeping only each feature's geometry and a name (from `name`, `title` or `Name`), with coordinates rounded to 6 decimals. A save without a new file SHALL keep the stored area. The public page SHALL draw the area read-only on the chosen workspace base map (falling back to Streets), in the chosen colour, fitted to its bounds, and SHALL load the map library only when a map block is on the page.

#### Scenario: Polygon normalised
- **WHEN** a map block is saved with a Feature whose polygon has 10-decimal coordinates and properties `{"name": "Park", "owner": "x"}`
- **THEN** the stored FeatureCollection has one feature with properties `{"name": "Park"}` and 6-decimal coordinates

#### Scenario: Invalid file refused
- **WHEN** the upload is not JSON, has no geometry, or has a latitude of 120
- **THEN** the save is refused with an error and no block is created

#### Scenario: Leaflet only where needed
- **WHEN** a page with no map block renders
- **THEN** it does not load Leaflet; a page with a map block does
