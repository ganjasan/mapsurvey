# responses-detail-drawer Specification

## Purpose
TBD - created by archiving change responses-v2-refactor. Update Purpose after archive.
## Requirements
### Requirement: Detail surface replaces the Session Details modal
When `RESPONSES_V2` is on, the workspace SHALL open a detail surface whenever a session is
activated from a table row, a feed entry, or a map feature's open-response action. The surface
SHALL render from the existing `analytics_session_detail` endpoint: a side drawer at ≥1200px, an overlay panel at 768–1199px, and a full-screen view below
768px. The surface SHALL show start time, duration, version, status; all answers grouped by
section; and geo answers with a view-only mini-map.

#### Scenario: Desktop row click opens the drawer
- **WHEN** a creator clicks a table row at ≥1200px
- **THEN** the drawer opens beside the table with that session's details and the row is highlighted

#### Scenario: Phone opens full-screen
- **WHEN** a creator taps a response card below 768px
- **THEN** the detail renders full-screen with a back affordance

#### Scenario: File answers render as media
- **WHEN** the opened session contains photo, audio or document answers (respondent file uploads,
  PR #127)
- **THEN** the detail surface renders them as the session-detail partial does today — image
  thumbnails linking to the file, inline audio player, download links — in every form factor

### Requirement: Status and trash actions live in the detail surface
The detail surface SHALL provide the validation status control (approved / on hold / not
approved) and a trash action for the open session, applying them via the existing session action
endpoints without closing the surface (trash MAY close it after confirmation). Destructive
actions SHALL use an in-page confirmation, not `window.confirm`.

#### Scenario: Approve from the drawer
- **WHEN** the creator sets status "approved" in the drawer
- **THEN** the session's status persists and the table/feed chip updates without a page reload

#### Scenario: Trash with in-page confirm
- **WHEN** the creator activates Trash in the drawer
- **THEN** an in-page confirmation appears and, on confirm, the session moves to trash

### Requirement: Prev/next triage within the current list
The detail surface SHALL offer previous/next navigation iterating the session list as currently
filtered and sorted at the moment the surface was opened. When the underlying list changes while
the surface is open, navigation SHALL continue over the opened snapshot and the surface SHALL
indicate that the list has changed.

#### Scenario: Next follows the filtered order
- **WHEN** the table is filtered to "Issues" and the drawer is opened on the first flagged session
- **THEN** "next" opens the following flagged session in the table's sort order

#### Scenario: List changes underneath
- **WHEN** a live refresh adds sessions while the drawer is open
- **THEN** prev/next still traverse the snapshot and a "list changed" hint is shown

