## ADDED Requirements

### Requirement: The settings base-map picker scales and the position map shows the default
Survey settings SHALL show *Base maps* as one folded line naming the base maps that are on, opening
on click to a checklist that offers a filter when the workspace has more than eight base maps.
*Default base map* SHALL offer only the base maps that are on. The *Default position* map SHALL
draw the default base map from the provider table and SHALL redraw when the default changes. The
help text SHALL describe the control without naming storage keys.

#### Scenario: Folded list with a filter for many styles
- **WHEN** settings render for a workspace with nine base maps
- **THEN** *Base maps* is a closed fold naming the enabled ones, and opening it shows the checklist with a filter

#### Scenario: Position map follows the default
- **WHEN** the creator changes *Default base map* from Satellite to Topo
- **THEN** the *Default position* map redraws with Topo tiles
