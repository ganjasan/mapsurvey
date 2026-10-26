## Context

`base_landing.html` has carried two JSON-LD blocks since July 2026: a `SoftwareApplication` that
describes a self-hosted developer tool ("DeveloperApplication", "Linux, Docker") and an
`Organization` with `sameAs` [GitHub, Participedia], both written as text in the template and not
linked to each other. There is no `WebSite` node. A DataForSEO sample on 2026-10-26 showed Google
returning the brand result page for `mapsurvey` in only ~38% of searches; the rest read the query
as "survey map" (#443). Structured data is one of the inputs Google uses to decide that a string is
a named entity and which site it belongs to; the others (Wikidata, consistent listings, mentions)
are off-repo work for the owner.

## Goals / Non-Goals

**Goals:**
- One connected graph: WebSite (homepage pair) → publisher Organization ← publisher/author
  SoftwareApplication, with stable `@id`s on `https://mapsurvey.org/#…`.
- Describe the product as what it is: a hosted web application that is also self-hostable.
- Make adding a profile a one-line, tested change.

**Non-Goals:**
- Writing to Wikidata, G2, LinkedIn or any directory (owner, by hand; drafts in the ops repo).
- Per-page structured data (FAQPage, BreadcrumbList) — unchanged.
- `SearchAction` / sitelinks search box (Google retired the box in 2024).
- Measuring the effect — that is the monthly DataForSEO re-run named in the issue.

## Decisions

- **Build the JSON in Python, render with a template tag.** `survey/brand.py` holds the registry and
  returns plain dicts; `survey/templatetags/brand_tags.py` serialises them with `json.dumps` and
  escapes `<`, `>` and `&` as `\u003c`, `\u003e`, `\u0026` so nothing in a value can close the `<script>`.
  Alternative: keep hand-written JSON in the template — that is how the current blocks got their
  stale category, and a typo there fails silently in production.
- **`@id` fragments on the canonical host**, not on the request host, so previews and the `/ru/`
  twin point at the same entity.
- **`WebSite` only on the homepage pair.** Google reads the site name from the home page; repeating
  it on every landing adds nothing. `landing.html` serves both `/` and `/ru/`, so the tag goes into
  its `structured_data` block once.
- **One `<script>` per node, linked by `@id`, `@type` a single string.** A `@graph` or a type list
  would be equally valid JSON-LD, but the existing landing tests (and anything else reading
  `@type` per block) expect one typed document per script; `@id` carries the links either way.
- **`SoftwareApplication` with `applicationCategory: BusinessApplication`** and `offers` describing the free plan and
  `isAccessibleForFree: true`; the AGPL licence and `codeRepository` stay, because they are true and
  self-hosting is part of the pitch.
- **No price figure in structured data beyond `0`.** The Pro price lives only in
  `partials/_landing_pricing.html` (CLAUDE.md rule); the free offer is `price: "0"` as today.

## Risks / Trade-offs

- [Effect is unproven] → structured data is a hint, not a switch; the issue tracks the share of
  brand SERPs monthly so we can tell whether this and the off-repo work move it.
- [A wrong `sameAs` (someone else's profile) would merge us with another entity] → only profiles we
  own go into the registry; the test refuses non-https, self-links and duplicates.
- [Template tag output differs from what the test sees] → the test parses the rendered page, not
  the dicts.

## Migration Plan

Template-only change; deploy with the next merge. Rollback is a revert. Google re-reads the markup
on its next crawl; the owner can request reindexing of `/` in Search Console.
