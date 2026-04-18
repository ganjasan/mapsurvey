## Why

Users actively search for "Maptionnaire alternative" and related comparison queries to find Mapsurvey — this is how existing lead Jaakko Huttunen (Futuria Consulting) found the product. Currently the only SEO asset targeting these searches is a single keyword in the landing page meta description. Dedicated competitor comparison pages are a standard SaaS SEO tactic (Notion, Linear, Airtable all run them) and capture bottom-funnel search intent that broad category content cannot. Maptionnaire is expensive and closed-source while Mapsurvey is free and AGPL — the positioning asymmetry is strong enough to convert.

## What Changes

- Add four public URLs forming the competitor comparison surface:
  - `/alternatives/` — hub page listing all published competitor comparisons
  - `/alternatives/<competitor>/` — "looking for X alternative" broad-intent page
  - `/vs/<competitor>/` — detailed head-to-head feature comparison
  - `/migrate-from-<competitor>/` — migration guide for high-intent users (architecture keeps this URL pattern; Maptionnaire v1 does not ship this page — see note below)
- Introduce two new models: `Competitor` (slug, display name, is_active) and `ComparisonPage` (FK competitor, page_type, status, last_fact_checked)
- Ship Maptionnaire as the first competitor on v1 with two pages: `alternative` and `vs`. The `migrate` page type remains in the schema for future competitors; Maptionnaire's migration guide is deferred until we can source reliable facts about Maptionnaire's export formats.
- Draft content authored in markdown files under `docs/marketing/comparisons/<competitor>/*.md`; production content lives in Django templates converted by hand once reviewed
- Status field gates publication: `draft` → 404 for anonymous users, visible to staff with preview banner; `published` → live and included in `sitemap.xml`
- Add trademark/non-affiliation legal disclaimer to every comparison page showing `last_fact_checked` date
- Add "Compare" column to landing footer with links to hub page
- Extend `sitemap_xml` view to enumerate published comparison pages
- Reuse existing `base_landing.html`, `landing.css` design tokens, and `trust-section` / `trust-checklist` component classes — no new CSS framework surface

## Capabilities

### New Capabilities
- `competitor-comparison-pages`: Public SEO-oriented pages comparing Mapsurvey to named competitor products, with per-page draft/publish status, staff preview, and trademark disclaimer

### Modified Capabilities
- `landing-page`: Add "Compare" column to landing footer linking to `/alternatives/` hub

## Impact

**Affected code:**
- `survey/models.py` — add `Competitor`, `ComparisonPage` models
- `survey/views.py` — add `comparisons_hub`, `comparison_page` generic view; extend `sitemap_xml`
- `survey/urls.py` — add 4 URL patterns
- `survey/admin.py` — register both models for status editing
- `survey/assets/css/landing.css` — add `.comparison-table`, `.draft-banner`, `.pricing-side-by-side`, `.migration-step`, `.competitor-hub-grid` component classes
- `survey/templates/base_landing.html` — add "Compare" footer column
- `survey/tests.py` — add tests for status gate, hub filtering, sitemap inclusion

**New files:**
- `survey/templates/comparisons/hub.html`
- `survey/templates/comparisons/_draft_banner.html`
- `survey/templates/comparisons/_legal_disclaimer.html`
- `survey/templates/comparisons/maptionnaire/alternative.html`
- `survey/templates/comparisons/maptionnaire/vs.html`
- `survey/templates/comparisons/maptionnaire/migrate.html`
- `docs/marketing/comparisons/maptionnaire/alternative.md` (authoring draft, not served)
- `docs/marketing/comparisons/maptionnaire/vs.md`
- `docs/marketing/comparisons/maptionnaire/migrate.md`
- One new migration under `survey/migrations/`

**Dependencies:** none — no new Python packages required.

**Legal:** Comparison pages include trademark acknowledgement ("Maptionnaire is a registered trademark of Mapita Oy. Mapsurvey is not affiliated with Mapita Oy.") and an explicit fact-check date to limit exposure from outdated claims.

**SEO:** Four new URLs added to `sitemap.xml` once published. Each page sets its own `canonical_url`, `og:url`, `og:title`, `meta_description`, `meta_keywords` via existing `base_landing.html` blocks. `og:type` is set to `article` on comparison pages (differing from `website` on the home page).
