# PostHog as the single home for internal analytics

## Why

We measure ourselves with three tools that do not talk to each other, and one gap where the third
tool should be:

- **Web analytics** — Plausible answers "how many visits", cookielessly and cheaply, and stops at
  the door. It cannot tell us what the visitor did after registering, because it has no idea who
  they are.
- **Product analytics** — does not exist as such. `survey/funnel.py` reconstructs a funnel after the
  fact from rows that happen to have been persisted. That is why we keep learning things late and
  sideways: `end_datetime` is set on 0 of 4586 sessions, so completed and abandoned are
  indistinguishable; a creator copied 12 blocks by hand and cut 9 versions in one day and we found
  it by reading survey structure, not by any signal the product emitted; a lead logged in and
  deleted their map 13 seconds later and we know only because of Render request logs.
- **Error tracking** — does not exist. `LOGGING` (`settings.py:359-389`) sends WARNING+ to stdout so
  500 tracebacks reach Render logs. Nothing aggregates them, nothing alerts, nothing tells us
  whether a traceback hit one creator once or forty creators all morning.

Three questions, three answers that cannot be joined: we cannot ask "did the visitors from this
channel hit the error that made them leave". PostHog answers all three against one event stream
keyed by the same person.

The immediate forcing function: `feature/ai-survey-generator` is finished (31/31 tasks) and
unmerged. It exists to fix the largest known leak — of 222 registrations 53% ever create a survey
and 38% ever add a question. Merging it without instrumentation means shipping the biggest
activation change we have made into a funnel we can only reconstruct afterwards from table rows.

## What this is not

The product already contains a second, unrelated analytics system, and conflating the two would be
a serious mistake:

`SurveyEvent` (`survey/models.py:173`), `TrackedLink` (:194), `survey/events.py`,
`PerformanceAnalyticsService`, the Performance tab and the UTM link generator measure **our
customers' respondents** — section funnels, referrer buckets, campaign attribution, page load. That
is a feature we sell to creators about their own surveys. It stays in our database, unchanged and
untouched by this change, for three reasons: the data belongs to the customer, `/trust/` promises
respondents no third-party scripts in the survey-taking flow, and sending respondents to a
third-party processor is exactly the DSGVO exposure our government pipeline cannot carry.

**PostHog is for internal analytics only.** Ours, about us.

## What Changes

Delivered in stages, because "replace three systems" is not one reviewable change. This proposal
covers stage 1; stages 2–4 are separate changes with their own specs, listed here so the
destination is explicit rather than emergent.

### Stage 1 — base integration (this change)

- PostHog Cloud EU behind `POSTHOG_PROJECT_KEY` / `POSTHOG_API_HOST`, **unset by default** so local
  development, the test suite and PR previews emit nothing.
- The snippet loads on our surfaces only — landings, editor, account and organization pages — and
  never on `/surveys/` or `/r/`. Enforced in the context processor, not by which template forgot to
  include it.
- Signed-in creators identified by user id, with `email` / `username` / `date_joined` as person
  properties, so a cohort maps back to a real account the way the outreach workflow already works.
- `/trust/` narrowed: two unscoped bullets currently promise no cookies and no third-party trackers
  site-wide. They become claims about respondents, which is what they were always meant to be.
- **Plausible keeps running.** Stage 1 is additive on purpose: two trackers in parallel is how we
  find out what PostHog's numbers look like next to a known baseline before betting the acquisition
  dashboard on them.

### Stage 2 — activation funnel (`posthog-activation-funnel`)

Named events for the stages `survey/funnel.py` currently reconstructs: registration, first survey
created, first question added, published, first response. Emitted with `creation_method` so the
AI-generated path and the empty-editor path are distinguishable from the first event onward. This
is what makes the AI generator's effect measurable rather than inferred.

### Stage 3 — error tracking (`posthog-error-tracking`)

Client exceptions via `posthog-js` exception autocapture, server exceptions via `posthog-python`
attached to Django's logging config. Net-new capability; nothing is being migrated. This is the
stage that requires the server-side SDK — client-side JS cannot see a Django 500.

### Stage 4 — retire Plausible (`posthog-replaces-plausible`)

Point the `plausible` source of `sync_acquisition_metrics` at PostHog's query API, drop
`PLAUSIBLE_*`, remove the script. Deliberately last: it happens only after stage 1 has run in
parallel long enough that the two series can be compared, and it is the only stage that can put a
wrong number on the funnel dashboard. GSC is unaffected and stays.

## Risk — `/trust/` must be narrowed in this change, not later

`/trust/` is the page we send IT security teams to; it is the answer to Manuel Frost's "my security
team must approve this first". It currently claims, unscoped:

- *"No cookies used for tracking or analytics purposes"* (line 37)
- *"No third-party trackers or advertising scripts"* (line 40)

Both sit in a respondent-focused section but read site-wide. PostHog sets a cookie, builds person
profiles and is a third-party tracker. Shipping it while those bullets stand unqualified makes our
trust page wrong on the exact axis it exists to reassure — so the narrowing is part of this change,
not a follow-up.

The wording change is a statement about the business rather than a code detail and needs sign-off
before merge.

### Line 95 is already inaccurate, before PostHog exists

*"No third-party scripts — no external JavaScript, trackers, or CDN dependencies in the survey-taking
flow"* (line 95) does not describe the product as built. Plausible loads on respondent pages through
the same shared partial and fires respondent events by name:

- `base_survey_template.html:859` — `plausible('survey_start', …)`
- `base_survey_template.html:715` — `plausible('survey_section_complete', …)`
- `survey_thanks.html:17` — `plausible('survey_complete', …)`

Respondent survey pages additionally load Leaflet, FontAwesome and Bootstrap from public CDNs, which
the same bullet denies.

Keeping PostHog off `/surveys/` and `/r/` therefore does not *preserve* that claim — it declines to
make it worse. Fixing it is a real decision with two branches, and neither belongs in this change:

1. **Make the claim true** — move the respondent funnel off Plausible onto `SurveyEvent`, which
   already records `session_start` / `section_view` / `section_submit` / `survey_complete` and would
   make the Plausible respondent events redundant; then self-host the CDN assets.
2. **Correct the wording** — say what actually runs in the survey-taking flow.

Branch 1 is the one consistent with everything else we tell government buyers, and it is cheap
precisely because `SurveyEvent` already exists. Raised as a follow-up rather than assumed.

## Found while doing this — out of scope

`/trust/` also claims *"Hosted on Render.com — Frankfurt, Germany (EU region)"* and *"Data stays in
the EU — no cross-border transfers outside the European Economic Area"* (lines 55–56). `render.yaml`
declares no `region:`, so every service runs in Render's default region, Oregon (US). That is
inaccurate today, independent of PostHog, on the page most likely to be read by a German
procurement officer.

Not touched here: the fix is either a migration (backlog #11,
`improvement-frankfurt-server-migration.md`) or a wording correction, and choosing between them is a
business decision.
