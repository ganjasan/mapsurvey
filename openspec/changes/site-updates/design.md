## Context

C1 (pages, #628) is on `epic/sites-wave-c`. Blocks are a closed set (`sites.BLOCK_KINDS`, one cleaner, one
public template, one canvas include); rows inside a block (FAQ, contacts) live in `SiteBlock.data`. Owner
decisions 2026-11-09: updates are a SITE feed shown by blocks, each update has its own address, a "You said,
we did" entry is said → did + status.

## Goals / Non-Goals

**Goals:** a feed that any number of blocks show; addresses for the feed and every update (C3 links there);
"You said, we did" with a status badge; the builder rule "primary action in the block".

**Non-Goals:** telling subscribers (C3 #630); comments on updates; pictures in updates (a later block-level
gallery suffices); scheduled publishing; linking an update to a results block (later, with #347 reports).

## Decisions

### D1 · `SiteUpdate` table, not block rows
`SiteUpdate(site CASCADE, kind news|decision, date, title ≤160, body rich, said ≤2000 plain, status
included|partly|not|'', site_survey SET_NULL, link_url ≤500, is_published, translations JSON, created_by,
created_at, updated_at)`; index `(site, is_published, -date)`. A feed shown by several blocks and addressed
one by one cannot be rows of one block. `body` is the news text AND the decision's "what we did" — one rich
field, one sanitiser path, one translation key. *Alternative*: separate `did` column — rejected, two rich
fields that are never both used.

### D2 · Block kind `updates` reads the feed
`data = {count: 3|5|10|0 (all), kinds: ''|news|decision}`; `is_complete` is always true (it is a view), and
`block_card()` returns `{'updates': [...], 'more': bool}` for published updates, so `page_blocks` drops the
block when the list is empty — the results-block pattern. The builder passes `drafts=True`.

### D3 · Feed and update pages through `site_public`
Routes `p/<slug>/updates/` and `p/<slug>/updates/<int:id>/` go to `site_public` with `view='feed'|'update'`,
registered before `p/<slug>/<page>/` (`updates` is already a reserved page slug). Access, language, review
link, menu and header are the page code path; `public.html` swaps the block loop for
`sites/updates/_feed.html` / `_detail.html`. The page header's `page` is a lightweight stand-in (title =
"Updates" or the update's title, `is_home` false) so the template needs one branch, not a second page.

### D4 · Builder: add in the block, edit in the panel
The canvas makes forms inside a block inert, so *Add news* / *Add "You said, we did"* are buttons handled
in `site_pages.js` (POST, then go to `?page=…&select=update:<id>`). Cards carry
`data-select-target="update:<id>"`; every update of the site has a pane `update:<id>` in the side panel
(rendered once per builder load, like block panes). The autosave in `site_pages.js` is generalised from the
page form to any `form[data-autosave-json]` and updates labels by `data-label-for`. Text is edited in the
panel, not inline: an update is a small form (title, date, said, body, status, survey, link) and inline
rich editing would need the block-form serialisation that updates do not use.

### D5 · Service, translations, screening
`services.sites.add_update(actor, site, kind)`, `save_update(actor, site, update, values, partial=True)`
(validates everything first: title, ISO date, status, URL through `redirects.is_valid_redirect`, survey link
of this site; `coerce_creator_html` on body), `delete_update`. All call `touched(site)` (re-screen when live)
and write audit rows; publishing emits `site_update_published` (ids only). `site_translations` adds an
"Updates" group after the pages (`update:<pk>:title|body|said`); `set_translations` accepts entity kind
`update`; `localize` translates the updates it is given. `collect_site_text` reads updates and translations.

### D6 · Not copied
`sites.duplicate_site` copies no updates — a copy starts the NEXT engagement; its news would be false there.
The plan's D8 said "copies updates"; this is a deliberate change, stated in the spec.

## Risks / Trade-offs

- [A site's update pages add many sitemap entries] → only published updates of public sites; a council
  posts a few a month.
- [Editing in the panel is a step away from the canvas] → adding and opening are in the block; revisit inline
  editing if creators ask.
- [The full feed has no pagination] → fine to ~100 updates; add paging when a site gets there.

## Migration Plan

Migration `0130_site_updates`: create `SiteUpdate`, alter `SiteBlock.kind` choices (no data change). Reverse
drops the table; an `updates` block left behind is skipped by the public page (unknown kind is never drawn).
