## Why

Issue #607 (epic #348, Sites v1.1 wave A, story S8). A consultancy runs the same kind of engagement for client after client; rebuilding the site from an empty page each time is the hand work the profile says they pay to avoid.

## What Changes

- **Duplicate** on every row of the Sites list and **Duplicate site** in Site settings: a new unpublished site titled "<title> (copy)" with its own address, the same settings (language, width, visibility, cover), survey links, blocks with their headings, menu flags and data, and the files of documents blocks (stored objects shared). Event registrations are never copied.
- Survey cards and results blocks of the copy point at the copy's own survey links.
- A copy is a new site: it counts as a Pro use exactly like *New site* (trial allowance included).
- Templates ("Save as template", starter sites) are wave B.

## Capabilities

### Modified Capabilities
- `survey-sites`: a site can be duplicated.

## Impact

`sites.duplicate_site`, `site_views.editor_site_duplicate`, URL `editor_site_duplicate`, `list.html`, `_page_panel.html`, help, catalogs. No migration.
