## 1. Models & Migration

- [x] 1.1 Add `Competitor` model to `survey/models.py` with fields: `slug` (SlugField, unique), `display_name` (CharField, 100), `is_active` (BooleanField, default False), `created_at` (DateTimeField, auto_now_add)
- [x] 1.2 Add `ComparisonPage` model to `survey/models.py` with fields: `competitor` (FK to Competitor, on_delete=CASCADE, related_name='comparison_pages'), `page_type` (CharField with choices: 'alternative', 'vs', 'migrate'), `status` (CharField with choices: 'draft', 'published', default='draft'), `last_fact_checked` (DateField), `unique_together = [('competitor', 'page_type')]`
- [x] 1.3 Generate migration via `python manage.py makemigrations survey` and inspect the output
- [x] 1.4 Apply migration locally with `python manage.py migrate`

## 2. Admin Registration

- [x] 2.1 Register `Competitor` in `survey/admin.py` with `list_display = ['slug', 'display_name', 'is_active']`, `prepopulated_fields = {'slug': ('display_name',)}`
- [x] 2.2 Register `ComparisonPage` in `survey/admin.py` with `list_display = ['competitor', 'page_type', 'status', 'last_fact_checked']`, `list_filter = ['status', 'page_type']`, `list_editable = ['status']`

## 3. Views

- [x] 3.1 Add `comparison_page(request, page_type, competitor_slug)` to `survey/views.py`: decorated with `@lang_override('en')`; fetches `ComparisonPage.objects.select_related('competitor').get(competitor__slug=competitor_slug, page_type=page_type)` (404 on `DoesNotExist`); raises `Http404` if `status='draft'` and `not request.user.is_staff`; renders `comparisons/<competitor_slug>/<page_type>.html` with context `{'competitor': page.competitor, 'page': page, 'is_draft': page.status == 'draft'}`
- [x] 3.2 Add `comparisons_hub(request)` to `survey/views.py`: decorated with `@lang_override('en')`; queries `Competitor.objects.filter(is_active=True).prefetch_related('comparison_pages')`; for each competitor, filters pages based on `request.user.is_staff` (anonymous see only `status='published'`, staff see all); passes list of `(competitor, page_list)` tuples to `comparisons/hub.html`
- [x] 3.3 Extend `sitemap_xml` in `survey/views.py` to include hub URL `/alternatives/` always, plus every published `ComparisonPage` URL constructed from `{page_type: url_pattern}` dict

## 4. URL Patterns

- [x] 4.1 Add URL patterns to `survey/urls.py` before the catch-all survey routes: `path('alternatives/', views.comparisons_hub, name='comparisons_hub')`, `path('alternatives/<slug:competitor_slug>/', views.comparison_page, kwargs={'page_type': 'alternative'}, name='comparison_alternative')`, `path('vs/<slug:competitor_slug>/', views.comparison_page, kwargs={'page_type': 'vs'}, name='comparison_vs')`, `path('migrate-from-<slug:competitor_slug>/', views.comparison_page, kwargs={'page_type': 'migrate'}, name='comparison_migrate')`

## 5. Shared Partials

- [x] 5.1 Create `survey/templates/comparisons/_draft_banner.html`: renders a `<div class="draft-banner">` with text "Draft — visible to staff preview only. Not indexed by search engines."
- [x] 5.2 Create `survey/templates/comparisons/_legal_disclaimer.html`: receives `page` in context; renders `<section class="comparison-disclaimer">` with text "{{ competitor.display_name }} is a registered trademark of its respective owner. Mapsurvey is not affiliated with {{ competitor.display_name }}. Comparison information current as of {{ page.last_fact_checked|date:"F Y" }}."

## 6. Hub Template

- [x] 6.1 Create `survey/templates/comparisons/hub.html` extending `base_landing.html`: override `{% block title %}`, `{% block meta_description %}`, `{% block meta_keywords %}` targeting "participatory mapping alternatives", override `{% block canonical_url %}` and `{% block og_url %}` to `/alternatives/`
- [x] 6.2 Render hero section with `trust-hero` styling: eyebrow "Compare", h1 "Alternatives to popular participatory mapping tools", subtitle
- [x] 6.3 Render competitor grid using new `.competitor-hub-grid` CSS class: each card shows `{{ competitor.display_name }}`, short description (template-inlined per competitor for now), and 3 links (one per page_type) — only published pages linked for anonymous, all pages with "Draft" labels for staff
- [x] 6.4 Skipped on hub — disclaimers live on individual comparison pages where specific trademark is named

## 7. Maptionnaire Comparison Templates

