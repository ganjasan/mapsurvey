## MODIFIED Requirements

### Requirement: A landing is a workspace-owned public page
The system SHALL provide `Landing`, owned by one `Organization`, with a title, a plain-text summary, an optional cover picture on the public media tier under a random key, a unique slug, a page language, a visibility (`public` or `unlisted`) and a published flag. Members with the owner, admin or editor role of that workspace SHALL create, edit, publish, unpublish and delete its landings; viewers SHALL see the builder read-only; anyone else SHALL get 404 for a landing's builder URL, whatever their active workspace.

The builder SHALL be a canvas: it SHALL render every block with the same templates as the public page, SHALL let the creator edit headings and text in place, SHALL show a toolbar on the hovered block (drag, move up, move down, duplicate, settings, delete) and a "+" between blocks that opens the block library, SHALL list the blocks in an outline that scrolls to and selects a block, and SHALL show the selected block's non-text settings in a side panel (the page's settings when nothing is selected). Changes SHALL be saved automatically: a post with `autosave=1` SHALL answer JSON with the re-rendered block and outline row, or `422` with field errors; a block with incomplete data (empty text, no files, no area, no question, no date) SHALL be kept in the builder and SHALL NOT be drawn on the public page. Publishing, the listed/unlisted switch, the address and the QR code SHALL live in one popover on the Publish button. A desktop / phone toggle SHALL reflow the canvas to 390 px.

#### Scenario: Editor creates a landing
- **WHEN** an editor of a Pro workspace posts a title "Riverside Park plan" to create a landing
- **THEN** a draft landing exists in that workspace with slug `riverside-park-plan` and the browser is sent to its builder

#### Scenario: Viewer cannot change a landing
- **WHEN** a viewer posts to any builder endpoint of a landing of their workspace
- **THEN** the response is 403 and nothing changes

#### Scenario: Another workspace's landing is invisible
- **WHEN** a member of workspace A opens the builder URL of a landing of workspace B
- **THEN** the response is 404

#### Scenario: Slug rules
- **WHEN** settings are saved with slug `Edit`, `ab`, or a slug another landing has
- **THEN** the save is refused with a field error and the landing keeps its slug

#### Scenario: Autosave answers the re-rendered block
- **WHEN** the builder posts a text block's new body with `autosave=1`
- **THEN** the answer is JSON with `ok` true, the block's canvas HTML containing the new body and its outline row, and the body is stored sanitised

#### Scenario: Autosave refusal keeps the block
- **WHEN** the builder posts a button block with URL `javascript:alert(1)` and `autosave=1`
- **THEN** the answer is 422 JSON with an error for `url` and the stored block is unchanged

#### Scenario: Incomplete block stays off the public page
- **WHEN** a text block is added from the library and never written in
- **THEN** the builder shows it (empty, selected) and the published page does not

#### Scenario: Canvas renders every kind editable
- **WHEN** an editor opens a landing with one block of every kind
- **THEN** every block renders in the canvas with its kind tag, a toolbar and editable text fields, and a panel exists for each

#### Scenario: Read-only canvas
- **WHEN** a viewer, or an editor of a lapsed workspace, opens the builder
- **THEN** the canvas renders without editable fields, toolbars or the "+" lines, and the panel inputs are disabled
