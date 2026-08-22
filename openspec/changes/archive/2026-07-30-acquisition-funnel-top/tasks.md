## 1. Data model

- [x] 1.1 Add `AcquisitionDaily` model (`source`, `date`, `segment`, nullable `impressions`,
  `clicks`, `ctr`, `position`, `visitors`, `pageviews`, `synced_at`) with
  `unique_together = (source, date, segment)` and an index on `(source, date)`
- [x] 1.2 Add `AcquisitionSyncState` model (one row per source: `last_attempt_at`,
  `last_success_at`, `last_error`, `is_configured`) with a helper that reports the state as
  `not_configured` / `ok` / `failing`
- [x] 1.3 Add `DemoOpen` model (`session` FK, nullable `user` FK, `created_at`), written only for
  the demo survey
- [x] 1.4 Generate the migration and check the number against other worktree branches before merge
  (`0042_acquisition_metrics`; 0042 free on all branches, sibling worktrees sit at 0036/0037)

## 2. Provider clients

- [x] 2.1 Add `google-api-python-client` and `google-auth` to the dependency manifest
  (`Pipfile`, not `requirements.txt` — the project builds via `pipenv install --system`)
- [x] 2.2 Create `survey/acquisition.py` with a GSC client that reads credentials from
  `GSC_SERVICE_ACCOUNT_JSON` (env, production) falling back to the `GSC_KEY` file path (local dev),
  and returns per-day rows for the whole property and for the marketing page group
- [x] 2.3 Define the marketing page group — **inverted to an exclusion list**
  (`ACQUISITION_NON_MARKETING_PREFIXES`) after checking GSC's real top pages: the app-prefix set is
  stable while marketing landings keep being added, so an allow-list would silently drop each new
  SEO landing. Verified against 90 days of live data; design.md D3 updated
- [x] 2.4 Add a Plausible Stats API client reading `PLAUSIBLE_API_KEY` / `PLAUSIBLE_SITE_ID`,
  returning per-day whole-site visitors/pageviews, landing-page visitors, and a per-channel
  referrer breakdown
- [x] 2.5 Make both clients raise a typed "not configured" condition, distinct from a request
  failure, when their credentials are absent
- [x] 2.6 Refactor `scripts/gsc_report.py` to use the shared client instead of its own auth, so the
  local report and the sync cannot drift apart

## 3. Sync command

- [x] 3.1 Add `survey/management/commands/sync_acquisition_metrics.py` accepting `--days` (default
  7) and `--source gsc|plausible`
- [x] 3.2 Write rows via `update_or_create` on `(source, date, segment)` so re-runs overwrite and
  provider revisions land
- [x] 3.3 Update `AcquisitionSyncState` per source: attempt time always, success time and cleared
  error on success, error message on failure, not-configured when credentials are absent
- [x] 3.4 Isolate sources: one provider failing must not abort the other, and must never delete or
  zero previously stored rows
- [x] 3.5 Exit non-zero when every requested source fails, so a failed cron run is visible
- [x] 3.6 Print a per-source summary (days written, days skipped, failures) for cron log readability

## 4. Demo-open recording

- [x] 4.1 Add a cached resolver from `DEMO_SURVEY_URL` to a `SurveyHeader` (extract the UUID),
  returning `None` for unset, malformed, or dangling URLs
- [x] 4.2 Record a `DemoOpen` on session creation for the demo survey only, capturing
  `request.user` when authenticated; never touch `SurveySession` fields (all three session-creation
  sites in `views.py`; the import-restore path in `serialization.py` is deliberately excluded — a
  restored session is not someone opening the demo)
- [x] 4.3 Make the recording failure-tolerant: an error here must not break the respondent's survey
  session

## 5. Dashboard service layer

- [x] 5.1 Add an acquisition block builder to `survey/funnel.py`: impressions, landing visits,
  registrations, demo opens for the selected window, each with a value-or-unavailable state
- [x] 5.2 Compute step conversions, propagating unavailability instead of substituting zero
- [x] 5.3 Compute demo opens: full-history total from non-deleted demo sessions, plus the
  anonymous/signed-in split from `DemoOpen` with the split's start date
