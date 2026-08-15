# Design — PostHog base integration (stage 1)

## Context

`survey/templates/partials/_analytics.html` is already the single place a tracker enters the page.
It is included from four heads:

| Template | Surface | PostHog? |
|---|---|---|
| `base_landing.html:8` | marketing landings | yes |
| `base.html:6` | logged-in chrome, account pages | yes |
| `editor/editor_base.html:5` | survey editor | yes |
| `base_survey_template.html:3` | **respondent-facing survey pages** | **no** |

It is fed by `survey.context_processors.analytics`, which reads settings defaulting to empty strings
(`PLAUSIBLE_SCRIPT_URL`, `GOOGLE_SITE_VERIFICATION`); empty renders nothing. That idiom — unset
means off, and off is the default — is what keeps the test suite and local development out of
production analytics, and PostHog follows it exactly.

## Goals

- One event stream for our own web analytics, product analytics and (stage 3) errors, keyed by the
  same person, so the three can be joined in a single query.
- Zero effect when unconfigured: no script tag, no network call, no test elsewhere needs changing.
- One place that decides "is this page ours", so a new template cannot silently opt respondents in.

## Non-goals (stage 1)

Named funnel events (stage 2), error tracking and `posthog-python` (stage 3), removing Plausible
(stage 4), session recording, reverse proxy, feature flags, experiments.

## Decisions

### 1. The boundary against the creator-facing analytics feature is architectural, not incidental

`SurveyEvent`, `TrackedLink`, `survey/events.py` and `PerformanceAnalyticsService` are a product
feature measuring the customer's respondents. PostHog measures us. They are never merged, and the
mechanism that guarantees it is the exclusion list: the PostHog snippet is not rendered on any
respondent surface, so there is no path by which a respondent event could reach PostHog even by
mistake.

Note what this does *not* buy. `/trust/` line 95 claims the survey-taking flow carries no
third-party scripts, and that is already untrue — Plausible loads there through this same partial
and fires `survey_start`, `survey_section_complete` and `survey_complete` by name, and the pages pull
Leaflet, FontAwesome and Bootstrap from public CDNs. The exclusion keeps PostHog from deepening the
problem; it does not fix it. See the proposal for the two branches.

