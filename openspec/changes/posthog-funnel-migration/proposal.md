# Moving the growth funnel to PostHog — analysis and plan

Written as an analysis first, because the honest answer to "move the admin dashboard to PostHog" is
**move about half of it, and the half that matters most needs a data backfill before it says anything
true.** This document is for a decision, not for implementation. No code changes accompany it.

## What the admin dashboard actually is

`/admin/survey/funnelreport/` looks like one page. It is three systems in a trench coat, and they
have different answers to "should this move".

`dashboard_context()` (`survey/funnel.py:858`) assembles 15 blocks from:

**1. `CreatorFunnelService` — the funnel, computed from current table state.** Not from events. It
reconstructs each stage by asking the database a question about *now*: which user ids own a survey
(`_created_uids`), which own a survey with a question, which own a published one, how many sessions
each has collected. Registration cohorts come from `auth_user.date_joined`.

**2. `AcquisitionService` — external numbers, synced.** Google Search Console impressions and clicks,
Plausible landing visits, demo opens, into `AcquisitionDaily` by a daily cron. Nothing is fetched
during a request.

**3. The cohort system — a classification vocabulary.** `CohortDimension` → `Cohort` → `UserCohort`,
with automatic assignment by email domain (`survey/cohorts.py`) plus `DomainSegmentRule` rows loaded
from a gitignored file, because naming customer domains in a public repository would publish our
roster.

## The finding that shapes everything

**The dashboard is a state reconstruction; PostHog is an event log. They are not the same shape, and
converting one to the other is the whole job.**

Concretely: "created a survey" in the dashboard means *this user currently owns a row in
`survey_surveyheader`*. In PostHog it would mean *this user emitted `survey_created` at some point*.
Those agree only if the event was emitted at the time and never lost. Today no such event exists —
PostHog's first event is from **2026-08-15**, and the platform's first signup is from months earlier.

So a naive move produces a dashboard that starts empty, disagrees with the old one for months, and
cannot answer the question that motivated it: whether AI onboarding changed activation, which needs
a *before* as much as an after.

There are exactly two ways out, and the choice is the main thing to decide:

**A. Backfill history into PostHog.** Every stage the dashboard computes has a timestamp already in
the database — `date_joined`, `SurveyHeader.created_at`, `Question` creation, `SurveySession.start_datetime`.
Those can be replayed into PostHog as events carrying their original timestamps, after which
PostHog's funnels, retention and lifecycle insights work over the full history. Feasible; see design.

**B. Forward-only.** Keep the admin dashboard as the historical record and let PostHog accumulate.
Cheaper today, and it means for several months every funnel question has two answers that disagree,
with no way to tell which is right.

**Recommendation: A**, because the reason to do this at all is to stop reconstructing behaviour from
state, and a forward-only move leaves us reconstructing for another two quarters.

## What should move

| Block | Verdict | Why |
|---|---|---|
| Stage funnel (reg → created → question → published → responses) | **Move** | This is literally what PostHog funnels are. It also gains drop-off per step, time-to-convert, and breakdown by any property — which is how `creation_method: ai\|manual` answers the AI-onboarding question |
| `cohort_funnel` (per registration-month) | **Move** | Native: a funnel broken down by signup month, or retention keyed on registration |
| `time_to_value` (median days to survey/publish/response) | **Move** | Funnel "time to convert" gives median *and* distribution, which our single median hides |
| `active_user_metrics` (active 7/30/90, returned, dormant) | **Move — and it gets better** | Lifecycle and retention insights are native. Our version is a hand-rolled approximation over `last_login`, `UserActivity`, survey `updated_at` and response times |
| `weekly_signups`, `weekly_activity` | **Move** | Trends |
| `cohort_breakdown` (by segment/plan) | **Move as person properties** | Send the assigned cohort as a person property; PostHog cohorts then filter every insight, replay and future experiment. This is the biggest *gain* — today the segmentation only exists on one admin page |
| `top_active_surveys` | **Move** | Trends broken down by survey |

## What must stay, and why

| Block | Verdict | Why |
|---|---|---|
| `DomainSegmentRule` and the classification logic | **Stays** | The *rules* map named customer domains to segments. The resulting **label** (`segment: university`) is fine to send; the rule table is our customer roster and must not leave our database |
| `dormant_valuable`, `collecting_unpublished` | **Stays** | Operational worklists that carry emails and drive outreach. PostHog cohorts could express them, but the outreach workflow reads from our DB and this adds a round trip for no gain |
| `AcquisitionService` — the GSC half | **Stays** | Search Console impressions and clicks are not in PostHog and never will be. The Plausible half is stage 4's business, not this change's |
| `goals` (targets vs GTM numbers) | **Stays for now** | The targets are business constants in code. Could become PostHog insight targets later; no urgency |
| `cluster_radar` (48h signup bursts, same-domain groups) | **Stays** | Bespoke detection, cheap where it is, and no PostHog primitive fits it well |
| `abuse_summary` | **Stays** | Reads `AbuseEvent`; a security audit log, not product analytics |
| `SurveyEvent` / Performance tab / UTM links | **Never moves** | Unchanged from the stage-1 boundary: this measures our *customers'* respondents on their behalf. It is a feature we sell |

## What this is not

- Not deleting the admin dashboard. It keeps the acquisition top-of-funnel, the worklists, the
  cluster radar and the abuse summary — and stays the fallback while PostHog's numbers are being
  trusted.
- Not stage 2. The named activation events this needs are the same ones stage 2 needs; doing this
  first means stage 2 is mostly already done, which is the argument for this ordering.
- Not respondent analytics. Nothing here sends respondent data anywhere.

## Cost and prerequisites

- Backfill volume is small: roughly (real users × ~5 stage events) + one event per response session.
  At current scale that is comfortably inside the 1M events/month free tier, as a one-off.
- **A paid plan must be enabled to unlock historical imports.** PostHog's migration docs state
  historic imports are free but the feature requires a card on file. Usage stays inside the free
  tier, so the expected bill is $0 — but a card is a decision, not a detail.
- Live production numbers could not be read while writing this: `MAPSURVEY_DB_URL` no longer
  authenticates (SSL closes; the IP is allow-listed, so the credential looks stale) and the Render
  MCP reports `SSL/TLS required`. Volume estimates above are structural, not measured. Worth
  confirming before the import.

## Open questions for the decision

1. **A or B** — backfill, or forward-only?
2. **Card on file for the paid plan** — required for A.
3. **How far back?** Everything, or from a date where the data is trustworthy? Cohort labels and
   `SignupAttribution` only exist forward from their own deploys, so the deep history has stages but
   thinner segmentation.
4. **Does the admin dashboard eventually shrink** to acquisition + worklists, or stay whole as a
   cross-check?
