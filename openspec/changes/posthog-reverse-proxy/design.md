## Context

PostHog reaches our stack twice, over two independent paths that happen to share one setting today:

- **Browser** — `survey/templates/partials/_analytics.html` renders the JS snippet, initialised
  against the value `survey/context_processors.py` puts in the template context, which is
  `settings.POSTHOG_API_HOST`.
- **Server** — `survey.apps.SurveyConfig._configure_posthog` sets `posthog.host` from the same
  `settings.POSTHOG_API_HOST`, and that module-level client is what `PosthogContextMiddleware`
  (view exceptions) and the `task_failure` receiver in `mapsurvey/celery.py` (Celery failures) use.

Only the first path has a blocker problem. The second one runs inside our own containers, where no
extension has ever removed a request.

The constraint that shapes everything below: `/trust/` is the page IT security teams read, and on
2026-08-15 six of its claims turned out not to describe the product. Every statement this change
makes about where data goes has to be checkable against the code and the DNS, not aspirational.

Verified before writing this (not assumed):

- `dig mapsurvey.org` → `mapsurvey.onrender.com` → `gcp-us-west1-1.origin.onrender.com.cdn.cloudflare.net`
  — Cloudflare already fronts every request to the hosted service.
- `dig NS mapsurvey.org` → `dns1.registrar-servers.com` (Namecheap) — our zone is not on Cloudflare,
  so the managed proxy's documented "disable the orange cloud on this CNAME" requirement is
  inapplicable.
- No CSP header is set anywhere in `mapsurvey/settings.py` or `survey/middleware.py` — a new script
  origin needs no policy change.
- PostHog's own documentation: managed reverse proxy is free on Cloud, EU requests "typically
  terminate at EU edges" but this "isn't contractually guaranteed", and no request content is
  stored at the edge.

## Goals / Non-Goals

**Goals:**

- Browser events reach PostHog from a first-party hostname that blocklists do not match.
- Server-side error capture keeps its direct, dependency-free path to PostHog Cloud EU.
- An unconfigured proxy is indistinguishable from today — tests, local dev and PR previews unchanged.
- `/trust/` describes the Cloudflare path accurately, including the part that predates this change.

**Non-Goals:**

- Proxying Plausible. It is scheduled for removal in `posthog-replaces-plausible`.
- Self-hosting a proxy (Cloudflare Worker, or a Django/nginx route). Considered below and rejected.
- Session recording, which stays disabled — the masking policy it needs still does not exist.
- Changing what is captured, or where PostHog loads. `POSTHOG_EXCLUDED_PREFIXES` is untouched.

## Decisions

### 1. Two settings, not one: `POSTHOG_CLIENT_HOST` alongside `POSTHOG_API_HOST`

`POSTHOG_CLIENT_HOST` is what the browser initialises against; `POSTHOG_API_HOST` remains what the
Python SDK talks to and keeps its `https://eu.i.posthog.com` default. An empty
`POSTHOG_CLIENT_HOST` falls back to `POSTHOG_API_HOST`, so "not configured" reproduces current
behaviour exactly.

*Where the fall-back lives matters.* It is resolved in `survey.context_processors.analytics`, at
request time, not in `settings.py` at import time. Writing
`POSTHOG_CLIENT_HOST = os.environ.get(...) or POSTHOG_API_HOST` in settings would bake in whatever
the API host happened to be during import; every later override — `self.settings(POSTHOG_API_HOST=…)`
in a test, a preview pointed at a throwaway project — would then move the server while silently
leaving the browser on the frozen value. The existing `test_api_host_is_overridable` catches exactly
this, which is how the first draft of this change was found to be wrong.

*Why not one setting?* Because pointing the Python SDK at the proxy would make our error reporting
depend on a DNS record, a Cloudflare edge and PostHog's proxy tier — three things that can fail
independently of PostHog's ingest API — for zero benefit, in the subsystem whose entire purpose is
to still work when something else is broken. Server-side there is no ad blocker to defeat.

*Why not a boolean plus a derived hostname?* A boolean would encode the subdomain in code. Every
environment that has ever needed a different PostHog target (PR previews, a throwaway project) got
it from an environment variable, and that pattern holds here.

The reason `settings.py:291` uses `or` rather than a `get()` default still applies at the end of the
chain: Render declares these `sync: false`, so the dashboard can hand us an empty string, and an
empty host silently initialises the SDK against nothing. Hence the final fall-back to the Cloud EU
constant in the context processor, not just "client host or API host".

### 2. `ui_host` pinned to `https://eu.posthog.com`

With `api_host` set to a domain of ours, `posthog-js` can no longer infer where the PostHog app
lives, and toolbar / "open in PostHog" links resolve against the proxy. Pinning `ui_host` is
PostHog's documented answer. It is a constant, not a setting: it is a property of which PostHog
cloud we are on, and that is already fixed by `POSTHOG_API_HOST`'s default.

### 3. Static assets ride the proxy, and we verify it rather than assert it

The snippet computes its script source as
`api_host.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js"`. Against
`https://e.mapsurvey.org` the replacement matches nothing, so `array.js` is fetched from the proxy
host — which the managed proxy serves, and which is the whole point: an asset host containing
`posthog` would be blocked exactly like the ingest host.

This is a behaviour we inherit from a minified vendor snippet by way of a string that does not
match, which is a fragile thing to rely on silently. It gets an explicit browser verification step
in `tasks.md` and a note in the template, rather than being left to be rediscovered.

