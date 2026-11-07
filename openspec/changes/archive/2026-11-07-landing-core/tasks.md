## 1. Data

- [x] 1.1 Models `Landing`, `LandingSurvey`, `LandingBlock` (random-key image paths); `ContentReview.landing` + nullable `survey` + one-of constraint; migration
- [x] 1.2 `billing/features.py`: `landing_pages` (Pro), trial allowance 1

## 2. Domain module

- [x] 2.1 `survey/landings.py`: `BLOCK_KINDS`, `clean_block`, `slug_error`, `unique_slug`, `linkable_surveys`, `survey_card`, `page_blocks`, `nav_items`
- [x] 2.2 `content_screening`: `collect_landing_text`, `screen_landing`, `is_landing_held`, `report_landing`; subject-aware notice context, review page, `confirm_phishing`

## 3. Builder

- [x] 3.1 `survey/landing_views.py`: list, create, builder, settings, cover, survey link/unlink/reorder, block add/edit/delete/reorder, publish/unpublish, delete; role + Pro gates; screening triggers; events
- [x] 3.2 Templates `landings/list.html`, `landings/builder.html`, partials for block list, block forms, survey list; `js/landing_builder.js`, `css/landing_builder.css`
- [x] 3.3 Sidebar row in `app_nav.MODULES` + active mapping + Pro mark

## 4. Public page

- [x] 4.1 `landing_public` + `landing_report` views, URLs `/p/<slug>/`, `/p/<slug>/report/`; `landings/public.html` + block partials; `css/landing_public.css`
- [x] 4.2 Sitemap entry; `/p/` in `POSTHOG_EXCLUDED_PREFIXES`; OG tags; noindex for unlisted

## 5. Tests, docs, strings

- [x] 5.1 `survey/tests/test_survey_landings.py` covering every scenario; abuse-review scenarios in its module
- [x] 5.2 Help page `how-to/landing-pages.md` + `help_links` key; translations in the offered catalogs
- [ ] 5.3 Full suite, `openspec validate landing-core --strict`
- [x] 5.4 Dev check: build a landing with every block, publish, open `/p/<slug>/` on desktop and phone width; screenshots
- [ ] 5.5 PR into `epic/landing-pages`, merge, archive
