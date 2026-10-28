## Context

We already ship audience landing pages (`/for-planners/`, `/for-government/`, `/for-researchers/`,
`/for-educators/`) and a comparison page (`/alternatives/maptionnaire/`). Each is a thin
view — `capture_signup_source(request)` then `render(request, '<page>.html')` — whose template
extends `base_landing.html` and overrides SEO blocks (`title`, `meta_description`, `meta_keywords`,
`canonical_url`, `og_url`, `og_title`). `sitemap_xml` and `robots_txt` are hand-maintained lists in
`survey/views.py`. This change adds two more pages on that exact pattern; no new infrastructure.

## Goals / Non-Goals

**Goals**
- Rank for two bottom-funnel head terms with dedicated, self-canonical pages.
- Reuse the landing pattern verbatim — zero new abstractions, models, or dependencies.
- Avoid keyword cannibalization with the existing `/for-government/` page.

**Non-Goals**
- No blog / CMS infrastructure (that is the separate top-of-funnel effort).
- No RU translations yet (pages ship English-first, wrapped in `{% trans %}` like the others).
- No changes to the root `/` landing page or its `landing-page` capability.

## Decisions

### Decision: New capability `seo-landing-pages`, not a modification of `landing-page`
The existing `landing-page` capability specifies the root `/` page with its fixed structure (hero,
how-it-works, survey cards, stories, contact). The audience "for …" pages were shipped without being
folded into that spec. Rather than overload `landing-page`, these product pages get their own
capability describing the reusable SEO-landing contract (own URL, extends `base_landing.html`,
self-canonical, UTM CTA, sitemap/robots discoverability). Cleaner separation; future audience/product
pages can extend the same capability.

### Decision: Product/category framing to avoid cannibalizing `/for-government/`
`/for-government/` already targets "community engagement platform **for local government**" — an
*audience* page. The two new pages take the *product/category* angle:
- `/community-engagement-platform/` — the broad head term. H1 "Community Engagement Platform" with no
  single-audience scope; body frames the product across segments (councils, NGOs, consultancies,
  universities, transport agencies) and cross-links to `/for-government/` and `/for-planners/` as
  those segments' dedicated pages.
- `/public-consultation-software/` — the consultation-*workflow* angle: statutory consultation,
  planning applications, infrastructure/transport schemes; audience wider than government (developers,
  consultancies). H1 "Public Consultation Software".

Each page is self-canonical and owns a distinct primary term, so they reinforce rather than compete.
Internal links flow product page → audience page and product page ↔ product page.

### Decision: UTM scheme consistent with existing pages
Primary CTAs point to `django_registration_register` with
`?utm_source=engagement_platform&utm_medium=community_engagement_platform` and
`?utm_source=consultation_software&utm_medium=public_consultation_software`, mirroring the
`utm_source=government&utm_medium=for_government` convention.

### Decision: Internal linking via shared footer
Both pages are added to the `base_landing.html` footer "Product" list, so every landing page links to
them (site-wide internal links for crawl + link equity). They are intentionally *not* added to the
nav "Solutions" dropdown, which is reserved for audience "for …" pages.

## Risks / Trade-offs

- **Cannibalization risk with `/for-government/`.** Mitigated by the product-vs-audience split above and
  distinct self-canonicals. If Google still conflates them, the fallback is to canonicalize the
  audience page's secondary term to the product page — not needed at launch.
- **Thin-content risk.** Each page must carry genuinely distinct copy (segments, use cases, comparison
  framing), not a reskin of `/for-government/`. Templates are written with page-specific sections.

## Migration Plan

Pure addition — no migration. Ship views + templates + URL + sitemap/robots + footer links + tests in
one change. `python manage.py collectstatic` not required (no new static assets; reuses `landing.css`).

## Open Questions

- Do we want `hreflang`/RU variants later? Deferred — the whole landing suite is English-only until RU
  translations are complete (per the disabled language switcher in `base_landing.html`).
