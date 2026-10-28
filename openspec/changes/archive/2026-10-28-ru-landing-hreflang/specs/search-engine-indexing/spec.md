## ADDED Requirements

### Requirement: Sitemap and robots.txt advertise the scheme visitors use
`/sitemap.xml` `<loc>` entries and the `Sitemap:` line in `/robots.txt` SHALL use the scheme of the public request: `X-Forwarded-Proto` when the proxy sends it; otherwise `SITE_URL`'s scheme when the request host equals `SITE_URL`'s host; otherwise the request's own scheme.

#### Scenario: Production behind the TLS proxy
- **WHEN** `/sitemap.xml` is requested with `X-Forwarded-Proto: https` on host `mapsurvey.org`
- **THEN** every `<loc>` starts with `https://mapsurvey.org/`

#### Scenario: Canonical host without the proxy header
- **WHEN** `/robots.txt` is requested on the `SITE_URL` host without `X-Forwarded-Proto` and `SITE_URL` is `https://…`
- **THEN** the `Sitemap:` line starts with `https://`

#### Scenario: Local development
- **WHEN** `/sitemap.xml` is requested on `localhost` over plain HTTP without the header
- **THEN** entries start with `http://localhost`

### Requirement: The sitemap lists the Russian homepage with its alternates
`/sitemap.xml` SHALL list `/ru/`, SHALL declare the `xhtml` namespace, and both the `/` and `/ru/` entries SHALL carry `xhtml:link` alternates for `en`, `ru` and `x-default` matching the page's `hreflang` links. `/robots.txt` SHALL allow `/ru/`.

#### Scenario: Russian homepage in the sitemap
- **WHEN** `/sitemap.xml` is fetched
- **THEN** it contains a `<loc>` for `/ru/`, and the `/` and `/ru/` entries each contain `xhtml:link rel="alternate"` entries for `en`, `ru` and `x-default`

#### Scenario: Robots allows the Russian homepage
- **WHEN** `/robots.txt` is fetched
- **THEN** it contains `Allow: /ru/`
