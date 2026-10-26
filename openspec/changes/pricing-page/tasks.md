## 1. Plan cards

- [x] 1.1 `survey/templates/partials/_plan_cards.html`: Free / Pro / Done-for-you, period radios, `surface` + `prefix` params, Pro bullets from `billing.features`
- [x] 1.2 `survey/assets/css/plan_cards.css`: own tokens, dark mode, one column under 760px
- [x] 1.3 Template tag exposing the Pro feature labels to the partial

## 2. Public page and nav

- [x] 2.1 `views.pricing` + `path('pricing/')` + `pricing.html` (cards, payment FAQ, links to `/pro/` and `/services/`)
- [x] 2.2 `/pricing/` in `sitemap_xml`
- [x] 2.3 `base_landing.html`: nav and footer "Pro" → "Pricing"
- [x] 2.4 `_landing_pricing.html` renders the partial; drop "early access" text

## 3. Plan & billing

- [x] 3.1 `org_billing.html`: cards replace the Free/Pro boxes; current plan marked; one Upgrade button bound to the period radios; Get a quote; "Prices" → `/pricing/`

## 4. Strings and tests

- [x] 4.1 Strings: billing has never had catalog entries (no `billing/locale`, no billing msgids in `survey/locale`); translating the plan cards with the rest of the billing UI is a follow-up, not this change
- [x] 4.2 Move the "price lives in one place" test to `_plan_cards.html`; update tests that pinned the old text or `/pro/` in nav/footer
- [x] 4.3 Tests (GIVEN/WHEN/THEN): `/pricing/` anon + owner CTA, sitemap, nav, billing cards for owner/admin/Pro, yearly period posts yearly
- [x] 4.4 Run `./run_tests.sh survey` and `./run_tests.sh billing`; check pages in a browser at 1280 and 360 px
