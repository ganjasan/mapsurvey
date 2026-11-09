## Why

A site is one long page today. The Sites Vision v2 (2026-11-09, ops `requirements/vision/sites.md`,
FE-15; issue #628, epic #348 wave C, story S4) moves the module to **municipal sites** and project sites
that residents navigate — About · Take part · Documents · News — rather than scroll. Pages are also what
the rest of wave C stands on: updates (C2) live on a News page, the projects list (C5) is the council's home
page, visits (C4) are counted per page.

## What Changes

- A site has **one or more pages** (`SitePage`): a title, an address segment, an order and a menu flag.
  The **home page** is created with the site, always first, never deleted, and keeps the site's address
  `/p/<slug>/`; every other page is at `/p/<slug>/<page-slug>/`. Every block belongs to exactly one page.
- **Every existing site becomes a one-page site** with the same address, blocks and look (the migration
  creates a home page per site and attaches its blocks). A **new** site starts with one page — owner
  decision 2026-11-09: no "one page or several" choice before the first click.
- **Menu.** With one page the menu is the block headings, as today. With two or more pages the menu lists
  the pages (the current one marked), and the block headings of the current page become a second line.
  Pages other than home carry a compact header (site name as a link home, the page title as the heading);
  the cover is the home page's.
- **Builder.** The outline rail gets the site's pages above the blocks: *Add page* (one click, an
  untitled page), drag to reorder, select a page to edit its title, address and menu flag in the side
  panel, delete it with the app's dialog (its blocks go with it, and the dialog says how many). The canvas
  shows one page; `?page=<id>` names it. A block's Settings gain *Move to page*.
- **A Municipal site starter** next to Consultation and Master plan: About (home) · Take part · Documents ·
  News, each with its starter blocks. Duplicate, *Save as template* and *From a template* copy pages.
- Page titles are **translatable** (Translations tab rows, `page:<id>:title` keys, outdated detection),
  **screened** with the rest of the site's text, and every page of a public site is in the **sitemap**
  with its `hreflang` alternates.
- Event registration and cancellation return the resident to the page the event block is on; the review
  link and the language choice survive moving between pages.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `survey-sites`: a site is made of pages; the public page, menu, builder, templates, duplicate,
  translations, screening, sitemap and event flows become page-aware.

## Impact

- **Model and migration** (additive): new `SitePage`, `SiteBlock.page` FK; one migration creates a home
  page per existing site, attaches its blocks, then makes the FK required. Production has no sites yet
  (2026-11-09), so the backfill is small; the code path is still written for any number.
- **Code**: `survey/sites.py` (page helpers, `nav_items`, a11y lint per page, `duplicate_site`),
  `survey/services/sites.py` (page create/update/reorder/delete, block move, starters with pages),
  `survey/site_views.py` (public page per page, builder page selection, page endpoints, event redirects),
  `survey/site_templates.py` (Municipal site), `survey/site_translations.py`, `survey/content_screening.py`,
  the sitemap in `survey/views.py`, `survey/urls.py` (`/p/<slug>/<page>/`, editor page routes).
- **Templates and static**: `sites/public.html`, `sites/builder.html`, new `sites/editor/_page_tabs.html`
  and `_sitepage_panel.html`, `js/site_builder.js`, `css/site_public.css`, builder CSS.
- **Strings**: creator catalogs (builder, starter); respondent catalogs for the one new public label.
- **Help**: the Sites how-to page gains a "Pages" section. **What's new**: the wave C hero, amended later.
- No API/MCP surface exists for sites yet; nothing to change there.
