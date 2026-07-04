# Tasks — funnel-monitoring

Phase 0 (groups 1–3) ships with **no migration** and can be a standalone PR.
Phase 1 (groups 4–5) adds attribution and can follow in a second PR.

## 1. CreatorFunnelService (Phase 0)

- [x] 1.1 Create `survey/funnel.py` with `CreatorFunnelService`; define the real-registration base queryset (exclude `is_staff`/`is_superuser`, leave a documented hook for future AbuseEvent-flagged exclusion)
- [x] 1.2 Implement `cohort_funnel()` → list of dicts per `date_trunc('month', date_joined)` cohort with counts: registrations, created, added_question, published (`status in published/closed/archived`), got_1/got_5/got_10 (non-deleted `SurveySession`)
- [x] 1.3 Implement `weekly_signups()` → registrations grouped by `date_trunc('week', date_joined)`
- [x] 1.4 Implement `alltime_totals()` → single-row funnel totals for the header cards
- [x] 1.5 Return plain dicts/lists only (no ORM objects leak to the template)

## 2. Admin dashboard page (Phase 0)

- [x] 2.1 Add `FunnelReport(SurveyHeader)` proxy model (`Meta.proxy=True`, verbose_name "Funnel dashboard") in `survey/models.py` with a one-line comment pointing at design.md D1 (metadata-only migration `0032_funnelreport.py`)
- [x] 2.2 Register `FunnelDashboardAdmin` in `survey/admin.py` with `change_list_template = "admin/funnel_dashboard.html"` and an overridden `changelist_view` injecting service results into `extra_context`; cheap no-op default queryset (`get_queryset().none()`)
- [x] 2.3 Create `survey/templates/admin/funnel_dashboard.html` (extends admin base): cohort funnel table, weekly signups series, all-time totals cards; CSS bars via built-in `widthratio` (no CDN)
- [x] 2.4 Confirm the page inherits admin staff-only auth (non-staff/anon denied) — `has_*_permission` gated on `request.user.is_staff`

## 3. Tests (Phase 0)

- [x] 3.1 `CreatorFunnelService` unit tests (GIVEN/WHEN/THEN): cohort counts, staff/superuser exclusion, published-status gating, deleted-session exclusion, ≥1/≥5/≥10 thresholds
- [x] 3.2 Admin access test: staff sees the page; non-staff and anonymous are denied
- [ ] 3.3 Sanity-check aggregate output shape against the known 2026-07-04 baseline numbers (do on prod after deploy)

## 4. SignupAttribution model + capture (Phase 1)

- [ ] 4.1 Add `SignupAttribution` model (OneToOne→`User`, `raw_referrer`, `source_bucket`, `utm_source/medium/campaign` nullable, `created_at`) in `survey/models.py`
- [ ] 4.2 Create the additive migration (new table, nullable, no backfill)
- [ ] 4.3 On landing/register GET, reuse `store_utm_in_session(request)` and stash the classified referrer bucket (`_classify_referrer`) in the session
- [ ] 4.4 On successful registration, create the `SignupAttribution` row from session values then clear them; wrap in fail-open try/except (mirror `emit_event` posture) so capture never blocks a signup
- [ ] 4.5 Add `source_breakdown()` to `CreatorFunnelService` (group registrations by `source_bucket`, historical rows fall under `direct`/unknown) and render a signups-by-source table on the dashboard

## 5. Tests (Phase 1)

- [ ] 5.1 Capture tests: referrer+UTM present → `SignupAttribution` created with correct bucket/UTM; direct visit → recorded as direct/null
- [ ] 5.2 Fail-open test: persistence error during capture does not fail the registration
- [ ] 5.3 Dashboard test: source breakdown renders and groups pre-attribution users under unknown/direct

## 6. Wrap-up

- [ ] 6.1 Run `./run_tests.sh survey` green (PostGIS container up)
- [ ] 6.2 Update `docs/gtm/gtm-plan-2026-h2.md` §5 to link the shipped dashboard; note Phase 1 attribution start date
- [ ] 6.3 (Optional / follow-up) note the Discord weekly-digest cron as a thin consumer of `CreatorFunnelService`
