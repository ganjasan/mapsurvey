## ADDED Requirements

### Requirement: Responses maps share one mount lifecycle
Every Leaflet map on the Responses page SHALL be created through one shared helper
(`EditorMap.mount`), never by a direct `L.map(...)` call in a template — the Map pane, the Overview
thumbnail, the response detail mini-map and the full-size response modal alike. The helper SHALL keep
the map instance on its container element, never in a page global; SHALL dispose any map already
mounted on that element, or whose element has left the document, before creating a new one; SHALL
never raise while disposing; and SHALL run a surface's layer-adding and fitting code only once the
container has a non-zero size.

Rationale: the drawer mini-map is re-created on every HTMX swap. Holding the previous instance in a
global and calling `remove()` on it after its DOM was discarded threw once, left Leaflet's
container id half-cleared, and then threw "Map container is being reused by another instance" on
every later open in that session. Drawing before layout threw on the first polygon. One helper
answers all three questions once.

#### Scenario: A second response replaces the first mini-map without error
- **WHEN** a creator opens one response's detail and then another
- **THEN** the first mini-map is disposed without raising and the second mounts and draws its features

#### Scenario: A map mounted into a hidden container draws when it becomes visible
- **WHEN** a surface mounts a map while its container is 0×0 (an overlay drawer before layout, a hidden pane)
- **THEN** no layer is added and nothing is fitted until the container has a size, after which the surface's features are drawn once

#### Scenario: A half-torn map cannot poison its container
- **WHEN** Leaflet's own `remove()` throws part-way through disposing a map
- **THEN** the container is still left mountable — its Leaflet id and panes cleared — and the next mount on it succeeds

#### Scenario: A swapped-away element takes its map with it
- **WHEN** HTMX discards the element a map is mounted on
- **THEN** the map is disposed with the element and no reference to it survives the swap

#### Scenario: A direct Leaflet mount in an analytics template fails the build
- **WHEN** an analytics template calls `L.map(` instead of the helper
- **THEN** the source guard fails, naming the template
