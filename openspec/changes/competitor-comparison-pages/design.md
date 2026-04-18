## Context

The project already serves two kinds of public informational pages (landing at `/` and trust at `/trust/`), both using the simple pattern: function-based view with `@lang_override('en')`, template extending `base_landing.html`, hardcoded content, no database model. `Story` is the only admin-editable public content and uses the pattern: single model + slug URL + admin body field.

Competitor comparison pages need more structure than trust-page because:
- Each competitor has three distinct URLs (alternative/vs/migrate), each with its own publication status
- Content is authored as markdown drafts for easy review before going live
- Pages must 404 for anonymous users while in draft, but remain previewable by staff
- Legal disclaimer text must be identical across all pages (single source of truth)
- The feature must support adding second/third competitors without rewriting the URL table

The landing page's SEO infrastructure (meta tags, canonical, Open Graph, Schema.org JSON-LD) is already generalized via template blocks in `base_landing.html` — comparison pages inherit this for free.

## Goals / Non-Goals

**Goals:**
- Ship three Maptionnaire pages + one hub page with SEO-friendly URLs and full meta-tag inheritance
- Draft/published status per page controllable from Django admin without code deploy
- Staff can preview drafts; anonymous visitors cannot
- Adding a second competitor (MetroQuest) requires zero Python changes — only data + templates
- Single source of truth for trademark disclaimer text across all comparison pages
- Published pages automatically appear in `sitemap.xml`

**Non-Goals:**
- i18n / localized comparison pages (deferred with other marketing i18n work; EN-only via `@lang_override('en')`)
- WYSIWYG admin editing of comparison content (pages are Django templates, not CMS rows)
- Runtime markdown parsing (`.md` drafts are authoring-only, never served)
- Auto-generated comparison tables from structured data (content is deliberately hand-written for voice and SEO)
- Schema.org `AggregateRating` (no real ratings exist; fake ratings violate guidelines)
- User-facing "request a comparison" feature / form

## Decisions

### 1. Two-model design: `Competitor` + `ComparisonPage`

`Competitor(slug, display_name, is_active)` holds the competitor identity. `ComparisonPage(competitor_fk, page_type, status, last_fact_checked)` holds one row per URL.

**Alternative considered:** One flat model `ComparisonPage(competitor_slug, page_type, status, last_fact_checked)` without a `Competitor` model. Rejected — the hub page needs to list "all published competitors" as an aggregate; with a flat model this requires `DISTINCT` queries and loses the natural `is_active` hub gate. A dedicated `Competitor` row is also the right place to park `display_name` (used in hub cards), avoiding hardcoded strings in templates.

**Alternative considered:** Store full markdown body in the model (`ComparisonPage.body_md` TextField), render with a markdown parser at request time. Rejected — loses `{% trans %}`, `{% static %}`, `{% url %}` template tag access; introduces a markdown parser dependency; conflates "content" and "publication state" in one field. Per user decision (Q3=B), drafts live as `.md` files for writing, production is Django templates.

### 2. One generic view + separate hub view

`comparison_page(request, page_type, competitor_slug)` handles all three per-competitor URLs. Template path is conventional: `comparisons/<competitor_slug>/<page_type>.html`. Page lookup by `(competitor__slug, page_type)`. Draft gate in the view (two-line check, not a decorator).

`comparisons_hub(request)` is a separate flat view — it queries all active competitors and their published page states, which is structurally different from rendering one specific page. Forcing both into a single view would require a `page_type='hub'` special case.

**Alternative considered:** Four separate FBVs (one per URL type). Rejected — they'd share 90% of their bodies. A private helper (Agent 1's suggestion) is functionally equivalent to the generic view but requires three wrapper FBVs in `views.py` plus three matching URL entries for no gain.

### 3. Parametric URL patterns with `slug` converter

```python
path('alternatives/<slug:competitor_slug>/', views.comparison_page,
     kwargs={'page_type': 'alternative'}, name='comparison_alternative')
```

Adding MetroQuest later = zero URL changes. The pattern `migrate-from-<slug:competitor_slug>/` uses a literal prefix in the path; Django's slug converter accepts `[a-zA-Z0-9_-]+` which is sufficient.

**Alternative considered:** Hardcode Maptionnaire into URL strings and add new `path()` lines per competitor. Rejected — moves the cost of adding a competitor from data to code and grows `urls.py` linearly.

### 4. Status gate inline in the view

```python
if page.status == 'draft' and not request.user.is_staff:
    raise Http404
```

**Alternative considered:** Custom decorator `@draft_protected`. Rejected — the check is two lines, used in exactly two places (generic view + hub view), and a decorator would need to know how to extract the `ComparisonPage` instance, adding indirection.

### 5. Shared partials for disclaimer and draft banner

- `comparisons/_legal_disclaimer.html` — trademark disclaimer + non-affiliation + `{{ page.last_fact_checked|date }}`
- `comparisons/_draft_banner.html` — staff-only "Draft preview" warning bar

