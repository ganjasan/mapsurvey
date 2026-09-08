## Why

The AARRR review of 2026-09-08 (PostHog dashboard 941308) found that the two acquisition numbers we
show cannot be trusted and one is missing: `survey_first_response` fires on the author's own test
session (median 21 min after publish, ~100% "conversion"), and none of the 114 `SignupAttribution`
rows reach PostHog, so no PostHog insight can answer "which channel brings creators who publish".
Meanwhile Google Search Console and Bing are now native PostHog warehouse sources, which makes our
own GSC/Plausible sync and the Plausible subscription redundant — Plausible is being cancelled for
cost, and 48% of its entries were customers' respondents anyway.

## What Changes

- **Signup attribution reaches PostHog.** `creator_registered` carries the stored first-touch as
  `$set_once` person properties (`first_source_bucket`, `first_referrer_host`, `first_utm_source`,
  `first_utm_medium`, `first_utm_campaign`); `sync_posthog_person_properties` backfills the same
  properties for the 114 existing rows.
- **Attribution capture is fixed.** First-touch lives in a 90-day cookie instead of the session
  (session dies before "saw it in ChatGPT, came back a week later"); an internal referrer
  (`mapsurvey.org`) is never recorded as the source (36 of 114 rows were spoiled this way);
  `_classify_referrer` gains an `ai` bucket (chatgpt.com, perplexity.ai, gemini.google.com,
  claude.ai, copilot.microsoft.com) and a `search_other` bucket (duckduckgo, brave, yahoo, ecosia,
  startpage), and `utm_source=chatgpt.com` counts as `ai` even without a referrer.
- **First response distinguishes the author from the public.** `SurveySession` records whether it
  was opened by the survey's owner/collaborator or by an anonymous respondent; `survey_first_response`
  fires only for the first *external* session and carries `respondent_kind`. Editor-preview sessions
  (`tags=['editor-preview']`) never count.
- **Distribution and return events.** New creator events `share_link_copied`, `qr_shown`,
  `embed_copied`, `responses_viewed`, `data_exported` (with `survey_id`, never respondent data),
  closing the blind spot between "published" and "got answers" and giving Retention a meaningful
  return signal.
- **"Made with Mapsurvey" badge on the public results page** `/r/<slug>/` with
  `utm_source=viral_loop&utm_medium=results`; no survey identifier in the link.
- **BREAKING: Plausible removed.** Snippet and custom events (`survey_start`,
  `survey_section_complete`, `survey_complete`) leave `_analytics.html`, `base_survey_template.html`,
  `survey_thanks.html`; `PLAUSIBLE_*` settings, the Plausible client in `acquisition.py`, the
  "Landing visits" stage and the Plausible sync state go; `/trust/` stops claiming aggregate analytics
  on survey pages (respondent pages will send nothing to any third party).
- **BREAKING: `sync_acquisition_metrics`, `AcquisitionDaily`, `AcquisitionSyncState` and the
  `mapsurvey-acquisition-sync` cron are retired.** Top of funnel (impressions, clicks, landing
  visits, channel mix) is read on the PostHog AARRR dashboard from the native GSC/Bing sources and
  `$pageview`; the Django funnel dashboard's acquisition block becomes a link to it. Demo-open
  recording (`DemoOpen`) is untouched.

## Capabilities

### New Capabilities
- `creator-distribution-events`: PostHog creator events for sharing a survey (link, QR, embed) and
  returning to its data (responses page, export); creator-only, `survey_id` only.
- `made-with-badge`: the "Made with Mapsurvey" acquisition loop on respondent-facing surfaces
  (survey, thanks, public results) with UTM tagging rules and the no-survey-identifier constraint.

### Modified Capabilities
- `signup-attribution`: first-touch persisted in a cookie, internal referrer excluded, new
  `ai`/`search_other` buckets, attribution forwarded to PostHog as `$set_once` with a backfill.
- `creator-funnel-events`: `survey_first_response` counts only external sessions and carries
  `respondent_kind`; `SurveySession` records the opener's relation to the survey.
- `acquisition-metrics-sync`: Search Console and Plausible ingestion, the sync command, the local
  daily store and per-source sync state are REMOVED; only demo-open recording remains.
- `creator-funnel-dashboard`: top-of-funnel block, acquisition stages, channel breakdown and sync
  freshness are REMOVED in favour of a link to the PostHog AARRR dashboard; registrations-by-source
  stays (it reads `SignupAttribution`).
- `product-analytics`: trust page wording updated — no third-party analytics on respondent pages at
  all; Plausible no longer listed.

## Impact

- **Code**: `survey/events.py` (classifier, capture, persistence), `survey/signals.py`,
  `survey/product_events.py`, `survey/models.py` (`SurveySession.opened_by_kind` + migration;
  removal of `AcquisitionDaily`/`AcquisitionSyncState` + migration), `survey/views.py` (session
  creation ×2, download, badge include, trust page), `survey/editor_views.py` (responses, export,
  share events), `survey/funnel.py`, `survey/acquisition.py` (delete), two management commands
  (delete `sync_acquisition_metrics`, extend `sync_posthog_person_properties`), templates
  (`_analytics.html`, `base_survey_template.html`, `survey_thanks.html`, `public_results.html`,
  `trust.html`, funnel dashboard), `mapsurvey/settings.py`, `render.yaml`, `.env.example`,
  `CLAUDE.md`, `loadtest/`/docs mentioning Plausible.
- **Data**: two schema migrations (add column, drop two tables). Drop tables only after the PostHog
  GSC source has run for a week; Plausible history export is a manual step before cancelling.
- **Infra**: Render Blueprint sync never deletes resources — the cron service
  `mapsurvey-acquisition-sync` (crn-d9ljd8jm8hqs738rpkl0) and its `GSC_SERVICE_ACCOUNT_JSON` secret
  must be deleted by hand after merge. `PLAUSIBLE_SCRIPT_URL` env var on the web service becomes
  unused.
- **PostHog**: new person properties and events appear; AARRR dashboard tiles for "registrations by
  channel → publish" and distribution events are added after the first live events (not part of
  this change's code).
- **Privacy boundary unchanged**: every new event is a creator event with `survey_id` only;
  `respondent_kind` says owner/external, nothing about the person.
