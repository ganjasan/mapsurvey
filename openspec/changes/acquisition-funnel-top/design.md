## Context

`survey/funnel.py` computes the whole creator funnel live from existing tables on every request:
registrations → activated → logged in → created a survey → added a question → published →
collected ≥1/5/10 responses. That works because every stage is already a row in our own database.

The stages this change adds are not. Impressions live in Google Search Console, landing visits live
in Plausible Cloud, and both are third-party HTTP APIs with latency, quotas, and credentials. The
live-computation pattern cannot be extended to them: a staff page must not block on two external
APIs, and a rate-limited or expired credential must not take the dashboard down.

Current state of the two sources:

- **GSC** — a service account already has read access to `sc-domain:mapsurvey.org`, used by
  `scripts/gsc_report.py`. The JSON key lives at `~/.config/mapsurvey/…json` on the developer
  machine only; production has never seen it. GSC data lags ~2 days and is revised retroactively
  for roughly the following week.
- **Plausible** — the tracking script is live on production (`plausible.io/js/pa-….js`), but no
  Stats API key exists yet; one must be created in the Plausible account.

Demo opens are already in our database: `DEMO_SURVEY_URL` points at a normal survey
(`/surveys/<uuid>`), so every demo run is a `SurveySession` row. What is *not* there is who ran it:
`SurveySession` has no user field and deliberately stores no respondent identity, because it is the
same table that holds our customers' respondents.

Deployment has a web service and a Celery worker but **no beat scheduler**, so "run this daily" has
no existing home.

## Goals / Non-Goals

**Goals:**

- Show the pre-registration funnel — impressions → landing visits → registrations → demo opens —
  next to the existing activation funnel, with step-to-step conversion.
- Keep the dashboard request free of outbound API calls: everything it reads is local.
- Make ingestion idempotent and re-runnable over a date window, so a failed day self-heals on the
  next run and GSC's retroactive revisions land correctly.
- Fail per-source and visibly: a missing key or a dead API degrades one panel, states why, and
  leaves the rest of the page intact.
- Split demo opens into anonymous vs. authenticated without putting respondent identity on the
  shared `SurveySession` table.

**Non-Goals:**

- No per-user cross-source journey stitching (we cannot tie a Google impression to a signup, and
  will not try to). Stage-to-stage rates here are population ratios, not identity-tracked paths.
- No replacement for Plausible's own UI: we sync the few series the funnel needs, not full
  analytics. Deep dives stay in Plausible.
- No backfill of the anonymous/authenticated demo split before deploy — historic demo sessions
  keep only a total.
- No real-time freshness. Daily granularity, daily sync.

## Decisions

### D1 — Store external metrics locally as daily rows; never call an API from the dashboard

A new `AcquisitionDaily` model holds one row per `(source, date, segment)`, written by a management
command and read by the dashboard.

*Why:* the dashboard is a synchronous admin page. Calling GSC and Plausible inline would add
seconds of latency, make the page fail when a third party is down, and burn quota on every reload.
Local rows also give us history that outlives Plausible's retention and GSC's 16-month window.

*Alternative considered:* cache API responses in Redis with a TTL. Rejected — a cache miss still
blocks the request on a live API call, and the data would silently vanish on eviction, which is a
bad property for the numbers we make GTM decisions from.

### D2 — One flat table with nullable metric columns, not JSON, not one table per source

```
AcquisitionDaily(source, date, segment, impressions, clicks, ctr, position,
                 visitors, pageviews, synced_at)
unique_together: (source, date, segment)
```

Metrics not applicable to a source stay `NULL` (Plausible rows have no `impressions`, GSC rows
have no `visitors`).

*Why:* the dashboard aggregates these by summing and dividing across date ranges. Explicit columns
let that happen in SQL; a JSON blob would force Python-side aggregation over every row. Two tables
would duplicate the sync-state and window logic for no gain.

*Trade-off:* adding a metric later means a migration. Acceptable — the metric set here is small and
stable, and a migration is a better forcing function than an untyped blob.

### D3 — `segment` carries a per-source meaning; the marketing group is defined by exclusion

- `source='gsc'`: `segment=''` → the whole domain; `segment='marketing'` → everything except the
  app prefixes listed in `ACQUISITION_NON_MARKETING_PREFIXES`.
- `source='plausible'`: `segment=''` → whole site; `segment='landing'` → `/`;
  `segment='src:<channel>'` → visitors attributed to that referrer channel.