### 4. Managed proxy over a self-hosted one

Alternatives considered:

- **Cloudflare Worker on our own account** — we would own the route end to end. But our DNS is on
  Namecheap, so this means moving the zone to Cloudflare or fronting a subdomain with it: real
  infrastructure work, a new bill, and a new thing to operate, to reach a Cloudflare edge that
  PostHog's managed proxy already reaches for free.
- **Proxying through Django** — a `/e/` route forwarding to PostHog. Rejected outright: production
  is a single 0.5-CPU Render instance pinned by a mounted disk (zero-downtime deploys are already
  impossible for that reason), and putting analytics traffic through gunicorn spends the exact
  resource our load testing says is scarce.
- **Do nothing** — accept blocker loss. Rejected because the loss is biased toward our most
  technical creators, which is the segment the activation funnel is about.

The managed proxy's cost is a consent screen naming Cloudflare as a processor. Since Cloudflare
already carries 100% of our traffic via Render's CDN and runs our Turnstile challenges, this adds a
path, not a party.

### 5. The trust-page wording is part of this change

Two edits, both to `survey/templates/trust.html`:

- The Hosting & Data Residency section gains Cloudflare as CDN and reverse proxy for the hosted
  service, and the existing PostHog bullet (line 66) is extended to distinguish **storage** (PostHog
  Cloud EU) from **transit** (Cloudflare's anycast network, normally terminating at EU edges,
  contractually unguaranteed).
- Cloudflare stops appearing only as "Turnstile" in the abuse-defenses bullet, which today reads as
  if that were the extent of the relationship.

The first of those is true today, before any proxy exists. Shipping the proxy is what makes leaving
it unsaid indefensible rather than merely incomplete.

### 6. A subdomain chosen against blocklists, not for readability

`e.mapsurvey.org`. PostHog's documentation is explicit that `analytics`, `tracking`, `posthog` and
`ph` are matched by name, which rules out the names a reader would find self-explanatory. Single
letter beats a clever word: nothing to pattern-match, nothing to age badly.

## Risks / Trade-offs

- **First-party host makes blocking harder, and that is the point — but it is also the criticism**
  → Scope limits it: PostHog cannot load on `/surveys/` or `/r/`, so no respondent is ever measured
  through this path. The people it applies to are visitors to our own marketing and editor pages,
  where `/trust/` states plainly that product analytics runs. `do_not_track` handling is unchanged
  from the current snippet.
- **EU termination is not contractually guaranteed** → Storage stays in PostHog Cloud EU; only
  transit is affected, and no request content is stored at the edge. `/trust/` says exactly this
  rather than the stronger claim it would be easy to leave standing. For an institution that cannot
  accept it, the answer on that page is unchanged and already there: self-host.
- **DNS mistake sends browser events into a hole** → `POSTHOG_CLIENT_HOST` is set on Render *after*
  the CNAME resolves and PostHog reports the proxy healthy. Until then it is unset and everything
  behaves as today. Rollback is deleting one environment variable, no deploy required.
- **The proxy host serving `array.js` is inferred from a non-matching string replacement** →
  Verified in a browser as an explicit task (network tab: `array.js` 200 from the proxy host, `/e/`
  requests 200), not assumed from reading the minified snippet.
- **Two hosts invite the wrong one being used** → Tests assert both directions: the rendered snippet
  carries the client host, and the Python SDK is configured with the API host. Comments at both
  sites say why they differ.
- **Blocklists eventually catch first-party proxy hostnames** → Real but slow, and the standard
  answer (rotate the subdomain) is a DNS change plus one environment variable. Nothing in the code
  hardcodes the name.

## Migration Plan

Ordered so that no step can break the current state:

1. Accept the managed-proxy terms in PostHog and provision the proxy; note the issued target. The
   documentation says `*.proxy-eu.posthog.com`; the EU project actually issues
   `*.cf-prod-eu-proxy.europehog.com`, so take the value from the API rather than the docs.
2. Namecheap: `CNAME e → <target>`. Wait for propagation and PostHog's health check (docs say 2–5
   minutes, existing-record changes can take hours).
3. Merge the code change with `POSTHOG_CLIENT_HOST` unset everywhere — a no-op deploy by
   construction.
4. Set `POSTHOG_CLIENT_HOST=https://e.mapsurvey.org` on the Render web service and worker.
5. Verify in a browser: `array.js` loads from the proxy host, ingest requests return 200, events
   land in the PostHog project, and a survey page under `/surveys/` still carries no PostHog at all.
6. Verify with a blocker enabled (uBlock Origin) that events still arrive — this is the change's
   entire purpose and the only test that measures it.

**Rollback**: unset `POSTHOG_CLIENT_HOST`. The browser falls back to `POSTHOG_API_HOST` and the
system is byte-for-byte what it is today. The CNAME can stay; an unused DNS record costs nothing.

## Open Questions

- **How much were we actually losing?** Unknowable before the proxy exists. The honest measurement
  is the week-over-week change in identified creators and `$pageview` volume on `/editor/` after
  step 4, against a period with no other funnel changes shipping. Worth writing down when it lands;
  it is also the number that decides whether Plausible deserves the same treatment before it is
  retired.
- **Does the worker need `POSTHOG_CLIENT_HOST` at all?** It renders no templates. It is set on both
  services only so the two never drift into different PostHog configurations — cheap insurance, but
  arguably noise in `render.yaml`.
