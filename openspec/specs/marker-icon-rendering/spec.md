# marker-icon-rendering Specification

## Purpose
TBD - created by archiving change editor-icon-picker-expansion. Update Purpose after archive.
## Requirements
### Requirement: One resolver maps an icon value to a glyph on every surface
An `icon_class` value SHALL be resolved by a single helper on the server (`survey/marker_icons.py`
with a `marker_icon` template tag) and a single helper in the browser (`MarkerIcon`). A value of
the form `<set>:<name>` SHALL resolve to an SVG `<use>` of symbol `<set>-<name>` from that set's
sprite; any other non-empty value SHALL resolve to a Font Awesome `<i>` with the value as its
class list, unchanged. No surface SHALL build the icon markup itself or prepend a legacy `fa `
prefix. The surfaces are: the respondent map marker, the crosshair overlay for placing and
editing a point, the geo draw button card, the star-rating icon, and the editor picker preview
and grid.

#### Scenario: Font Awesome value renders as before
- **WHEN** a point question stores `fas fa-bus`
- **THEN** the respondent marker, crosshair overlay and draw button render `<i class="fas fa-bus …">`

#### Scenario: Map-set value renders as SVG
- **WHEN** a point question stores `maki:bench`
- **THEN** the same surfaces render an `<svg>` whose `<use>` references the Maki sprite symbol `maki-bench`, filled with the icon colour

#### Scenario: Legacy prefix is gone
- **WHEN** the respondent page renders a marker for any Font Awesome value
- **THEN** the class list starts with the stored value and contains no bare `fa` token added by the page

### Requirement: SVG glyphs sit where font glyphs sit
Inside the pin and the crosshair overlay an SVG glyph SHALL be drawn at the same size and
offset as a Font Awesome glyph, in the icon colour, so a Maki pin and a Font Awesome pin look
alike apart from the drawing.

#### Scenario: Pin geometry is shared
- **WHEN** a Maki and a Font Awesome marker are rendered side by side
- **THEN** both glyphs are centred horizontally in the pin at the same vertical offset and size

### Requirement: Unknown map-set values fall back to the default pin
A `<set>:<name>` value that no sprite symbol exists for SHALL resolve to the default Font
Awesome pin (`fas fa-map-marker-alt`) on both sides. A Font Awesome-shaped value SHALL be
passed through even when the catalog does not list it.

#### Scenario: Unknown symbol
- **WHEN** a question stores `temaki:does-not-exist`
- **THEN** the marker renders the default pin icon

#### Scenario: Unlisted Font Awesome class passes through
- **WHEN** a question stores `fas fa-some-pro-icon`
- **THEN** the marker renders `<i class="fas fa-some-pro-icon …">`

### Requirement: Sprites are static assets discovered from the page
Maki and Temaki sprites SHALL be generated symbol sheets under static files, each symbol keeping
its own viewBox and carrying no fill so CSS colour applies. Pages that draw markers SHALL expose
the hashed sprite URLs to the browser resolver via a `data-icon-sprites` attribute rendered with
`{% static %}`; the resolver SHALL NOT hard-code a static path.

#### Scenario: Sprite URL survives static hashing
- **WHEN** `collectstatic` renames `maki.svg` with a content hash
- **THEN** the rendered `data-icon-sprites` attribute carries the hashed URL and markers still draw

#### Scenario: Symbols are colourable
- **WHEN** the Maki sprite is generated
- **THEN** no `<symbol>` or descendant carries a `fill` attribute

### Requirement: Font Awesome stylesheet version matches the catalog
Every base template SHALL load Font Awesome Free 5.15.4, the version the catalog is generated
from, so the picker never offers a glyph the stylesheet cannot draw.

#### Scenario: Templates agree
- **WHEN** the base, survey and editor base templates render
- **THEN** each references the 5.15.4 stylesheet and none references 5.8.1

