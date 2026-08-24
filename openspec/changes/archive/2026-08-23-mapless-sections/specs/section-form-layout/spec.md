# section-form-layout Specification

## ADDED Requirements

### Requirement: A form-layout section renders as a full-width classic form
When a section has `layout = "form"`, the respondent page SHALL render that section as a
centered full-width form — questions stacked down the page — with the map and all
map-coupled chrome (draw bar, crosshair, basemap switcher, panel-hide button) hidden.
Sections with `layout = "map"` (the default, and any unrecognized stored value) SHALL
render exactly as before this change.

#### Scenario: Form section hides the map
- **WHEN** a respondent opens a section with `layout = "form"`
- **THEN** the question panel spans the page as a centered column and the map is not visible

#### Scenario: Map section is unchanged
- **WHEN** a respondent opens a section with `layout = "map"`
- **THEN** the panel-beside-map rendering is byte-identical to the pre-change output

### Requirement: Layout mode follows HTMX navigation in both directions
Navigating between sections of different layouts within one respondent session SHALL
switch the page mode without reloading the page or destroying the persistent map instance:
map → form hides the map, form → map restores it with its previous state.

#### Scenario: Welcome form into map section
- **WHEN** a respondent submits a `form` head section whose next section is `layout = "map"`
- **THEN** the map appears with the survey's start position without a full page load

#### Scenario: Back navigation restores form mode
- **WHEN** a respondent on a `map` section navigates back to a `form` section
- **THEN** the map is hidden again and the form renders full-width

#### Scenario: Direct load of a form section has no map flash
- **WHEN** a respondent loads a `form` section's URL directly
- **THEN** the initial server-rendered HTML already carries the form-layout mode — the map
  is never visible, not merely hidden after scripts run

### Requirement: Geolocation is not requested on a form section
The browser geolocation prompt SHALL NOT be triggered while a `form` section is active,
even when the survey or section has geolocation enabled.

#### Scenario: Welcome page asks for nothing
- **WHEN** a respondent opens a `form` head section of a survey with `use_geolocation = true`
- **THEN** no geolocation permission prompt appears until a `map` section is shown

### Requirement: The forward button label is the creator's to name
Each section SHALL accept an optional creator-defined forward-button label (with
per-language translations); when set, it SHALL replace the default Next/Finish label for
that section. Empty SHALL mean the existing defaults — no label is ever inferred from the
section's position or layout.

#### Scenario: Welcome page gets a Start button by authorship
- **WHEN** the creator sets the head section's button label to "Start"
- **THEN** the rendered forward button reads "Start"

#### Scenario: No custom label means the old defaults
- **WHEN** a section has no custom label
- **THEN** the button reads "Next" (or "Finish" on the last section) exactly as before

#### Scenario: The label follows the respondent's language
- **WHEN** a section's label has a translation for the respondent's selected language
- **THEN** the translated label renders

### Requirement: Geo questions and form layout exclude each other
A `form` section SHALL NOT contain geo questions (`point`, `line`, `polygon`). The system
SHALL enforce this at question creation/save time and at layout-switch time; there is no
rendering fallback for a geo question inside a form section because the state is
unreachable through the product.

#### Scenario: Geo question rejected in a form section
- **WHEN** a request tries to save a `point` question into a section with `layout = "form"`
- **THEN** the save is refused with an error

#### Scenario: Layout switch refused while geo questions exist
- **WHEN** a creator tries to set `layout = "form"` on a section containing a `polygon` question
- **THEN** the change is refused with a message naming the blocking questions