*Why the marketing split matters:* `sc-domain:mapsurvey.org` counts impressions of every published
survey page too. Those are our customers' respondents finding *their* survey, not people
discovering Mapsurvey. Verified against 90 days of live GSC data during implementation: one customer
survey page drew 218 impressions, more than `/trust/` at 183. Folding those into the top of an
acquisition funnel would inflate impressions with traffic that can never convert to a registration.

*Why an exclusion list rather than an allow-list* (revised during implementation): the initial plan
was to enumerate marketing pages. The live page list shows why that inverts badly — marketing
landings are numerous and still multiplying (`/for-planners/`, `/for-government/`,
`/civic-engagement/`, `/community-engagement-platform/`, `/public-consultation-software/`,
`/participatory-budgeting/`, `/alternatives/*`, and more queued in other changes), while the app
prefixes to exclude are a short, stable set (`/surveys/`, `/accounts/`, `/editor/`, `/admin/`,
`/org/`, `/invitations/`, `/internal/`, `/nl/`, `/i18n/`, static and media). With an allow-list,
every future SEO landing would silently fall out of the funnel until someone remembered to add it;
with an exclusion list, new landings count automatically, which is the correct default. GSC's
`excludingRegex` page filter implements this in one query.

*Alternative considered:* separate `page_group` and `channel` columns. Rejected as premature — one
namespaced string covers today's needs and keeps the unique constraint simple.

### D3a — Both GSC segments must be queried in the same aggregation mode

**Found while running the real sync, not during design.** Search Console aggregates impressions two
different ways, and which one you get depends on whether a page dimension or filter is present:

- **property-level** (no page involved): one appearance in search counts once, even if several of
  our pages showed up for that query;
- **page-level** (a page dimension or filter present): each page's appearance counts separately.

Measured over the same 14 live days: 1329 property-level, 1717 page-level. Since the marketing
segment necessarily carries a page filter, querying the whole property without one produced
`marketing (1579) > whole property (1329)` — arithmetically impossible, and it would have silently
poisoned every conversion rate computed from the top of the funnel.

*Decision:* the whole-property query also carries a page filter, one that matches every URL
(`^https?://`), purely to keep GSC in page-level mode. Both segments are then in the same mode and
subtract cleanly: 1717 whole − 1579 marketing = 138 on app and survey pages, which matches a direct
query for those pages (134 for `/surveys/` plus the rest).

*Consequence, worth remembering at the next cross-check:* our stored whole-property number is
page-level and therefore reads **higher** than the total the Search Console UI shows for the same
window. That is not a bug; the two answer different questions. A regression test pins the
`marketing <= whole` invariant so this cannot silently regress.

### D4 — Demo opens: total from `SurveySession`, split via a narrow `DemoOpen` side table

The demo survey is resolved from `DEMO_SURVEY_URL` by extracting the UUID; total demo opens are
simply that survey's non-deleted sessions, available retroactively for all history.

The anonymous/authenticated split needs identity, which `SurveySession` deliberately lacks. Rather
than adding a user FK to the table that stores every customer's respondents, a `DemoOpen` row is
written **only** for sessions on the demo survey, holding the session, a nullable user FK, and a
timestamp.

*Why:* the demo survey is ours, and its respondents are prospects evaluating Mapsurvey — recording
that a logged-in user opened it is legitimate product analytics. Doing the same on the shared
session table would silently start linking our customers' respondents to platform accounts, which
is a privacy change nobody asked for and a GDPR liability.

*Consequence:* the split is forward-only from deploy. The dashboard shows the full-history total
and labels the split with the date it started, rather than pretending the earlier period was 100%
anonymous.

*Alternative considered:* write `authenticated: true` into `SurveyEvent.metadata` on
`session_start`. Rejected — that event log is respondent-behaviour telemetry for survey owners, and
overloading it with platform-side attribution mixes two audiences in one table.

### D5 — Ingestion is a management command run by a Render Cron Job

`python manage.py sync_acquisition_metrics [--days N] [--source gsc|plausible]` fetches the last N
days (default 7) and `update_or_create`s rows per `(source, date, segment)`.

*Why a 7-day rolling window rather than "yesterday":* GSC revises recent data for several days
after the fact, and a day lost to a transient failure would otherwise stay permanently missing.
Re-writing the last week on every run makes both problems self-correcting, and idempotency makes
re-running safe at any time.

*Why cron and not Celery:* there is a worker but no beat scheduler. Adding beat means a new
long-running process, a schedule store, and another thing to monitor for one daily job. A Render
cron service is one block of `render.yaml` and its failures are visible in the Render dashboard.

*Alternative considered:* sync lazily on dashboard view when data is stale. Rejected — it makes an
admin page occasionally take 10 seconds, and the sync stops happening entirely during any period
nobody opens the dashboard, which is exactly when history matters most.

