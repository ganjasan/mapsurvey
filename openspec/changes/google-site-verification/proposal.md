## Why

Google Search Console is the measurement prerequisite for the SEO track (educators page shipped,
comparison page next): without a verified property we have no impressions/position/query data.
Domain (DNS) verification is preferred, but an env-driven meta-tag makes URL-prefix verification a
zero-DNS, redeploy-only operation — and works for future verifications (e.g. Bing).

## What Changes

- `GOOGLE_SITE_VERIFICATION` setting (env var, default empty) exposed via the analytics context
  processor; when set, `<meta name="google-site-verification" content="…">` renders in the head of
  both base templates (`base_landing.html`, `base.html`). Empty ⇒ no tag, zero output change.

## Capabilities

### New Capabilities
- `site-verification`: Env-configurable Google site-verification meta tag on all pages.

### Modified Capabilities
<!-- none -->

## Impact

settings.py, survey/context_processors.py, base templates; test `GoogleSiteVerificationTest`.
Owner follow-up (not code): create the GSC property, verify (DNS TXT or this tag), submit sitemap.
