# Acquisition metrics, signup attribution, PostHog analytics and error tracking

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Acquisition metrics (top of the funnel)**: search impressions and clicks, landing visits and the
channel mix are read on the PostHog **AARRR** dashboard (`POSTHOG_AARRR_DASHBOARD_URL`, project
248938 dashboard 941308), where Google Search Console and Bing Webmaster Tools are native warehouse
sources (`googlesearchconsole_*`, `bingwebmastertools_*` tables). Nothing in this application
fetches or stores provider metrics any more — the former `sync_acquisition_metrics` command,
`AcquisitionDaily`/`AcquisitionSyncState` and the `mapsurvey-acquisition-sync` cron were retired
(change `acquisition-instrumentation`). Two rules for every HogQL over those tables: filter
`country != 'mar'` (38% of impressions are Moroccans searching a namesake app) and keep marketing
pages apart from `/surveys/` and `/r/` (those impressions are customers' respondents finding their
own survey). GSC data exists only from 2026-07-03, when the property was created. The staff funnel
dashboard at `/admin/survey/funnelreport/` keeps what only our database answers: registrations in
the window, registrations by first-touch source, and demo opens — total from `SurveySession` on the
`DEMO_SURVEY_URL` survey (retroactive), anonymous/signed-in split from `DemoOpen` (forward-only;
the user FK lives there and never on `SurveySession`, which must not link customers' respondents to
platform accounts). Demo helpers live in `survey/demo.py`.

**Signup attribution**: `FirstTouchMiddleware` writes a signed 90-day first-party cookie (`ms_ft`)
on the first marketing-page response — referrer host, bucket, UTM triple, landing path, no
identifier — and never on `/surveys/`, `/r/`, the editor or admin. `persist_signup_attribution`
reads it at registration (legacy session values as fallback) and never the request's own referrer,
which is the site itself. `classify_source` in `survey/events.py` buckets referrers as `email`,
`ai` (ChatGPT, Perplexity, Gemini, Claude, Copilot), `search_other` (DuckDuckGo, Brave, Yahoo,
Ecosia…), `google`, `bing`, `social`, `other`/`direct`; an AI `utm_source` promotes a direct visit to
`ai` because ChatGPT tags links with `utm_source=chatgpt.com` and often sends no referrer. The row
reaches PostHog as `$set_once` person properties (`first_source_bucket`, `first_referrer_host`,
`first_utm_*`, `first_landing_path`) on `creator_registered`; `sync_posthog_person_properties
--reclassify` repairs and backfills existing rows.

**First response and distribution events**: `SurveySession.opened_by_kind` (`external | owner |
collaborator | preview`) is set from the signed-in user's relation to the survey, never from
anything about an anonymous visitor. `survey_first_response` fires only for the first `external`
session. Creator events `share_link_copied`, `qr_shown`, `embed_copied` (browser, guarded by
`window.posthog`) and `responses_viewed`, `data_exported` (server) carry `survey_id` and a surface
only — never a slug or URL.

**Internal product analytics (PostHog)**: client-side snippet in
`survey/templates/partials/_analytics.html`, gated by `POSTHOG_PROJECT_KEY` (empty default = nothing
renders, which is what keeps tests, local dev and PR previews out of the production project) and
`POSTHOG_API_HOST` (Cloud EU). It measures **us**: which creator-facing screens get used, where
activation leaks. Plausible was removed in September 2026; respondent pages load no third-party
analytics script at all.

**Two hosts, on purpose.** The browser initialises against `POSTHOG_CLIENT_HOST` — a first-party
hostname CNAME'd to PostHog's managed reverse proxy, because `eu.i.posthog.com` is on every
mainstream blocklist and our creator audience runs blockers more than most. The server-side client
(`survey/apps.py`, and through it the middleware and the Celery receiver) keeps using
`POSTHOG_API_HOST` directly: no ad blocker runs inside our containers, so proxying error capture
would only add a DNS record and a CDN edge to the subsystem that must survive an outage. Empty
`POSTHOG_CLIENT_HOST` falls back to `POSTHOG_API_HOST`, and that fallback lives in the context
processor rather than in `settings.py` — resolving it at import time would freeze the value and
leave the browser on a stale host whenever the API host is overridden. `ui_host` is pinned to
`https://eu.posthog.com` because a custom `api_host` leaves the SDK unable to find the PostHog app.
Note the snippet derives its asset host by string-replacing `.i.posthog.com`, which is a no-op
against a proxy domain — so `array.js` correctly loads from the proxy too.

Two rules that are easy to get wrong:

- **PostHog never loads on respondent surfaces.** Two settings enforce one rule, both read in
  `survey.context_processors.analytics` — *not* by omitting the include from
  `base_survey_template.html`, since an omission would be invisible in review and a new base
  template would inherit whatever its author happened to copy.
  `POSTHOG_EXCLUDED_PREFIXES` (`/surveys/`, `/r/`) covers respondent URLs.
  `POSTHOG_EXCLUDED_VIEW_NAMES` (`editor_section_preview`, `editor_survey_thanks_preview`) covers
  the ones no prefix can express: the editor's Live preview frames a real respondent page served
  from under `/editor/`, where the surrounding page *is* tracked. That iframe used to run a
  second PostHog client in the creator's tab — one session with two recorders, so session replay
  alternated between the iframe's ~470px viewport and the editor's ~1600px one, and 1169 of 1799
  editor `$pageview`s over seven days were iframe loads rather than people. `_analytics.html` also
  refuses to `posthog.init()` when `window.top !== window.self`, which catches framed surfaces
  added after the view-name list. `editor_question_preview_live` and `public_results_preview`
  render standalone templates that include no analytics partial, which is why they are absent
  from the list — a new preview view that extends a base template must be added to it.
- **`SurveyEvent`/`TrackedLink`/`survey/events.py`/`PerformanceAnalyticsService` are a different
  system and must never be folded into PostHog.** They measure our *customers'* respondents on the
  customer's behalf (section funnel, referrer buckets, UTM campaigns, page load) and are a feature we
  sell. That data stays in our database. The two answer superficially similar questions about
  entirely different people.

**Error tracking (PostHog, same key)**: three capture paths — Django view exceptions via
`posthog.integrations.django.PosthogContextMiddleware` (in `MIDDLEWARE` after auth), Celery task
failures via the `task_failure` receiver in `mapsurvey/celery.py`, and client-side JS exception
autocapture (a PostHog project setting, not a template change). Unset key = the client is explicitly
disabled in `survey.apps.SurveyConfig`. Errors on `/surveys/`/`/r/` ARE captured (they are our
defects) but scrubbed by `_posthog_scrub_tags` in `settings.py` — no respondent IP/user-agent, URL
truncated to the prefix; `/admin/` and `/__debug__/` are not captured at all. The `posthog` package
is pinned `~=6.9`: 7.x needs Python ≥3.10, and 6.7.5–6.7.13 shipped with silently broken Django
exception capture — canary tests in `PostHogErrorTrackingTest` guard both directions.
