## MODIFIED Requirements

### Requirement: Duplicate, rename and delete
Owners, admins and editors SHALL be able to duplicate any style whose base the generator supports (`mapbox/streets-v12`): the copy is a workspace style named "<name> copy" with version 1 `pending`, published by a background task; open a workspace style in the editor, where its name is changed; delete a workspace style no survey references. Deleting a style that a survey references SHALL be refused with a message naming the surveys. Presets SHALL NOT be renamed, edited or deleted. Satellite and Topo SHALL show no *Duplicate*.

#### Scenario: Duplicate publishes in the background
- **WHEN** an editor duplicates Paper A
- **THEN** a new `MapStyle` of the workspace exists with version 1 `pending` carrying Paper A's settings, `publish_map_style_version` is enqueued on the `styles` queue, and after the task runs the version is `ready` with a Mapbox id different from Paper A's

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
