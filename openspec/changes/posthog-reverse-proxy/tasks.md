## 1. Settings: split the browser host from the server host

- [x] 1.1 Add `POSTHOG_CLIENT_HOST` to `mapsurvey/settings.py` next to `POSTHOG_API_HOST`, defaulting
      to empty. The fall-back to `POSTHOG_API_HOST` belongs in the context processor, not here:
      resolving it at import time freezes whatever the API host was then, so a later override
      (`self.settings(...)`, a preview pointed elsewhere) would leave the browser on the stale value
- [x] 1.2 Comment it with the reason the two differ: browser traffic needs a first-party host to
      survive blockers, server-side capture must not gain a DNS/edge dependency
- [x] 1.3 Confirm `survey/apps.py` and `mapsurvey/celery.py` still read `POSTHOG_API_HOST` and leave
      them unchanged

## 2. Browser snippet

- [x] 2.1 In `survey/context_processors.py`, publish the client host (falling back to the API host)
      instead of `POSTHOG_API_HOST`; keep the module-level default consistent with settings
- [x] 2.2 In `survey/templates/partials/_analytics.html`, add `ui_host: 'https://eu.posthog.com'` to
      the `posthog.init` config
- [x] 2.3 Add a short comment above the snippet recording that the vendor line derives the asset host
      by replacing `.i.posthog.com`, which is a no-op against a custom domain, so assets load from
      the proxy — deliberate, and verified in task 5.2

## 3. Deployment configuration

- [x] 3.1 Add `POSTHOG_CLIENT_HOST` (`sync: false`) to the web service and the worker in
      `render.yaml`
- [x] 3.2 Document both hosts in `.env.example`: what each one is for, that leaving the client host
      unset reproduces current behaviour, and the subdomain-naming constraint (no `ph`, `analytics`
      or `track` — blocklists match them by name)

## 4. Trust page

- [x] 4.1 In `survey/templates/trust.html`, add Cloudflare to the Hosting & Data Residency section as
      the CDN and reverse proxy fronting the hosted service, including analytics traffic
- [x] 4.2 Extend the product-analytics bullet (line 66) to separate storage (PostHog Cloud EU) from
      transit (Cloudflare's anycast network, normally EU-terminating, not contractually guaranteed)
- [x] 4.3 Re-read the abuse-defenses bullet (line 102) so Cloudflare no longer reads as
      "Turnstile vendor only"
- [x] 4.4 Run the template-comment guard test immediately after editing — `{# #}` is single-line and
      a multi-line one renders as visible page text

## 5. Tests

- [x] 5.1 Extend `PostHogSnippetTest` / `PostHogContextProcessorTest` in `survey/tests.py`:
      configured client host is what the snippet initialises against and `eu.i.posthog.com` does not
      appear; empty client host falls back to the API host; excluded prefixes stay excluded with the
      proxy configured; an empty project key renders nothing either way; `ui_host` is present in
      both configurations
- [x] 5.2 Add a test that the server-side client is configured with `POSTHOG_API_HOST` while
      `POSTHOG_CLIENT_HOST` is set to something else — the regression this change most invites
- [x] 5.3 Add a trust-page test asserting the Cloudflare disclosure and the storage/transit wording
      are present
- [x] 5.4 Run `./run_tests.sh survey` and record the delta against the pre-change baseline — 1248
      tests, OK (1 skipped), no failures introduced

## 6. Provisioning (outside the repo, in order)

- [x] 6.1 Accept the managed-proxy terms in PostHog, provision the proxy for the EU project, note the
      issued target. Done 2026-08-17 via the MCP `proxy-create` tool: `e.mapsurvey.org` →
      `3fcb8a68424c2bb1aabd.cf-prod-eu-proxy.europehog.com.`, id
      `01a00e50-a2c8-0000-cc0f-69c8a4f127c7`, status `waiting` until DNS resolves
- [x] 6.2 Namecheap: `CNAME e → 3fcb8a68424c2bb1aabd.cf-prod-eu-proxy.europehog.com.`; wait for
      PostHog to move the record off `waiting` (2–5 min for a new record) and issue the certificate.
      Done 2026-08-17: resolving on the authoritative NS, 1.1.1.1 and 8.8.8.8; record went
      `waiting` → `issuing` → `valid` at 06:10 UTC; `https://e.mapsurvey.org/static/array.js`
      returns 200 (248932 bytes), which is the proxy serving PostHog's own SDK asset
- [x] 6.3 Merge and deploy with `POSTHOG_CLIENT_HOST` unset — a no-op by construction
- [x] 6.4 Set `POSTHOG_CLIENT_HOST=https://e.mapsurvey.org` on the Render web service and the worker
      **in the same session as 6.3**. Between the two, `/trust/` says analytics traffic transits
      Cloudflare while the browser is still talking to PostHog directly — a disclosure wider than
      the fact, which is the harmless direction but not one to leave standing for days. Do not merge
      before 6.2 resolves

## 7. Verification in production

- [x] 7.1 Load `/editor/` and confirm in the network tab: the PostHog asset loads from the proxy host
      with a 200, and ingest requests return 200. Done 2026-08-17 on `/` and `/trust/`:
      `POST https://e.mapsurvey.org/e/` → 200, no request to any `posthog` hostname; the rendered
      snippet carries `e.mapsurvey.org` as api_host and `eu.posthog.com` as ui_host
- [x] 7.2 Confirm events arrive in the PostHog project and an authenticated creator is still
      identified. Proxied visits land: `$set` and `$pageleave` rows for `https://mapsurvey.org/` and
      `/trust/` at 06:17–06:18 UTC, and real `/editor/` traffic at 06:21 produced `$pageview` and
      `$autocapture` through the proxy
- [ ] 7.3 Repeat 7.1 with uBlock Origin enabled — events must still arrive; this is the only check
      that measures what the change is for
- [x] 7.4 Load a survey page under `/surveys/` and a results page under `/r/` and confirm neither
      carries the proxy host or any PostHog reference. Done for `/surveys/`: the live demo survey
      renders zero `posthog` / `e.mapsurvey.org` matches, and with a cleared network log a reload
      issues no request to the proxy. Plausible still loads there, unchanged and separately known.
      No `/r/` page is currently published, so that half rests on the unit tests
- [ ] 7.5 Trigger a deliberate server-side error on staging or a preview and confirm it still reaches
      PostHog error tracking with the proxy configured
- [ ] 7.6 A week after 6.4, record the change in `$pageview` volume and identified creators on
      `/editor/` against the preceding week, and note it in the change — it is the only estimate we
      will ever get of what blocking was costing, and it informs whether Plausible needs the same
      treatment before retirement
- [x] 7.7 Explain the missing `$pageview` seen during 7.2. Two automated Chrome visits produced
      `$set` and `$pageleave` but no `$pageview`, which briefly looked like proxied pageviews being
      dropped — the metric 7.6 is built on. Resolved by ordinary traffic minutes later: real
      `/editor/` visits at 06:21 UTC captured `$pageview` and `$autocapture` through the proxy, so
      the gap was PostHog's bot filtering reacting to the automated session, not the proxy