### D6 — Credentials come from the environment, and their absence is a first-class state

- GSC: `GSC_SERVICE_ACCOUNT_JSON` (the key's contents as an env var) with the existing `GSC_KEY`
  file path kept as a local-development fallback; `GSC_SITE` for the property.
- Plausible: `PLAUSIBLE_API_KEY` and `PLAUSIBLE_SITE_ID`.

A `AcquisitionSyncState` row per source records last success, last attempt, and last error. The
dashboard reads it and renders one of: *configured and fresh*, *configured but stale/failing (with
the error and the age)*, or *not configured*.

*Why an env var rather than a mounted key file:* Render has no secret-file primitive on the plan in
use, and committing a key is not an option. Reading JSON from the environment keeps the key out of
both the repo and the image.

*Why surface the error instead of showing zeros:* a broken sync and a genuinely quiet week look
identical as a "0" on a chart. Anything derived from a source in an unknown state is shown as "—",
never as a number.

### D7 — Conversion rates are labelled as cross-source ratios, not tracked paths

The block shows impressions → visits → registrations → demo opens with a percentage between each
pair, computed over the same date window from four different measurement systems (GSC, Plausible,
our DB, our DB).

*Why call this out in the UI:* the numbers do not describe one cohort of people moving down a
funnel. Bot-filtered Plausible visitors, ad-blocked pageviews, and Google's impression definition
do not compose into a clean chain. The block therefore states its window and sources inline and
reads as "trend of ratios", which is what it can honestly support. Presenting it as a tracked
funnel would invite conclusions the data cannot carry.

### D8 — The dashboard block is a new section ② in the existing template

The funnel dashboard is one template with numbered sections (① Goals, ② This week, …). Acquisition
becomes the new ②, pushing the rest down, because it is the top of the funnel and belongs above the
registration-onward stages.

*Why not a separate admin page:* the whole value is seeing acquisition adjacent to activation. Two
pages would mean two loads and two mental contexts for one question.

## Risks / Trade-offs

- **GSC data lags ~2 days and is revised** → the block labels its window explicitly ("through
  <date>, GSC lags ~2 days") and the 7-day rolling re-sync picks up revisions.
- **Plausible undercounts due to ad blockers; GSC impressions are inflated relative to any human
  notion of "seeing" the site** → the two are never summed or reconciled, only shown as separate
  series; conversion percentages are framed as ratios (D7).
- **A leaked service-account key exposes read access to Search Console data** → the account is
  read-only and restricted to one property; the key stays in Render's env, never in the repo or a
  build layer.
- **The demo split is forward-only, so early weeks look anonymous-heavy** → the split is rendered
  from its start date onward and annotated, rather than backfilled with an assumption.
- **`DEMO_SURVEY_URL` can be unset, point at a deleted survey, or be changed** → resolution is
  defensive: unresolvable means the demo metrics render as "not configured", not a 500. Changing
  the URL to a different survey silently changes what the metric means; the resolved survey name is
  shown in the panel so the reading matches reality.
- **A new daily job is a new thing that can quietly stop** → sync state is on the dashboard itself,
  so a stalled sync is visible where the numbers are read, without a separate alerting setup.
- **Adding `google-api-python-client` to production dependencies** grows the image for one daily
  job → accepted; the alternative is hand-rolling OAuth2 service-account JWT signing.

## Migration Plan

1. Ship the models and the command with no credentials configured. The dashboard block renders in
   the "not configured" state; nothing else changes.
2. Create the Plausible Stats API key; add `PLAUSIBLE_API_KEY` / `PLAUSIBLE_SITE_ID` and the GSC
   service-account JSON to the Render environment.
3. Run the command manually with a wide `--days` to backfill as far as each API allows (GSC: up to
   16 months; Plausible: per plan retention).
4. Enable the cron service.
5. `DemoOpen` starts recording on deploy; the total-opens series is retroactive from existing
   sessions on day one.

Rollback: the block is additive and reads only new tables. Disabling the cron service and leaving
the credentials unset returns the dashboard to its current behaviour with an extra "not configured"
panel; the migration itself is safe to leave in place.

## Open Questions

- ~~Which URL prefixes constitute the `marketing` page group?~~ **Resolved during implementation**
  by checking 90 days of live GSC data: the group is defined by exclusion instead, see D3.
- Does the current Plausible subscription include Stats API access? If it does not, the Plausible
  half ships in the "not configured" state and the GSC half still works — the design keeps them
  independent for exactly this reason. The client already treats Plausible's `402` as
  not-configured rather than as a failure, so this degrades without a code change.