Every page template `{% include %}`s both. Single source of truth for legal text — if wording changes, one file edit, not N.

**Alternative considered:** Inline the disclaimer in each template directly. Rejected — creates N-fold risk of drift when legal wording changes, and we already agreed (conversation context) that the disclaimer text is legally load-bearing.

### 6. Hub page handles draft/published visibility in its query

The hub loads `Competitor.objects.filter(is_active=True).prefetch_related('comparison_pages')`. For each competitor, it groups its pages by status and renders only published pages to anonymous visitors; staff see draft pages with a label. Competitors with zero published pages are hidden from anonymous viewers.

### 7. Draft `.md` files live in `docs/marketing/comparisons/<competitor>/*.md`

Django never reads these. They are writing-stage artifacts — analogous to a Notion draft or a Google Doc. When content is approved, the author converts markdown prose into the Django template (wrapping with existing `trust-section` / `landing-inner` classes, adding CTAs, Schema.org tweaks, etc.). This is the same "manual conversion" step that happens on every OpenSpec change's `specs/ → openspec/specs/` promotion.

### 8. CSS lives in `landing.css`

New classes appended in a `/* === Comparison Pages === */` section: `.comparison-table`, `.pricing-side-by-side`, `.migration-step`, `.draft-banner`, `.competitor-hub-grid`, `.comparison-disclaimer`. The landing CSS is already a single-file design system and these are marketing-surface components — splitting into a separate file would add an HTTP round-trip with no modularity gain (the file is already small and cache-friendly).

### 9. Sitemap integration queries published pages

`sitemap_xml` view extends its hardcoded URL list with a `ComparisonPage.objects.filter(status='published').select_related('competitor')` loop, mapping each row to its URL via a small `{page_type: url_template}` dict. The hub URL `/alternatives/` is always included (it has no draft state).

### 10. Legal disclaimer shows fact-check date

`ComparisonPage.last_fact_checked` is a `DateField` (not `DateTimeField`) updated manually when content is reviewed. Shown as `"Comparison information current as of {{ page.last_fact_checked|date:"F Y" }}"` — e.g. "April 2026". This creates a clear paper trail against stale-information claims.

## Risks / Trade-offs

**[Duplicate content across 3 Maptionnaire URLs]** Google may penalize near-identical pages. → Mitigation: content plan (confirmed in Q5) requires each page to have 60%+ unique content. `/alternatives/` has short table; `/vs/` has full table; `/migrate/` has steps unique to migration. Each has its own `canonical_url`.

**[Incorrect competitor facts trigger cease-and-desist]** If we misquote Maptionnaire pricing or features, Mapita Oy could demand takedowns. → Mitigation: fact-check markers in `.md` drafts during authoring; disclaimer with `last_fact_checked` date; `{# FACT-CHECK #}` comments stripped only after manual verification; tier names (Point/Collect/Communicate) are publicly stated on maptionnaire.com, prices deliberately not quoted.

**[Accidental publication of draft]** Editor flips status to `published` before content is ready. → Mitigation: staff draft banner makes in-progress state visible on the rendered page; admin list display shows status prominently; review checklist item in tasks.md before flipping.

**[Template-routing bugs when competitor slug doesn't match template path]** A `Competitor` row without a matching template directory causes `TemplateDoesNotExist` at request time. → Mitigation: sanity test in `tests.py` iterates all published `ComparisonPage` rows and asserts the corresponding template file exists. Runs in CI before deploy.

**[SEO cannibalisation between `/alternatives/` hub and `/alternatives/maptionnaire/`]** Two URLs sharing the "alternatives" keyword. → Mitigation: hub targets broader "participatory mapping alternatives" query; per-competitor page targets "maptionnaire alternative". Different `meta_description` + H1. Hub has 1-2 sentence summaries only; per-competitor has full content.

**[Maptionnaire runs their own comparison page targeting Mapsurvey]** → Not a mitigation but acknowledged — if they respond with their own `/alternatives/mapsurvey/`, we get a free backlink from a higher-authority domain.

## Migration Plan

1. Create models + migration; run `migrate` in dev
2. Build templates + CSS + views; write tests
3. Create Maptionnaire `Competitor` + 3 `ComparisonPage` rows (all `status='draft'`)
4. Draft markdown content in `docs/marketing/comparisons/maptionnaire/*.md`; iterate with reviewer
5. Convert approved markdown to Django templates (`survey/templates/comparisons/maptionnaire/*.html`)
6. Fact-check pass: verify every claim against current maptionnaire.com; update `last_fact_checked`
7. Flip `status='published'` per page in admin as each is ready (pages can go live staggered)
8. Deploy; verify sitemap includes new URLs; submit to Google Search Console
9. Monitor organic traffic; iterate copy based on Google Search Console query data

Rollback: set `status='draft'` in admin — pages immediately return 404 for anonymous visitors. No deploy needed.

## Open Questions

None — all architectural decisions resolved in Q1–Q6 pre-design discussion with user. Content-level decisions (specific table rows, migration step details) will surface during draft authoring and are not architecturally blocking.
