## Context

Sites (epic #348) shipped v1 and v1.1 (waves A and B, PR #627, 2026-11-09): `Site` → ordered `SiteBlock`s,
one public page `/p/<slug>/`, a canvas builder (`sites/builder.html`, `js/site_builder.js`), every write
through `survey/services/sites.py`, translations keyed by block id in JSON columns
(`site_translations.py`), starters in `site_templates.py`, duplication in `sites.duplicate_site`. The Sites
Vision v2 (ops `requirements/vision/sites.md`) and the plan's decision D4 add pages. Production has no
sites yet on 2026-11-09, but the code must not assume that.

Owner decisions that bind this change: a new site starts with one page and multi-page structure comes
from templates (2026-11-09); primary actions in the block, refinements in Settings; reuse the app's
dialogs, no `confirm()`; one-click create.

## Goals / Non-Goals

**Goals:**
- Pages as a list with a menu, the home page at the site's address forever, existing sites unchanged.
- One place that knows "which page" for every read path (public page, builder, translations, screening,
  sitemap, events) so nothing still walks `site.blocks` as if it were one page.
- A Municipal site starter that shows the multi-page path in one click.

**Non-Goals:**
- Nested pages, page templates, per-page cover or width, redirects for renamed page addresses.
- Updates/News content (C2 #629): the News page of the starter holds a text block until C2 adds `updates`.
- Per-page visits (C4 #631) — it will key on `SitePage.pk`, nothing to prepare here.

## Decisions

### D1 · `SitePage` table, `SiteBlock.page` required
`SitePage(site FK CASCADE, title ≤ 60, slug ≤ 64 blank for home, order, in_menu, is_home, translations
JSON, created_at, updated_at)`; constraints: one `is_home` per site (partial unique), unique `(site, slug)`
for non-home pages. `SiteBlock.page` FK CASCADE, required after the backfill. `SiteBlock.site` stays (every
query, the event URL and the file-key logic use it); `SiteBlock.save()` fills `page` with the site's home
page when unset, so the hundreds of tests and any old path that create blocks with `site=` only keep
working and land on home. *Alternative*: blocks keep a nullable page and NULL means home — rejected, every
reader would carry the NULL rule. *Alternative*: drop `SiteBlock.site` — rejected, a rename/move this change
does not need (no data moves, ADR-001 §4).

### D2 · Home page is a row, fixed first, slug empty
The home page is a real row (`is_home=True`, `slug=''`, `order=0`) so its title is editable and
translatable and the menu needs no special case. It cannot be deleted or reordered: moving another page
first would silently change what printed QR codes open. `sites.home_page(site)` is `get_or_create`, called
by `create_site`, `duplicate_site`, the builder and `SiteBlock.save()`; the migration creates it for every
existing site. Default home title is "Home" in the creator's UI language at creation (creator text from
then on); the Municipal starter names it "About".

### D3 · URLs and reserved segments
`p/<slug:slug>/<slug:page>/` registered after `p/<slug>/report/` (Django tries routes in order, and
`events/…` is deeper). `sites.RESERVED_PAGE_SLUGS` lists `report events updates embed review feed new edit
admin api static media` — `updates` for C2's auto page, `embed` for C4. `page_slug_error(slug, page)` mirrors
`slug_error`; `unique_page_slug(site, title)` slugifies with `-2`, `-3` suffixes, falling back to `page`.

### D4 · One reader: `page_blocks(site, page, …)` and `pages_for(site)`
`blocks_for(site, page=None)` filters by page (home when None); `page_blocks` takes the page; a new
`sites.pages_for(site)` returns pages in order and `sites.page_for(site, slug)` resolves the request (home for
`''`, 404 otherwise). `nav_items` becomes `menu(site, pages, page, blocks)` → `{'pages': [...] or [],
'anchors': [...]}`: pages only when two or more are in the menu. `site_public` takes `page=''`.

### D5 · Builder: page tabs in the rail, `sitepage:<id>` selection
The rail gets a pages list (`sites/editor/_page_tabs.html`) above "Blocks". The builder already uses the
selection id `page` for the SITE settings panel ("Title and cover"); renaming it would touch every
selection path in `site_builder.js`, so site pages are selected as `sitepage:<id>` and get their own panel
(`_sitepage_panel.html`). Clicking a page tab is a navigation to `?page=<id>` (full reload): the canvas, the
outline and the panels are server-rendered per page and the builder already round-trips through redirects
for add/duplicate/delete; `_back()` carries `page`. Reorder posts `{order: [ids]}` (non-home) to
`editor_site_pages_reorder`, same pattern and SortableJS options as blocks. The block panel's *Move to page*
is a select that posts to `editor_site_block_move` (a refinement → Settings, per the owner rule).

### D6 · Service functions
`services.sites`: `add_page(actor, site)`, `update_page(actor, site, page, values)` (title, slug,
in_menu; `partial` like `update_settings`; refusal = `ValidationFailed`), `reorder_pages`, `delete_page`
(refuses home; deletes blocks through `delete_block` so files are released), `move_block(actor, site, block,
page)`; `save_block` and `duplicate_block` take/keep the page; `reorder_blocks` checks the order lists every
block of THAT page. All call `touched(site)` (re-screen when live) and write audit rows
(`site_page_create|update|delete`). `SiteServiceLayerTest` keeps guarding the views.

### D7 · Translations keyed `page:<id>:title`
`SitePage.translations = {lang: {'title': …}}`; `set_translations` accepts entity kind `page`;
`site_translations.occurrences` walks `pages_for(site)` and, per page, its title then its blocks (page
numbers of the table follow); `localize` translates the pages it is given. `duplicate_site` remaps
`page:<old>:title` hashes like block hashes. Ids in site keys are allowed (no draft copies, plan D2); the
survey rule "codes, never ids" is untouched.

### D8 · Starters with pages
`STARTERS[key]` gains optional `pages: [(title, slug, [blocks])]`; the first entry is the home page (its
slug ignored). `create_from_template` builds pages then blocks through `add_page`/`update_page`/`save_block`,
so a starter is valid by construction. Municipal site: About (heading, text, timeline, contacts) · Take part
(survey card, event) · Documents (documents, map) · News (heading, text — C2 swaps in `updates`).

### D9 · Public page header
`public.html` keeps one template: `{% if page.is_home %}` the hero, else `lp-hero lp-hero--page` with brand,
site title linked home and `<h1>` page title. The second-line anchors reuse `lp-nav`; pages render as
`lp-pages`. Links carry `?lang=` (non-primary) and `review=` through one `page_url` helper in the view, not
string-building in the template. Fixed strings: the pages `<nav>` aria-label reuses an existing respondent
msgid where one fits; any new public label gets all 75 respondent catalogs.

### D9b · Events
`site_event_register` and the cancel page build the return URL from `block.page` (`sites.page_url(site,
page)`), keeping the anchor.

## Risks / Trade-offs

- [A block created by the old code during the deploy window has no page] → `SiteBlock.save()` defaults to home in
  the new code; the old instance serves for seconds and production has no sites. The NOT NULL step runs in the
  same migration after the backfill.
- [Full reload on page switch feels heavier than the in-page selection] → pages are switched rarely; keeps one
  render path and no client-side state for "current page".
- [Renaming a page address breaks links already shared] → stated in the panel hint, like the site address;
  redirects for old page slugs are a later item if asked.
- [Translations tab page numbering changes for multi-page sites] → it is a label, not a key; CSV rows match by
  key.
- [Deleting a page deletes event registrations without the attendee-list warning] → the confirm dialog names
  the blocks and says registrations go too.

## Migration Plan

One migration `0129_site_pages`: create `SitePage`; add nullable `SiteBlock.page`; `RunPython` creates a home
page per site (title from the site's language catalog "Home", order 0) and sets `page` on its blocks; alter
`page` to non-null; add constraints. Reverse: drop the FK and the table (blocks keep `site` and order, so
rollback loses nothing but non-home pages). Post-deploy check: `Site.objects.filter(pages__is_home=True)
.count() == Site.objects.count()`.

## Open Questions

None blocking. Redirects for renamed page addresses and per-page covers wait for a customer request.
