# map-style-rendering Specification

## Purpose
How a map style — a system preset or, later, a workspace style — is rendered on a map surface and published for print, and the decision record that fixes the path for the Map styles epic (#545).

## ADDED Requirements

### Requirement: The rendering path is a recorded decision
The repository SHALL hold an Architecture Decision Record at `openspec/docs/adr/0001-map-style-rendering-path.md` that names ONE of the paths `vector`, `hosted-raster` or `hybrid` as the way a map style reaches the respondent and creator map surfaces, with the measurements that led to it. The record SHALL state, for the chosen path, how the printed form's frame and the mark-recognition reference image are produced from the same style the respondent saw.

#### Scenario: Record present and decided
- **WHEN** the repository is checked out on `epic/map-styles` or any branch cut from it
- **THEN** `openspec/docs/adr/0001-map-style-rendering-path.md` exists, its `Status` line reads `Accepted`, and its `Decision` section names exactly one of `vector`, `hosted-raster`, `hybrid`

#### Scenario: Print path is part of the decision
- **WHEN** the ADR's `Decision` section is read
- **THEN** it names the API or renderer that produces the printed frame and the reference image for the chosen path, and the delay, if any, between saving a style and that frame reflecting it

#### Scenario: Measurements are reproducible
- **WHEN** the ADR's appendix is read
- **THEN** it names the survey, the viewport sizes, the zoom, the device for the phone numbers, the date and the number of runs behind every figure in the options table

### Requirement: A style is published to Mapbox by one script
`scripts/mapbox_style_publish.py` SHALL turn a settings document into a Mapbox GL style over the `streets-v12` base and create or update it in the Mapsurvey Mapbox account with a deterministic name, so that running the script twice with the same settings updates one style rather than creating two. The transformation from settings to style SHALL be a pure function that needs no network, and every network call SHALL go through one client object.

#### Scenario: Same settings, one style
- **WHEN** the script is run twice with the same settings document against a stubbed Styles API that already holds a style of that name
- **THEN** the second run issues a `PATCH` to that style's id and no `POST`

#### Scenario: An ambiguous name refuses to publish
- **WHEN** the account holds two or more styles with the settings' name
- **THEN** the script stops, naming every matching id, and creates or updates nothing

#### Scenario: Settings change the style, nothing else does
- **WHEN** `apply_settings` is called on a stored copy of the base style with `poi: false`
- **THEN** the result has no layer whose `source-layer` is `poi_label`, every other layer of the base style is present unchanged, and calling it again with `poi: true` returns the base style's layers in their original order

#### Scenario: Greyscale is a style, not a filter
- **WHEN** `apply_settings` is called with `greyscale: true`
- **THEN** every `fill-color`, `line-color`, `text-color` and `background-color` in the result is a grey (`#rrggbb` with equal channels), so the Static Images API renders the greyscale print frame without client-side processing

#### Scenario: Token never reaches a browser
- **WHEN** the script's module is scanned
- **THEN** it reads the token from `MAPBOX_STYLES_TOKEN` only, and no template under `survey/templates/` references `MAPBOX_STYLES_TOKEN`

### Requirement: Prototype code never leaves the branch
The measurement prototype (the dev-only `basemap_proto` query parameter, the `__proto__/style/` view and its module) SHALL NOT be present on `epic/map-styles` or `master`. MapLibre itself is not banned: the decision puts it on the style editor page (#543).

#### Scenario: Epic branch is clean
- **WHEN** every Python file, template and first-party script under `survey/` and `mapsurvey/` on `epic/map-styles` is scanned
- **THEN** none contains `basemap_proto`, `__proto__/style` or `proto_views`
