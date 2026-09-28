## MODIFIED Requirements

### Requirement: Detail surface replaces the Session Details modal
When `RESPONSES_V2` is on, the workspace SHALL open a detail surface whenever a session is
activated from a table row, a feed entry, or a map feature's open-response action. The surface
SHALL render from the existing `analytics_session_detail` endpoint: a side drawer at ≥1200px, an overlay panel at 768–1199px, and a full-screen view below
768px. The surface SHALL show start time, duration, version, status; all answers grouped by
section; and geo answers with a view-only mini-map. The mini-map SHALL be mounted through the
shared editor map helper on every open, so that opening responses in succession — from the table,
from prev/next, or from a map feature — never fails on the previous open's map, and SHALL draw its
features only once its container has a size, whatever the form factor.

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

#### Scenario: Opening responses in succession keeps the mini-map alive
- **WHEN** a creator opens a response with geo answers, then another, then steps back with "previous"
- **THEN** each open shows that response's features on the mini-map and no error is raised on any open

#### Scenario: The mini-map draws once the overlay drawer is laid out
- **WHEN** a response is opened at 768–1199px or below 768px, where the drawer is an overlay or full-screen and has no size at swap time
- **THEN** the mini-map waits for the container to be laid out and then shows the features fitted to view

#### Scenario: The v1 modal still gets its mini-map
- **WHEN** `RESPONSES_V2` is off and a session is opened in the Session Details modal
- **THEN** the mini-map renders once the modal is shown, through the same helper, with no modal-specific hook in the partial
