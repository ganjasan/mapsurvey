## Context

The 2026-07-04 GTM baseline was produced by hand-running aggregation SQL against prod
(`auth_user`, `survey_surveyheader`, `survey_surveysession`). That work needs to become a
standing, staff-only view so the weekly growth review is a glance, not a query session.

Two adjacent changes already exist and their models are **already in `survey/models.py`**:
- `SurveyEvent` (append-only event log, FK → `SurveySession`) and its helpers in `survey/events.py`
  (`emit_event`, `build_session_start_metadata`, `_classify_referrer`, `store_utm_in_session`,
  `_consume_utm_from_session`).
- `TrackedLink` (per-survey UTM links) from utm-link-generator.

Both are **respondent-side, per-survey**: they answer "how do respondents move through *this*
survey?" This change answers a different question — "how do *creators* move from landing to an
activated account across the *platform*?" — for a different audience (founder/staff). It reuses
the referrer/UTM parsing helpers but does not extend `SurveyEvent`, whose grain (session) is wrong
for creator-lifecycle events.

Current registration path: `mapsurvey/urls.py` → `AbuseProtectedRegistrationView`
(subclass of `AsyncEmailRegistrationView` → django-registration `RegistrationView`). The user is
created by the form during activation-backend flow; abuse defenses (honeypot, rate-limit, Turnstile)
run in `dispatch()`. `store_utm_in_session()` already exists and is called on survey entry — it can
be reused verbatim on the landing/register GET.

## Goals / Non-Goals

**Goals:**
- Turn the baseline SQL into a repeatable staff-only dashboard with zero new infra (no PostHog).
- Ship the dashboard (Phase 0) with **no migration** — pure aggregation over existing tables,
  retro-active on first load.
- Start attributing signups to a source (Phase 1) so the growth hypotheses become measurable.
- Reuse existing referrer/UTM helpers; add no duplicate parsing logic.

**Non-Goals:**
- Respondent-side / per-survey funnel — owned by survey-event-tracking.
- A full event pipeline (`analytics_events` with `visit`/`publish`/etc. per-event rows). The
  backlog floated this; we deliberately compute creator-lifecycle stages from existing tables
  instead of emitting events, because every stage is already derivable (a row in `SurveyHeader`
  = "created", `status IN (published,…)` = "published", a `SurveySession` = "response"). Only the
  one stage that is *not* derivable — the acquisition source — needs new persistence.
- IP persistence / geo-IP. No new PII.
- Exposing the funnel to non-staff (creators/investors). If needed later, port the service to an
  `/editor/admin/` view — the service layer is written to make that a template swap.

## Decisions

**D1 — Custom admin page via proxy model + `changelist_view` override, not a third-party dashboard app.**
A `FunnelReport(SurveyHeader)` proxy model (`Meta.proxy = True`, no table) registered on the admin
site with `change_list_template = "admin/funnel_dashboard.html"` and an overridden `changelist_view`
that injects the aggregates into `extra_context`. Rationale: gets staff auth, menu placement, and
site chrome for free; zero dependencies; matches the backlog "admin-only dashboard" decision.
*Alternatives:* django-admin-charts / django-dashboards (heavy, semi-maintained, rejected);
a bespoke `/editor/admin/funnel/` HTMX view (more work, no auth for free — deferred as the
"promote to non-staff" path only).
*Proxy base choice:* proxy off `SurveyHeader` (not `User`) to avoid a second admin entry for the
already-registered `User`; the proxy is display-only and its queryset is irrelevant (we override
the whole view). A no-op default queryset keeps the changelist cheap.

**D2 — Compute the funnel, don't log it (Phase 0).**
`CreatorFunnelService` in `survey/funnel.py` runs the baseline aggregations:
- *Real registrations* = `auth_user` excluding `is_staff`/`is_superuser` (bot rows already purged;
  a hook is left to also exclude AbuseEvent-flagged users if that linkage is added later).