- [x] 7.1 Create `survey/templates/comparisons/maptionnaire/alternative.html` extending `base_landing.html`: override SEO blocks (title "Maptionnaire Alternative — Mapsurvey | Free & Open-Source", meta_description, meta_keywords "Maptionnaire alternative, open source Maptionnaire, free Maptionnaire, Maptionnaire vs open source", canonical to `/alternatives/maptionnaire/`, og_type='article'); {% include "_draft_banner.html" %} when `is_draft`; hero; "Why teams switch" section (4 bullets); short comparison table (8-10 rows); pricing snapshot paragraph; CTA row with "Create Your Mapsurvey" + "Try Demo Survey"; {% include "_legal_disclaimer.html" %}
- [x] 7.2 Create `survey/templates/comparisons/maptionnaire/vs.html` extending `base_landing.html`: SEO blocks for "Mapsurvey vs Maptionnaire"; hero; TL;DR paragraph; full comparison table grouped into sections (Survey building, Geo input, Data export, Analytics, Pricing, Hosting, Licensing) with 20-30 rows total; "Choose X if..." balanced section; pricing side-by-side visual; 2 inline placeholders for screenshots (editor + analytics) with `{# TODO: replace with /static/imgs/comparisons/... #}` markers; CTA; disclaimer
- [x] 7.3 Create `survey/templates/comparisons/maptionnaire/migrate.html` extending `base_landing.html`: SEO blocks for "Migrate from Maptionnaire"; hero; Step 1: Export from Maptionnaire; Step 2: Prepare data; Step 3: Create Mapsurvey account; Step 4: Import/recreate survey; feature mapping table (your Maptionnaire X → Mapsurvey Y); "What's different" section; FAQ (3-5 Q/A pairs); CTA with email link "Talk to us about migration"; disclaimer

## 8. CSS

- [x] 8.1 Append `/* === Comparison Pages === */` block to `survey/assets/css/landing.css` with classes: `.draft-banner`, `.comparison-disclaimer`, `.comparison-table`, `.pricing-side-by-side`, `.migration-step`, `.competitor-hub-grid`. Use existing design tokens (`--color-primary`, `--color-accent`, `--color-bg`, `--radius-md`, etc.) — no new tokens
- [x] 8.2 Ensure comparison table is responsive: single-column stacked layout below 768px, two-column grid above
- [x] 8.3 Run `python manage.py collectstatic --noinput` to sync to `staticfiles/`

## 9. Footer Update

- [x] 9.1 Add "Compare" column to footer in `survey/templates/base_landing.html` between "Legal" and "Connect" columns, linking to `{% url 'comparisons_hub' %}` with label "Alternatives"

## 10. Draft Markdown Content

- [x] 10.1 Create `docs/marketing/comparisons/maptionnaire/alternative.md` with full draft copy: hero headline + subheading, "why switch" 4 bullets, 8-10 row comparison table (markdown GFM), pricing paragraph, CTA text. Mark unverified claims with `<!-- FACT-CHECK: description -->` inline
- [x] 10.2 Create `docs/marketing/comparisons/maptionnaire/vs.md` with draft: TL;DR, full 20-30 row comparison table grouped by category, balanced "Choose X if..." section, pricing side-by-side table, all facts with FACT-CHECK markers where uncertain
- [x] 10.3 Create `docs/marketing/comparisons/maptionnaire/migrate.md` with draft: 4-step migration guide, feature mapping table, what's different section, FAQ

## 11. Database Seed Data

- [x] 11.1 Create `Competitor` row (via data migration `0028_seed_maptionnaire_comparison.py`): `slug='maptionnaire'`, `display_name='Maptionnaire'`, `is_active=True`
- [x] 11.2 Create three `ComparisonPage` rows (via same data migration) linked to Maptionnaire: one per `page_type` ('alternative', 'vs', 'migrate'), all `status='draft'`, `last_fact_checked=today`

## 12. Tests

- [x] 12.1 Add `CompetitorComparisonPagesTests(TestCase)` to `survey/tests.py` covering: published page 200 for anon, draft page 404 for anon, draft page 200 for staff with banner visible, nonexistent competitor 404, hub 200 for anon with only published pages visible, hub 200 for staff with draft labels, inactive competitor hidden from hub, sitemap includes published pages but not drafts, sitemap always includes `/alternatives/`, EN rendering regardless of session language
- [x] 12.2 Add template-existence sanity test: for every `ComparisonPage` row, `django.template.loader.get_template(f'comparisons/{competitor_slug}/{page_type}.html')` must resolve — catches slug/template mismatches before deploy
- [x] 12.3 Run `./run_tests.sh survey -v2` — all 19 new tests pass (1 pre-existing landing-section failure unrelated)

## 13. Content Authoring Workflow

- [ ] 13.1 Write draft content in `docs/marketing/comparisons/maptionnaire/*.md` files
- [ ] 13.2 Fact-check every `FACT-CHECK` marker against current maptionnaire.com; update or remove markers
- [ ] 13.3 Port finalized markdown into Django templates (wrap with existing `trust-section` / `landing-inner` classes, convert tables to `.comparison-table` structure, add `{% trans %}` for any user-visible strings if planning i18n in future)
- [ ] 13.4 Update `last_fact_checked` on each `ComparisonPage` row to reflect verification date

## 14. Quality & Launch

- [ ] 14.1 Manual QA: view each draft page logged in as staff, verify banner + content render correctly
- [ ] 14.2 Manual QA: log out, verify each draft returns 404; hub renders without any Maptionnaire link
- [ ] 14.3 Flip one page (`/alternatives/maptionnaire/`) to `status='published'` in admin; verify it goes live and appears in `/sitemap.xml`
- [ ] 14.4 Roll out remaining Maptionnaire pages to `published` once content is reviewed
- [ ] 14.5 Submit updated `sitemap.xml` to Google Search Console; request indexing of new URLs
