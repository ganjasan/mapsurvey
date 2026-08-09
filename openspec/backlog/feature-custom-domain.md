# Custom domain for surveys and results pages

**Type**: feature
**Priority**: high
**Area**: infra
**Epic**: pro-tier
**Created**: 2026-07-29

## Description

Let a Pro workspace serve its surveys and public results pages on its own domain —
`beteiligung.stadt-jena.de` or `mitmachen.think-jena.de` instead of
`mapsurvey.org/surveys/<uuid>/`.

For a consultancy running participation on behalf of a municipality, the survey URL is
what citizens see on posters, in the local press, and in the council resolution. A
third-party domain reads as "some tool they found"; the client's own domain reads as an
official process. This is the same purchase motive as white-label, expressed in the one
place a respondent cannot miss.

## Scope Sketch

- Domain registration in the workspace + verification (DNS TXT or CNAME challenge).
- Automatic TLS issuance and renewal (ACME); confirm what Render supports for
  wildcard/dynamic custom domains before committing to an approach — this is the main
  unknown and may dictate a proxy layer.
- Request routing: map hostname → workspace, then resolve the survey slug within it.
  Public survey URLs, thanks page, password gate, and results pages must all work.
- Per-survey or per-workspace default domain choice.
- Absolute-URL generation (emails, QR codes, sitemap, OG tags) must follow the custom
  domain, not `SITE_URL`.
- Fallback: the canonical `mapsurvey.org` URL keeps working; never strand a link that is
  already on a printed poster.

## Notes

- Pairs with [white-label branding](feature-white-label-branding.md) (#90) — a custom
  domain with our badge still on the page defeats the purpose; sell them together.
- Interacts with [the viral loop badge](feature-made-with-mapsurvey-viral-loop.md) (#75):
  custom domain implies the badge comes off, which is a real (accepted) acquisition cost.
- SEO consequence: results pages on client domains stop feeding
  [the showcase/SEO play](idea-public-results-showcase-seo.md) (#77). Consider keeping a
  canonical copy indexed on mapsurvey.org, or accept the trade explicitly.
- Non-trivial infra work — do not promise a date on a sales call before the TLS approach
  is settled.
