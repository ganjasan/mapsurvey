# A first-party host for browser analytics, and an honest Cloudflare disclosure

## Why

PostHog now runs on our creator-facing pages, and the browser half of it loads from
`eu.i.posthog.com` — a hostname that every mainstream blocklist carries. uBlock Origin, Brave's
shields, AdGuard and Safari's Tracking Prevention all drop it. The people we point PostHog at are
planners, GIS analysts and researchers: the single audience most likely to be running a blocker.
The events we lose are not a random sample, they are systematically the more technical half of our
creators, and the funnel we built PostHog to see is exactly where their absence distorts the
picture.

PostHog's managed reverse proxy fixes this at DNS level and costs nothing: a CNAME from a
first-party subdomain to a PostHog-operated endpoint, after which the browser talks to
`mapsurvey.org`'s own namespace and blocklists have nothing to match.

Two things make this cheap for us specifically, and both were verified rather than assumed:

- **Cloudflare is already in our request path.** `mapsurvey.org` resolves through
  `mapsurvey.onrender.com` → `gcp-us-west1-1.origin.onrender.com.cdn.cloudflare.net`; Render fronts
  every service with Cloudflare. We already run Turnstile and already trust `CF-Connecting-IP` in
  `CloudflareIPMiddleware`. The proxy's consent screen introduces no processor that is not already
  handling 100% of our traffic.
- **Our DNS is not on Cloudflare.** `mapsurvey.org` is served by Namecheap
  (`dns1.registrar-servers.com`), so the one documented failure mode of the managed proxy — a CNAME
  behind Cloudflare's orange cloud breaking SSL provisioning — cannot occur here.

The thing that is *not* free is the claim on `/trust/`. That page currently names Cloudflare only as
the Turnstile vendor, while Cloudflare in fact proxies the entire site. That gap exists today and is
independent of this change, but adding a second, analytics-specific Cloudflare path while the page
stays silent is precisely the failure we corrected on 2026-08-15, when six claims on `/trust/` and
in the DPA turned out not to describe the product. We are not repeating it.

## What Changes

- **A first-party analytics host for the browser only.** A new `POSTHOG_CLIENT_HOST` setting carries
  the proxy hostname; the browser snippet initialises against it. The subdomain is deliberately
  neutral (`e.mapsurvey.org` rather than anything containing `ph`, `analytics` or `track`, which
  blocklists match on by name).
- **Server-side capture keeps talking to PostHog directly.** `POSTHOG_API_HOST` stays
  `https://eu.i.posthog.com` and stays the value `survey.apps.SurveyConfig` hands the Python SDK.
  Ad blockers do not exist server-side, so routing Django view exceptions and Celery task failures
  through a proxy would buy nothing and add a dependency to the subsystem whose whole job is to keep
  working when other things break.
- **`ui_host` is pinned to `https://eu.posthog.com`.** Once `api_host` is a domain of ours, the SDK
  can no longer derive where the PostHog UI lives; without this, toolbar links and
  "view in PostHog" URLs point at our proxy.
- **Static assets follow the proxy.** The snippet derives its asset host by string-replacing
  `.i.posthog.com` with `-assets.i.posthog.com`; against a custom domain that replacement is a
  no-op, so `array.js` loads from the proxy host, which the managed proxy serves. This is correct
  behaviour, not an accident, and gets an explicit verification step rather than a comment.
- **Unset proxy = today's behaviour.** An empty `POSTHOG_CLIENT_HOST` falls back to
  `POSTHOG_API_HOST` (resolved per request, not at import time — see design.md), so
  local development, the test suite and PR previews are unchanged and no deployment can end up
  pointing the browser at a proxy that has not been provisioned.
- **`/trust/` names Cloudflare for what it does.** The page states that Cloudflare fronts the
  hosted service as CDN and reverse proxy — including analytics traffic — rather than mentioning it
  only as an anti-abuse widget. It also states plainly that PostHog stores data in the EU while
  transit passes over Cloudflare's anycast network, which PostHog documents as terminating at EU
  edges in the usual case but does not contractually guarantee.

Out of scope, deliberately: Plausible is blocked by the same lists and is not moved here. It is
slated for retirement in `posthog-replaces-plausible`, and proxying a tool we intend to remove is
work with a known expiry date.

## Capabilities

### New Capabilities

- `analytics-transport`: how browser and server reach PostHog — which host each uses, what happens
  when the proxy is unconfigured, where the UI and static assets resolve, and what the trust page
  must disclose about the transit path.

### Modified Capabilities

None. `product-analytics` (from `posthog-internal-analytics`) says the snippet initialises against
`POSTHOG_API_HOST` and that the host is overridable; both stay true, because with no proxy
configured `POSTHOG_CLIENT_HOST` *is* `POSTHOG_API_HOST`. The split is additive.

## Impact

**Code**

- `mapsurvey/settings.py` — new `POSTHOG_CLIENT_HOST`, empty by default
- `survey/context_processors.py` — the template context carries the client host, not the API host
- `survey/templates/partials/_analytics.html` — `api_host` from the client host, new `ui_host`
- `render.yaml` — `POSTHOG_CLIENT_HOST` (`sync: false`) on both the web service and the worker
- `.env.example` — document the split and why the two hosts differ
- `survey/templates/trust.html` — Cloudflare disclosure
- `survey/tests.py` — the split, the fallback, and the trust-page claim

Unchanged on purpose: `survey/apps.py` and `mapsurvey/celery.py`. They read `POSTHOG_API_HOST` and
must keep reading it.

**Infrastructure (outside the repo, one-time)**

- PostHog: accept the managed-proxy terms, provision the proxy, obtain the target hostname
- Namecheap: CNAME `e` → the PostHog-issued target (`*.cf-prod-eu-proxy.europehog.com`)
- Render: set `POSTHOG_CLIENT_HOST` on the web service and the worker

**Not affected**

- Respondent surfaces. `POSTHOG_EXCLUDED_PREFIXES` (`/surveys/`, `/r/`) is untouched, so the proxy
  never appears on a page belonging to a customer's audience — which is also why the managed
  proxy's HIPAA disclaimer is inapplicable to us: PostHog does not load where survey answers are
  written.
- `SurveyEvent` / `TrackedLink` / `PerformanceAnalyticsService` — a different system measuring
  different people, as ever.
- No CSP exists in the project, so no policy needs widening for the new origin.
