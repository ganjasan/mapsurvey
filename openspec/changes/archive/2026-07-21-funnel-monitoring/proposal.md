## Why

Growth is currently flying blind. We can only see the creator acquisition→activation funnel
by running ad-hoc SQL against prod (as done for the 2026-07-04 GTM baseline), and we have
**0% channel attribution** — we cannot tell which source produced a signup. This is the hard
prerequisite of the growth epic ([docs/gtm/gtm-plan-2026-h2.md](../../../docs/gtm/gtm-plan-2026-h2.md) §5):
no channel can be scaled while we cannot measure it. A repeatable, staff-only dashboard that
turns those one-off queries into a standing view — and starts capturing signup source — lets
the weekly review (continue/kill/scale per hypothesis) run in 5 minutes instead of a manual pull.

This is distinct from the existing [survey-event-tracking](../survey-event-tracking/proposal.md)
and [utm-link-generator](../utm-link-generator/proposal.md) changes: those track **respondent
behaviour inside a single published survey** (session → section drop-off → completion, keyed to
`SurveySession`). This change tracks the **creator lifecycle across the whole platform**
(register → create survey → publish → collect responses, keyed to `User`). Different subject,
different audience (founder/staff, not the survey creator).

## What Changes

Delivered in two phases inside one change so the cheap, no-migration dashboard ships first.

**Phase 0 — Creator funnel dashboard (no schema change):**
- A custom Django-admin page (proxy model + `changelist_view` override, staff-only) at
  `/admin/…/funnel/` showing the **monthly cohort activation funnel**: registrations → created
  a survey → added ≥1 question → published → ≥1 / ≥5 / ≥10 responses, per registration-month cohort.
- A **weekly signups** series and the current all-time funnel totals.
- A `CreatorFunnelService` in `survey/analytics.py` (or a new `survey/funnel.py`) holding the
  aggregation queries — the same logic proven in the 2026-07-04 baseline, filtered to real
  registrations (exclude staff/superusers; bot signups already removed).

**Phase 1 — Signup-source attribution:**
- Capture `HTTP_REFERER` + UTM params on the landing/register flow and **persist them onto the
  creator at registration** via a new `SignupAttribution` model (OneToOne → `User`: raw referrer,
  classified source bucket, `utm_source/medium/campaign`, created_at).
- Reuse existing helpers `store_utm_in_session()` and `_classify_referrer()` from `survey/events.py`
  — no duplicated parsing logic.
- Add a **signups-by-source** breakdown table to the dashboard.

## Capabilities

### New Capabilities
- `creator-funnel-dashboard`: Staff-only Django-admin page rendering the platform creator
  acquisition→activation funnel by monthly cohort + weekly signups, backed by a
  `CreatorFunnelService` that aggregates over `auth_user` / `SurveyHeader` / `SurveySession`
  with no schema change. Retro-active — reflects all historical data on first load.
- `signup-attribution`: Capture and persist the acquisition source (referrer bucket + UTM triple)
  of a **creator** at registration into a `SignupAttribution` record, and surface a
  signups-by-source breakdown on the dashboard.

### Modified Capabilities
<!-- None. This change adds new capabilities only. The registration view (registration-abuse-defenses)
     gains a signup-source hook, but that is behaviour owned by the new signup-attribution capability,
     not a change to the abuse-defense requirements. -->

## Impact

- **New files**:
  - `survey/funnel.py` — `CreatorFunnelService` (cohort funnel, weekly signups, source breakdown).
  - `survey/admin_funnel.py` (or extend `survey/admin.py`) — proxy model + `FunnelDashboardAdmin`.
  - `survey/templates/admin/funnel_dashboard.html` — dashboard template (Chart.js or CSS bars).
  - `survey/migrations/00XX_signup_attribution.py` — Phase 1 only.
- **Modified files**:
  - `survey/models.py` — `SignupAttribution` model (Phase 1) + `FunnelReport` proxy model.
  - `survey/admin.py` — register the dashboard proxy admin.
  - `survey/views.py` — persist signup source on registration success (Phase 1).
  - `mapsurvey/urls.py` / landing view — store referrer+UTM in session on landing (Phase 1;
    `store_utm_in_session()` already handles the UTM half).
  - `survey/tests.py` — funnel aggregation tests + attribution-capture tests.
- **Reused, not duplicated**: `store_utm_in_session()`, `_consume_utm_from_session()`,
  `_classify_referrer()` from `survey/events.py`.
- **No dependency added**: charts via a single static Chart.js include or plain CSS bars — no
  PostHog/Mixpanel (per backlog decision).
- **Privacy**: no PII beyond what's already stored; `SignupAttribution` holds referrer/UTM +
  user FK, no IP persisted (IP→country only if ever needed, out of scope here).
