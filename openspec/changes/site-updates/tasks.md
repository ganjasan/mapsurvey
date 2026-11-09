## 1. Model and helpers

- [x] 1.1 `SiteUpdate` model + migration `0130_site_updates` (table, index, `updates` block kind choice)
- [x] 1.2 `sites.py`: `updates` kind (label, icon, library tile), cleaner (`count`, `kinds`), `is_complete`, `block_card` → published updates + `more`, `feed(site, kinds=, drafts=)`, update constants
- [x] 1.3 `duplicate_site` copies no updates (unchanged code path; test)

## 2. Service

- [x] 2.1 `add_update`, `save_update` (all fields validated first; `coerce_creator_html`; URL rule; survey link of this site), `delete_update`; audit rows; `site_update_published` event
- [x] 2.2 Municipal starter: News page gets an `updates` block set to all

## 3. Public

- [x] 3.1 Routes `p/<slug>/updates/` and `p/<slug>/updates/<id>/` → `site_public(view=…)`; 404 for drafts/other sites
- [x] 3.2 `sites/blocks/updates.html`, `sites/updates/_card.html`, `_feed.html`, `_detail.html`; status badges; "All updates" link; CSS
- [x] 3.3 Sitemap lists the feed and published updates; screening reads updates

## 4. Builder

- [x] 4.1 Endpoints `editor_site_update_add`, `editor_site_update_edit` (autosave JSON/422), `editor_site_update_delete`; viewer 403
- [x] 4.2 Canvas: the block's cards (drafts marked) with `data-select-target="update:<id>"`, *Add news* / *Add "You said, we did"* buttons; block settings form (count, kinds)
- [x] 4.3 `_update_panel.html` per update (kind fields, date, survey, link, Published switch, Delete with the app's dialog); `site_pages.js` generic autosave + add buttons

## 5. Translations

- [x] 5.1 `update:<id>:title|body|said` occurrences, `set_translations` entity `update`, `localize` updates

## 6. Strings, help, docs

- [x] 6.1 Creator catalogs (11); compile; hygiene test
- [x] 6.2 Help: "Updates and You said, we did" section; CLAUDE.md Sites paragraph

## 7. Tests (`SiteUpdatesTest`, GIVEN/WHEN/THEN)

- [x] 7.1 Model/service: news and decision saved, drafts private, refusals 422, survey unlink keeps update, not copied
- [x] 7.2 Block: latest N + "All updates" link, kind filter, empty block skipped, builder shows drafts, add in block, viewer 403
- [x] 7.3 Pages: feed and update addresses, draft 404, `<title>`, sitemap, translations, screening, Municipal starter
- [x] 7.4 Run `test_survey_sites` + i18n hygiene; full suite once before the PR
