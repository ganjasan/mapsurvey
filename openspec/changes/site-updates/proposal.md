## Why

A council's site is the record of its engagement: what was asked, what residents said and what changed
because of it. Today that record is a PDF on another site, and residents who took part never see the
answer. The Sites Vision v2 (FE-16; issue #629, epic #348 wave C, story S5) adds dated updates and "You
said, we did" entries; the presentation-round epic #349 names "you said, we did" as its second item. C3
(subscribers, #630) needs something to tell subscribers about, and each update needs an address to link to.

## What Changes

- **A site has a feed of updates** (`SiteUpdate`, owner decision 2026-11-09): dated entries of two kinds —
  **news** (title, rich text, optional link and linked survey) and **"You said, we did"** (title, what
  residents said, what we did, a status *included / partly / not included*, optional linked survey).
  Drafts stay in the builder; published updates appear on the site.
- **Block kind `updates`** shows the feed: the latest N (3, 5, 10 or all) of one kind or both. Several
  blocks show the same feed (the latest three on home, everything on News). With more updates than it
  shows, the block links to the full feed.
- **Every published update has its own address** `/p/<slug>/updates/<id>/`, and the full feed is
  `/p/<slug>/updates/` — the targets C3's mails link to. Both are in the sitemap.
- **Builder**: *Add news* / *Add "You said, we did"* inside the block (primary action in the block, owner
  rule); clicking a card opens the update in the side panel — kind fields, date, linked survey, link,
  *Published* switch — autosaved; *Delete update* through the app's dialog.
- Updates are **translated** on the Translations tab (`update:<id>:title|body|said`), **screened** with the
  site's text, and written only through the sites service.
- The Municipal site starter's News page gets an `updates` block instead of its placeholder text.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `survey-sites`: a site's update feed, the `updates` block, update pages, and the starter change.

## Impact

- **Model and migration** (additive): new `SiteUpdate`; `updates` added to the block kinds.
- **Code**: `survey/sites.py` (kind, cleaner, completeness, feed helpers), `survey/services/sites.py`
  (add/update/delete), `survey/site_views.py` (endpoints, feed and update pages), `survey/site_translations.py`,
  `survey/content_screening.py`, sitemap in `survey/views.py`, `survey/site_templates.py`, `survey/urls.py`.
- **Templates/static**: `sites/blocks/updates.html`, `sites/updates/_card.html`, `_feed.html`, builder pane
  `sites/editor/_update_panel.html`, canvas controls, `js/site_pages.js` (generic autosave), CSS.
- Strings in the 11 creator catalogs; help "Updates" section. No API/MCP surface for sites yet.
