## ADDED Requirements

### Requirement: New style starts from a preset and opens the editor
The library SHALL offer owners, admins and editors a *New style* button whose menu lists the presets the generator can rebuild (Streets, Paper A, Paper B) with their preview tiles. Choosing one SHALL create a workspace style named "New style" — with ` (2)`, ` (3)` … when the name is taken — whose version 1 is `pending` with that preset's settings, enqueue its publication, count one `map_styles` use, and redirect to the new style's editor.

#### Scenario: New style from Paper B
- **WHEN** an editor of a Pro workspace chooses *New style* → Paper B
- **THEN** a workspace style "New style" exists with version 1 `pending` carrying Paper B's settings, the publish task is enqueued, and the response redirects to its editor

#### Scenario: Second new style
- **WHEN** "New style" already exists and another is created
- **THEN** the new one is named "New style (2)"

#### Scenario: Menu lists rebuildable presets only
- **WHEN** an editor opens the library
- **THEN** the *New style* menu offers Streets, Paper A and Paper B and not Satellite or Topo; a viewer sees no *New style*

#### Scenario: Spent trial
- **WHEN** a Free workspace whose `map_styles` allowance is spent chooses *New style*
- **THEN** the Pro-required page answers and nothing is created

## MODIFIED Requirements

### Requirement: Duplicate, rename and delete
Owners, admins and editors SHALL be able to duplicate any style whose base the generator supports (`mapbox/streets-v12`): the copy is a workspace style named "<name> copy" with version 1 `pending`, published by a background task, and the response SHALL open the copy in the editor; open a workspace style in the editor, where its name is changed; delete a workspace style no survey references. Deleting a style that a survey references SHALL be refused with a message naming the surveys. Presets SHALL NOT be renamed, edited or deleted. Satellite and Topo SHALL show no *Duplicate*.

#### Scenario: Duplicate publishes in the background
- **WHEN** an editor duplicates Paper A
- **THEN** a new `MapStyle` of the workspace exists with version 1 `pending` carrying Paper A's settings, `publish_map_style_version` is enqueued on the `styles` queue, the response redirects to the copy's editor, and after the task runs the version is `ready` with a Mapbox id different from Paper A's

#### Scenario: Delete refused while in use
- **WHEN** an editor deletes a style one survey enables
- **THEN** nothing changes and the response names that survey

#### Scenario: Delete of an unused style
- **WHEN** an editor deletes a style no survey references
- **THEN** `archived_at` is set, the style leaves the page and the pickers, and a delete of its Mapbox style is enqueued

#### Scenario: Viewer cannot act
- **WHEN** a member with the `viewer` role posts to duplicate, rename or delete
- **THEN** the response is 403 and nothing changes

#### Scenario: Workspace card links to the editor
- **WHEN** the library renders a workspace style
- **THEN** its card carries *Edit* linking to the editor and no separate rename form; a preset's card carries no *Edit*