Stated explicitly because the two systems answer superficially similar questions ("where do people
drop off?") about entirely different people, and a future reader optimising for "one analytics
system" would be deleting a feature we sell and creating a DSGVO exposure at the same time.

### 2. The include stays shared; the *gate* moves into the context processor

The obvious implementation is a second partial included from three heads and not the fourth.
Rejected: it encodes the privacy boundary as an omission. The next person to add a base template
copies an existing one, and whether respondents get tracked depends on which one they copied. An
omission is invisible in review.

Instead `survey.context_processors.analytics` computes `POSTHOG_PROJECT_KEY` per request and returns
`''` for excluded paths; `_analytics.html` keeps its existing `{% if %}` shape. A new template that
includes the shared partial inherits the correct behaviour, and turning tracking *on* for a new
surface becomes an explicit edit to a named list in `settings.py`.

The cost: the decision depends on `request.path`, so it is prefix matching rather than view
introspection. Acceptable here because `/surveys/` and `/r/` are fixed by `mapsurvey/urls.py` and
neither is user-configurable.

### 3. Exclusion list, not an inclusion list

`POSTHOG_EXCLUDED_PREFIXES = ('/surveys/', '/r/')`, mirroring the reasoning already written for
`ACQUISITION_NON_MARKETING_PREFIXES` (`settings.py:294-303`): the set of app prefixes is stable
while marketing landings keep being added, so an allow-list would silently drop each new SEO landing
out of analytics.

Both prefixes are third-party audiences: `/surveys/` is a customer's respondents, `/r/` is a
customer's public readers.

`/r/` is arguable — those pages carry the "Made with Mapsurvey" viral loop, whose conversion rate we
will eventually want. Excluded anyway: measuring that loop is a question about *our* inbound traffic,
which lands on a marketing page we do track, and is not a reason to profile the reader. Reversing it
is one line, and should be deliberate.

Worth recording, because it surfaced only when a test failed: `public_results.html` is a standalone
template that includes no analytics partial at all, so `/r/` carries no tracking today — not even
Plausible. The `/r/` entry in the exclusion list is therefore belt and braces rather than an active
prohibition. It earns its place the day someone gives that template a shared head, which is exactly
the kind of change nobody would think to review for tracking implications.

The consequence for tests: any assertion made by rendering a `/r/` page passes whether or not the
gate works. The `/r/` guarantee is asserted where it actually lives — directly against the context
processor — and the "does the gate read the setting" test drives `/surveys/`, whose template does
include the partial and where lifting the exclusion has a visible effect.

### 4. Cloud EU, not self-hosted

Self-hosting PostHog requires ClickHouse, which the Render stack does not offer; standing up managed
ClickHouse to answer product questions is out of proportion. Between clouds, EU
(`https://eu.i.posthog.com`) over US: production already runs in Render Oregon, and US-region
analytics would add a second US processor to a stack whose data residency is already the recurring
objection in German public-sector conversations. It does not fix residency — application data is
still in Oregon — but it avoids making it worse for nothing. Latency is irrelevant: these beacons
leave the visitor's browser, not our server.

`POSTHOG_API_HOST` is a setting, not a constant, so a PR preview can point at a throwaway project
without a code change.

### 5. Identify signed-in creators by user id; carry email as a person property

`distinct_id` is `str(user.pk)` — stable across email and username changes, which natural keys are
not. Email, username and `date_joined` ride along as person properties, set on page load for an
authenticated user.

Email is personal data and is sent deliberately. The alternative — an opaque id and no properties —
produces cohorts that cannot be acted on, and acting on them is the point: the outreach workflow
starts from an account and its behaviour. Under Cloud EU this is an EU-resident processor holding
data we already hold, and it is why the `/trust/` narrowing is in this change rather than after it.

Respondents are never identified, because the snippet never loads on their pages.

### 6. Official CDN snippet, autocapture on, recording off

Loaded from `<api_host>/static/array.js` per PostHog's install snippet rather than vendored into
`survey/assets/` — consistent with how Bootstrap, jQuery and FontAwesome already load in these same
heads, and it keeps the SDK patched without a `collectstatic` cycle. The trade is a third-party
origin in the critical path, mitigated by the snippet's own async loader, which is why the tag is
not a plain blocking `<script src>`.

Config: `capture_pageview: true`, `autocapture: true`, `disable_session_recording: true`,
`person_profiles: 'identified_only'`.

Autocapture is on because stage 1's job is to learn what creators do *before* we know which events
matter; the named taxonomy arrives in stage 2 informed by what autocapture shows, rather than
encoding today's assumptions. `identified_only` keeps anonymous landing traffic out of person
profiles — pageview counts still work, which is what the Plausible comparison needs — and halves
what we store about people who never sign up.

### 7. Plausible runs in parallel, and that is the point

Two trackers double-count nothing important: they write to different systems, and the funnel
dashboard reads only Plausible until stage 4. Running both is the only way to see how PostHog's
pageview numbers relate to a baseline we already trust before the acquisition dashboard depends on
them — and ad-block shortfall, bot filtering and PostHog's session definition all make that
relationship an empirical question, not a documented one.

## Risks / trade-offs

- **`/trust/` claims must be narrowed in this change.** See the proposal. The wording is a business
  statement and needs sign-off.
- **Ad blockers eat a share of client-side events.** Accepted: the numbers that must be exact are
  the server-side funnel ones, which do not come from here. A reverse proxy is the fix if the
  shortfall proves material — and stage 1's parallel run is what measures it.
- **Autocapture is noisy and can get expensive** once the editor is used heavily. Visible as event
  volume before it is visible as a bill; narrow to named events if it grows.
- **Path-prefix gating is coarse.** A respondent-facing view mounted outside `/surveys/` or `/r/`
  would start being tracked silently. The exclusion tests assert against genuinely routed URLs, so a
  route move breaks a test rather than leaking quietly.

## Open questions

1. Proxy PostHog under `mapsurvey.org` to survive ad blockers? Deferred — changes the deployment
   shape, and stage 1 produces the data to decide it.
2. Does the narrowed `/trust/` wording need a cookie banner alongside it? A lawyer's question; it
   gates the production key, not the merge.
3. Track `/r/` once the viral loop is actively optimised? One-line reversal, deliberate decision.
