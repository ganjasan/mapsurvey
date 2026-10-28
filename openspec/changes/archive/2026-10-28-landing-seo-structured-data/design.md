## Context

The SEO landing pages (`survey/templates/*.html` extending `base_landing.html`) already override `title`/`meta_description`/`meta_keywords`/`canonical_url`/`og_url` blocks per page. `base_landing.html` carries two site-wide JSON-LD blobs (`SoftwareApplication`, `Organization`). The sitemap and robots are plain function views (`survey/views.py::sitemap_xml`, `::robots_txt`) that hardcode the landing URL list; the same list also appears as route registrations in `survey/urls.py`. There is no page-level structured data, no FAQ content, and no shared landing registry.

Constraints:
- Django template inheritance + `{% trans %}` i18n is the existing idiom; no JS framework on landings.
- JSON-LD must be valid JSON — user-facing FAQ answers contain quotes/apostrophes, so escaping matters.
- Keep it DRY: the on-page FAQ and the `FAQPage` JSON-LD must come from one per-page source so they can't drift.

## Goals / Non-Goals

**Goals:**
- Reusable FAQ section + `FAQPage` JSON-LD driven by a single per-page Q&A list.
- `BreadcrumbList` JSON-LD on landings, correct for the two-level `alternatives/*` pages.
- One source of truth for the SEO landing list, consumed by `sitemap_xml` and `robots_txt`, with `lastmod`/`changefreq`/`priority`.
- Tests asserting presence + validity of structured data and full sitemap/robots coverage.

**Non-Goals:**
- No change to the root `/` landing page requirements (`landing-page` spec untouched).
- No auto-generation of `urls.py` routes from the registry (routes stay explicit; only robots/sitemap derive from the registry).
- No new content pages, no blog, no `/stories/` index (separate changes).
- No new runtime dependencies.

## Decisions

**D1 — The registry is the per-page data hub; a shared render helper injects it.**
The 13 landings are rendered by thin view functions (`render(request, 'x.html')`). Rather than hand-editing 13 views with bespoke Q&A/breadcrumb lists, the SEO landing **registry** (D2) holds each page's `faq` list and `breadcrumbs`, and a single helper `render_seo_landing(request, page_key)` looks the entry up and injects `faq_items` + `breadcrumbs` (as already-built JSON-LD strings) into the template context. Each view becomes `return render_seo_landing(request, 'civic_engagement')`. This makes the registry the one place that knows a page's path, crawl hints, breadcrumb, and FAQ — so a page can't have a route but miss its sitemap/FAQ, or vice-versa.
- Two shared partials read that context: `partials/_faq_section.html` renders the visible `<section>` by looping `faq_items`; `partials/_landing_structured_data.html` emits the `FAQPage` + `BreadcrumbList` `<script type="application/ld+json">`. Both derive from the same registry entry, so they can't drift.
- *Alternative considered*: define Q&A inside each template with `{% with %}`/inclusion tags — rejected because building valid JSON from template loops requires fragile manual escaping, and it re-scatters the source of truth the registry is meant to unify.
- *Escaping*: JSON-LD is built with `json.dumps(...)` in Python and passed to the template as a pre-escaped safe string, guaranteeing valid JSON regardless of quotes/apostrophes in answers.

**D2 — `survey/seo_landings.py` holds the registry + builders.** One module with: `SEO_LANDINGS` — an ordered registry (dataclass/dict per page: `key`, `path`, `url_name`, `changefreq`, `priority`, `lastmod`, `breadcrumbs`, `faq`), plus `build_faqpage_jsonld(faq)` and `build_breadcrumb_jsonld(request, crumbs)` returning `json.dumps` strings, and `render_seo_landing(request, key)`. Views and the sitemap/robots views import from here; tests get a direct unit surface.

**D3 — `structured_data` block in `base_landing.html`.** Add `{% block structured_data %}{% endblock %}` right after the site-wide JSON-LD. Landing templates fill it by `{% include "partials/_landing_structured_data.html" %}`. Root/other pages that extend the base and don't set it are unaffected.

**D4 — Registry drives robots + sitemap, not urls.py.** `SEO_LANDINGS` in `survey/seo_landings.py` is the single list of `(path, changefreq, priority)`. `robots_txt` builds its `Allow:` lines from it; `sitemap_xml` builds `<url>` entries with `<lastmod>` (deploy date or a static release date — see D5), `<changefreq>`, `<priority>`. `urls.py` keeps explicit `path()` calls (they need view callables), but a test asserts every registry path resolves and vice-versa, catching drift.

**D5 — `lastmod` value.** Use a per-entry static `lastmod` date string in the registry (updated when a page's content materially changes), not `now()` — a sitemap that reports "modified today" on every crawl trains crawlers to distrust `lastmod`. Default to the change's ship date for all current entries.

## Risks / Trade-offs

- **[Invalid JSON-LD from unescaped quotes]** → generate JSON via `json.dumps`, never string concatenation; test parses the emitted `<script>` with `json.loads`.
- **[FAQ/JSON-LD drift]** → both derive from the same `faq_items`; a test asserts each visible `<summary>`/question also appears in the `FAQPage` JSON.
- **[Registry vs urls.py drift]** → test resolves every registry path and asserts every landing route is in the registry.
- **[Google flags FAQ rich results as spammy if content is thin/duplicated]** → per-page Q&A must be genuinely page-specific (not the same 5 questions copy-pasted); enforced by review, and a test asserts distinct questions across pages.
- **[`lastmod` staleness]** → accepted; static dates are safer than always-now. Document that editors bump the date on material change.

## Migration Plan

Pure additive, no DB. Deploy = template + view refactor. Rollback = revert commit; no data migration. After deploy, validate a sample of pages with Google Rich Results Test and resubmit the sitemap in Search Console (manual, tracked in the outreach checklist).

## Open Questions

- None blocking. FAQ copy per page will be drafted during implementation from each page's existing value props; competitor pages (`alternatives/*`) get comparison-specific Q&A.
