## 1. Model and migration

- [x] 1.1 `SitePage` model (title ≤ 60, slug, order, in_menu, is_home, translations, timestamps; one home per site, unique non-home slug per site) and `SiteBlock.page` FK; `SiteBlock.save()` defaults `page` to the site's home page
- [x] 1.2 Migration `0129_site_pages`: create table, nullable FK, backfill a home page per site and attach its blocks, make the FK required, add constraints; reverse drops both
- [x] 1.3 `sites.py` page helpers: `home_page`, `pages_for`, `page_for`, `RESERVED_PAGE_SLUGS`, `page_slug_error`, `unique_page_slug`, `PAGES_MAX = 12`, `page_url(site, page, lang=, review=)`; `blocks_for`/`page_blocks`/`next_order` per page; `menu()` replacing `nav_items`; `a11y_issues` per page

## 2. Service layer

- [x] 2.1 `create_site` creates the home page; `add_page`, `update_page` (partial, autosave errors), `reorder_pages` (home stays first, only this site's pages), `delete_page` (refuses home; blocks via `delete_block`), `move_block`; audit rows and `site_page_created` event (ids, page count)
- [x] 2.2 `save_block` / `duplicate_block` / `reorder_blocks` / `move_after` / `delete_block` act within the block's page
- [x] 2.3 `sites.duplicate_site` copies pages with translations and puts blocks on the copied pages; translation-source remap for `page:<id>:title`; `save_as_template` / `create_from_template` keep pages
- [x] 2.4 Starters with `pages`; Municipal site starter (About · Take part · Documents · News) built through the service

## 3. Public page

- [x] 3.1 Route `p/<slug>/<slug:page>/` after `report/`; `site_public(request, slug, page='')` resolves the page (404 unknown), draws its blocks, home hero vs compact page header, `<title>`, hreflang per page
- [x] 3.2 `public.html` + `site_public.css`: pages menu with `aria-current="page"`, anchors as second line, links keeping `lang` and `review`
- [x] 3.3 Event register/refusal/cancel return to the block's page
- [x] 3.4 Sitemap lists every page of public published sites; screening reads page titles and their translations

## 4. Builder

- [x] 4.1 Builder context per `?page=`; `_back()` carries the page; add/duplicate/delete/reorder block within the page
- [x] 4.2 `_page_tabs.html` in the rail (tabs, *Add page*, drag reorder of non-home), `_sitepage_panel.html` (title, address with hint, menu flag, *Delete page* with the app's confirm dialog naming the block count)
- [x] 4.3 Endpoints `editor_site_page_add`, `editor_site_page_edit` (autosave JSON/422), `editor_site_pages_reorder`, `editor_site_page_delete`, `editor_site_block_move`; viewer 403, lapsed read-only
- [x] 4.4 `site_builder.js`: `sitepage:<id>` selection, page autosave, page drag reorder, *Move to page* select in the block panel
- [x] 4.5 Canvas page menu under the page head, mirroring the public one; links open the page in the builder; autosaved titles update it

## 5. Translations

- [x] 5.1 `site_translations`: page title occurrences (`page:<id>:title`) page by page before the page's blocks; `localize` pages; `set_translations` accepts `page`; CSV round trip

## 6. Strings, help, changelog

- [x] 6.1 Creator strings in every offered creator catalog; any new public label in all respondent catalogs; compile
- [x] 6.2 Help `how-to/sites.md`: "Pages" section (add, reorder, menu, addresses, Municipal starter)
- [x] 6.3 What's new: no new card (one card per epic, owner rule) — extend `2026-11-08-sites.html` with pages
- [x] 6.4 CLAUDE.md Sites paragraph: pages, home row, `page:<id>` keys, reserved segments

## 7. Tests (`survey/tests/test_survey_sites.py`, GIVEN/WHEN/THEN)

- [x] 7.1 Model/migration: new site has one home page; backfill attaches blocks; block without page lands on home; constraints
- [x] 7.2 Public: page routes, unknown page 404, draft/unlisted per page, menu one page vs several, hidden page, lang/review links, `<title>`
- [x] 7.3 Builder and service: add/rename/slug errors/reserved/limit/reorder/delete home refused/delete with blocks and registrations/move block/cross-site 404/viewer 403/autosave 422
- [x] 7.4 Duplicate, template and Municipal starter keep pages; translations and outdated status for page titles; screening; sitemap; event redirect to page
- [x] 7.5 Run `./run_tests.sh survey.tests.test_survey_sites` and the translation/screening modules; then the full suite once before the PR
