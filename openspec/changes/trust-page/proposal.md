## Why

Government and enterprise users require a clear, professional trust/security page before their IT security teams will approve Mapsurvey for institutional use. This is the #1 blocker for adoption — Manuel Frost (Berlin Senate) explicitly stated his IT security team must approve the tool before official use. No such page currently exists.

## What Changes

- Add a public `/trust/` page covering: GDPR/data privacy, hosting & data residency, open-source transparency, security measures, data ownership, and project background
- Generate a Data Processing Agreement (DPA) template as a downloadable static PDF
- Add "Trust" link to the landing page navigation bar and footer
- Page uses `base_landing.html` (same design as landing page), forced English via `@lang_override('en')`
- Corporate/formal tone appropriate for IT security review audience

## Capabilities

### New Capabilities
- `trust-page`: Public informational page at `/trust/` addressing IT security and GDPR concerns, with sections on data privacy, hosting, open-source transparency, security, data ownership, and project background
- `dpa-template`: Downloadable Data Processing Agreement (DPA) template as a static PDF for institutional users

### Modified Capabilities
- `landing-navigation`: Add "Trust" link to both the navigation bar and footer in `base_landing.html`