- Cohort = `date_trunc('month', date_joined)`.
- Stages via `EXISTS`/`LEFT JOIN` on `SurveyHeader.created_by_id` (created; published =
  `status IN ('published','closed','archived')`), question presence
  (`SurveyHeader→SurveySection→Question`), and non-deleted `SurveySession` counts (≥1/≥5/≥10).
Returns plain dicts/lists; no ORM objects leak to the template.
Rationale: correctness is trivially checkable against the known 2026-07-04 numbers, and there is
nothing to backfill. *Alternative* (event log) rejected as over-engineering for derivable stages.

**D3 — Signup attribution as a separate 1:1 model (Phase 1), not columns on `auth_user`.**
`SignupAttribution(user OneToOne, raw_referrer, source_bucket, utm_source, utm_medium,
utm_campaign, created_at)`. Rationale: keeps `auth_user` untouched (we don't own that table's
migrations cleanly), nullable-by-construction (absence = unknown source), and easy to drop if the
experiment ends. *Alternative:* a `UserProfile` grab-bag — rejected, no other need for one yet.

**D4 — Capture on the register flow, persist on success.**
On landing/register GET, call `store_utm_in_session(request)` (reused) and also stash the
classified referrer bucket in the session. On successful registration, create the
`SignupAttribution` row for the new user from the session values, then clear them. Hook point:
override the registration success path (`register()` / form_valid) rather than touching abuse
`dispatch()`. Fail-open: attribution capture is wrapped so it can never block or fail a signup
(mirrors `emit_event`'s swallow-all posture).

**D5 — Charts: one static Chart.js include or CSS bars.** No CDN dependency required; a stacked
bar per cohort + a weekly line is enough. Keep the template self-contained.

## Risks / Trade-offs

- **[Aggregation cost grows with table size]** → queries are indexed on FKs and `date_joined`;
  at current scale (hundreds of users, thousands of sessions) it's sub-second. If it ever slows,
  cache the service result for N minutes (staff-only page, staleness is fine). No premature cache.
- **[Proxy-model admin is a slightly unusual pattern]** → documented inline; it's a well-known
  Django idiom (proxy + `change_list_template`). Add a one-line comment pointing at this design.
- **[Referrer is often stripped]** (privacy browsers, direct nav) → "Direct/Unknown" bucket is
  expected and honest; UTM tags on our own outreach links fill the gap where it matters.
- **[Attribution only from ship date]** → no retro-active source data (referrer isn't stored
  historically). Documented as a known limitation; the cohort funnel (Phase 0) *is* retro-active,
  so only the source dimension starts empty.
- **[Double-counting duplicate accounts]** → the baseline noted duplicate accounts of one person.
  Phase 0 reports raw real-registration counts; de-dup is out of scope (tracked separately in
  improvement-account-dedup-signup-ux). Flagged so the number isn't over-read.

## Migration Plan

- **Phase 0**: only a metadata-only migration for the `FunnelReport` proxy model (creates a
  ContentType + permissions, performs no DDL, no table). Ship `funnel.py` + admin proxy + template.
  Rollback = remove the admin registration + proxy; nothing data-bearing to revert.
- **Phase 1**: one additive migration creating `SignupAttribution` (nullable, no backfill).
  Deploy is forward-only and safe (new table, new session writes, wrapped fail-open). Rollback =
  drop the table + revert the capture hook; the dashboard degrades to Phase 0 (no source column).

## Open Questions

- Should Phase 0 and Phase 1 be one PR or two? Recommend two (dashboard first, measured baseline
  live within days; attribution follows). Tasks are grouped to allow either.
- Do we want the AbuseEvent-flagged-user exclusion wired now, or is staff/superuser exclusion
  enough given bots are already purged? Default: staff/superuser only, leave a documented hook.
- Weekly digest to Discord (`scripts/notify_discord.sh`) — in scope here or a follow-up? Lean
  follow-up; the service layer makes it a thin cron consumer later.
