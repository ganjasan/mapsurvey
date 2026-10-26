## Context

Three surfaces must show the same plans: `/pricing/` and the category landings (built on
`base_landing.html` + `landing.css`) and Plan & billing (built on `base.html` + Bootstrap 4).
The landings already have `.pricing-card` styles; the billing page has none.

## Decisions

- **One partial, own stylesheet.** `partials/_plan_cards.html` carries its markup and links
  `css/plan_cards.css` itself (a `<link rel="stylesheet">` in the body is valid HTML), with
  class names under `plan-` and colour tokens of its own, so it looks the same under `landing.css`
  and under Bootstrap. Alternative — reuse `.pricing-card` from `landing.css` and copy it for the
  billing page — gives two looks that drift.
- **The price figure lives in the partial.** The rule from `seo-landings-rewrite` ("to take the
  price off the site, edit one file") is kept and moved: the test that reads the templates now
  looks for `$49` only in `_plan_cards.html`. The help site (`help/`) is a separate build and keeps
  its own copy, as today.
- **Monthly/yearly switch without JavaScript.** Two radios `name="period"` precede the grid;
  `:checked ~` rules show the matching figure. On Plan & billing the radios carry
  `form="pro-checkout"`, so the one **Upgrade to Pro** button posts the period the creator sees.
  "Get a quote" is its own small form (always yearly, `quote=1`), as now. The checkout view is
  unchanged. Ids are prefixed per include (`prefix`), so two blocks on one page never share a radio.
- **Done for you has no figure.** Service work is billed by the hour after a scoping call; the
  card names what we do and leads to `/demo/?src=pricing` (or `src=billing`), with a link to
  `/services/`. No hourly rate on the site.
- **Pro CTA on the public page:** anonymous → sign up (`?utm_source=pricing`); signed-in owner or
  admin of the active organisation → its Plan & billing page; any other signed-in member → the
  editor dashboard.

## Risks

- The four landings change visibly (third card, no "early access" tag). Their `lastmod` is not
  bumped: the change is the shared block, not the page's own text.