- [x] 5.4 Compute the referrer-channel breakdown for the window, ordered by volume
- [x] 5.5 Expose per-source freshness (last success age, stale flag) to the template
- [x] 5.6 Wire the block into `dashboard_context()` honouring the existing period selector

## 6. Dashboard template

- [x] 6.1 Insert the acquisition section as ② in `admin/funnel_dashboard.html` and renumber the
  sections below it, including the nav links
- [x] 6.2 Render the four stages with conversions, unavailable states with their reason, and the
  demo total plus split with its start date and the resolved survey name
- [x] 6.3 Render the channel breakdown and the per-source freshness line
- [x] 6.4 Add the inline note stating the window, the source of each stage, and that the
  percentages are cross-source ratios rather than tracked paths

## 7. Deployment

- [x] 7.1 Add a `cron` service to `render.yaml` running the sync daily, with the database and
  provider credentials wired in
- [x] 7.2 Add `GSC_SERVICE_ACCOUNT_JSON`, `GSC_SITE`, `PLAUSIBLE_API_KEY`, `PLAUSIBLE_SITE_ID` to
  settings with empty defaults, and to `render.yaml` as `sync: false`. Deliberately scoped to the
  cron service only: the dashboard reads local tables, so the web service needs no provider keys
- [ ] 7.3 Create the Plausible Stats API key in the Plausible account (**manual, user step**; if the
  plan denies API access the client already maps Plausible's 402 to not-configured, so the GSC half
  ships unchanged)
- [ ] 7.4 Set the credentials in the Render environment and run one manual wide-window backfill
  (**manual, user step** — needs the Render dashboard)
- [x] 7.5 Document the env vars and the sync command in `CLAUDE.md`

## 8. Tests

- [x] 8.1 Sync idempotency: same window twice leaves the row count unchanged and stores the second
  run's values
- [x] 8.2 Provider revision overwrites a previously stored day
- [x] 8.3 One provider failing leaves the other's rows and state intact; all-failing exits non-zero
- [x] 8.4 No credentials configured: command completes, writes nothing, both sources report
  not-configured
- [x] 8.5 GSC marketing page group excludes `/surveys/` impressions
- [x] 8.5a Both GSC segments are queried with a page filter (same aggregation mode), and the
  marketing total never exceeds the whole-property total — regression test for design.md D3a, a bug
  found by running the real sync
- [x] 8.6 `DemoOpen` is written for anonymous and authenticated demo sessions, and not for
  non-demo surveys
- [x] 8.7 Unresolvable `DEMO_SURVEY_URL`: session creation still succeeds, no `DemoOpen`, dashboard
  renders the demo stage as not configured
- [x] 8.8 Dashboard renders with no acquisition data at all (fresh install) without error
- [x] 8.9 Unavailable stage renders as unavailable, not zero; dependent conversions do too; a
  genuinely empty synced window renders zero
- [x] 8.10 Acquisition registrations for a window match the cohort funnel's count for that period
- [x] 8.11 Non-staff and anonymous access to the dashboard remains denied

## 9. GTM daily command

- [x] 9.1 Rename `~/.claude/commands/user-outreach.md` to `gtm-daily.md`, updating its title,
  description, and the usage examples that name `/user-outreach` (verified line-by-line that no
  existing content was lost in the move before deleting the old file)
- [x] 9.2 Prepend a metrics-review step: read the acquisition block and the funnel dashboard first
  (impressions, visits, registrations, demo opens, 30d vs previous 30d), then proceed to the
  existing per-user work. New `metrics` mode stops after that step
- [x] 9.3 Include the SQL/commands the review step needs (queries 0, 0b, 0c), and instruct it to
  report a stale or not-configured source rather than reading around it
- [x] 9.4 Update references to `/user-outreach` in project docs (`improvement-signup-anomaly-dashboard`).
  The `lead-followup` skill only references the `docs/marketing/user-outreach/` archive *directory*,
  which keeps its name, so it needs no change. Left the completed `creator-dossiers` change docs
  alone: they record what was done at the time under the old command name
