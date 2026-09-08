## Context

Two analytics systems coexist and must stay separate (see `product-analytics` spec): PostHog
measures *us* (creators), `SurveyEvent` measures *customers' respondents* on their behalf. This
change touches only the PostHog side and the creator-facing funnel, plus one respondent-facing
surface (the results page badge) that sends nothing to PostHog.

Current state, measured 2026-09-08 against production:

- `SignupAttribution` has 114 rows since 2026-07-05. 36 carry `raw_referrer = mapsurvey.org` in
  bucket `other` — `persist_signup_attribution` falls back to the current request's referrer (the
  internal hop to `/register/`) when the session holds nothing. ChatGPT arrives as referrer
  `chatgpt.com` (11) and/or `utm_source=chatgpt.com` (8) and lands in `other`; DuckDuckGo, Brave,
  Yahoo, Ecosia likewise. None of it reaches PostHog: `creator_registered` is server-side with only
  `timestamp_source`, and the browser's `$set_once` initial props never land on the person (65/65
  `None` over 30 days).
- `survey_first_response` fires on the first `SurveySession` of a survey regardless of who opened
  it. Median publish→first response is 21 minutes and conversion is ~100%: the author's own check.
- Plausible loads on every page including `/surveys/`, fires three respondent-flow events, and is
  the source of the "Landing visits" stage. The owner is cancelling it for cost.
- GSC and Bing became native PostHog warehouse sources on 2026-09-08 (dashboard AARRR, id 941308).
  Our own `sync_acquisition_metrics` cron was configured the same day and is now redundant.

## Goals / Non-Goals

**Goals:**
- Every registered creator in PostHog carries a first-touch source that survives a week-long gap
  between first visit and signup, and existing rows are backfilled with the same properties.
- `survey_first_response` means an external respondent answered.
- The step between "published" and "answered" is observable (share/QR/embed/responses/export).
- Plausible and the home-grown acquisition sync are gone; the trust page tells the truth again.
- The badge loop also covers the public results page.

**Non-Goals:**
- No new PostHog dashboard tiles in this change's code (they are built in PostHog after the first
  live events).
- No revenue instrumentation (pricing page does not exist yet).
- No collaborator-invite events (separate change once the invite flow is redesigned).
- No change to `SurveyEvent` / respondent analytics.
- No consent banner: the first-touch cookie is first-party, holds no identifier, and expires.

## Decisions

**D1. Attribution reaches PostHog as `$set_once` on the server event, not via a Postgres warehouse
source.** `product_events.emit(CREATOR_REGISTERED, user.pk, {'$set_once': {...}})` sets
`first_source_bucket`, `first_referrer_host`, `first_utm_source`, `first_utm_medium`,
`first_utm_campaign`, `first_landing_path`. Backfill: `sync_posthog_person_properties` gains the
same fields via `posthog.set_once(distinct_id, props)` so an existing value is never overwritten.
*Alternative rejected:* syncing `survey_signupattribution` through PostHog's Postgres source. It
would work, but opens production Postgres to an external network, and the same connection could
be pointed at respondent tables by a later "convenience" — the boundary we most want to keep is
easier to keep with nothing to point.

**D2. First-touch lives in a 90-day first-party cookie, set by a small middleware.**
`FirstTouchMiddleware` runs on GET responses for marketing paths only (not `/surveys/`, `/r/`,
`/editor/`, `/admin/`, `/accounts/` except `/accounts/register/`, not static/media). If the cookie
`ms_ft` is absent it writes a signed JSON blob: `{h: referrer_host, b: bucket, s/m/c: utm triple,
p: landing_path, t: unix}` — `SameSite=Lax`, `Secure` when the request is, `HttpOnly`, 90 days.
The referrer is recorded only when its host is not ours. `persist_signup_attribution` reads the
cookie first, then the legacy session keys (transition), then classifies. The internal-referrer
fallback (`request.META['HTTP_REFERER']` at persist time) is deleted.
*Alternatives:* keep the session (dies on browser restart, and ChatGPT/search discovery to signup
has a multi-day median); a `localStorage` write from `_analytics.html` (never runs for blockers,
which our audience uses). A cookie is the only store that survives both.

**D3. Classifier gains `ai` and `search_other`; UTM can promote a direct visit to `ai`.**
`_REFERRER_BUCKETS['ai'] = [chatgpt.com, chat.openai.com, perplexity.ai, gemini.google.com,
claude.ai, copilot.microsoft.com, you.com, phind.com]`, `['search_other'] = [duckduckgo.com,
search.brave.com, yahoo.com, ecosia.org, startpage.com, yandex.ru, yandex.com]`. When the bucket
is `direct` or `other` and `utm_source` matches `chatgpt.com|openai|perplexity|gemini|claude`,
the bucket becomes `ai`. `google.com` keeps `google`; `bing.com` keeps `bing`. Order of the dict
matters (first match wins); `email` stays before `social`.

**D4. `SurveySession.opened_by_kind` records the opener's relation; the signal filters on it.**
New `CharField(max_length=12, default='external')` with values `external`, `owner`,
`collaborator`, `preview`. Set at the three creation sites: `preview` where
`tags=['editor-preview']`; `owner` when `request.user` is authenticated and equals
`survey.created_by`; `collaborator` when a `SurveyCollaborator` row links them; `external`
otherwise (anonymous included). `emit_first_response_event` fires only for a session whose kind is
`external`, and only when no earlier non-deleted `external` session exists for the survey. The
event carries `respondent_kind='external'`. Historic rows keep the default `external`; the
backfilled history stays as it was and is labelled by the existing `timestamp_source` so insights
can start the honest series at the ship date.
*Alternative rejected:* inferring the author by IP or user agent — unreliable and it inspects the
respondent, which the boundary forbids.

**D5. Distribution events: server-side where a view exists, client-side for clipboard actions.**
`responses_viewed` in the editor responses view (GET, once per request), `data_exported` in
`download_data` and `export_survey` (property `format`), all through `product_events.emit`.
`share_link_copied`, `qr_shown`, `embed_copied` are browser captures guarded by
`window.posthog && posthog.capture` (same pattern and the same silence-when-blocked guarantee as
`ai_empty_intercept`). Properties: `survey_id`, `surface`. Never a URL with a slug, never a
respondent count.

**D6. Badge on `/r/<slug>/` reuses the existing partial** with `medium="results"`, rendered under
the page content for every survey (the `show_branding` flag stays unhonoured, as on the other two
surfaces). The link is `/accounts/register/?utm_source=viral_loop&utm_medium=results` — no slug,
no id — so a registration can be attributed to the loop without being attributable to a survey.

**D7. Plausible and the acquisition sync are removed in one PR; the DROP migration ships with it.**
The two tables are read only by the staff funnel dashboard. During Render's instance overlap the
old instance could render that page against dropped tables for a few seconds; the page is
staff-only and the failure is a 500 on one admin URL, so a two-PR dance is not worth it. Render
resources are deleted by hand afterwards (Blueprint sync never deletes): cron
`mapsurvey-acquisition-sync` and its `GSC_SERVICE_ACCOUNT_JSON`; `PLAUSIBLE_SCRIPT_URL` on the web
service. `DemoOpen` and `record_demo_open` stay — they are unrelated to the providers.

**D8. The Django funnel dashboard keeps what only our database can answer.** Registrations-by-
source (from `SignupAttribution`, now with the new buckets) and demo opens stay; the acquisition
block, channel breakdown and freshness panel are replaced by one card linking to the PostHog AARRR
dashboard with a one-line explanation of what lives there.

**D9. Trust page.** The Data Privacy section says respondent pages load no third-party analytics
scripts at all, and names PostHog as the only analytics on creator-facing pages. The DPA is built
from the HTML source (see `lesson-trust-page-claims`), so it is regenerated in the same PR.

## Risks / Trade-offs

- [`$set_once` silently keeps a wrong value once written] → the backfill runs *after* the
  classifier fix and re-classifies from `raw_referrer`, and a `--reclassify` option rewrites the
  36 spoiled `SignupAttribution` rows first; nothing is sent to PostHog before the rows are right.
- [Cookie read as "tracking" by a privacy-minded creator] → no identifier inside, 90-day expiry,
  `HttpOnly`, mentioned on `/trust/` as first-party attribution.
- [Owner opening the survey from a private window is counted external] → accepted; that is a
  genuine anonymous session and indistinguishable from a respondent by design.
- [Backfilled `survey_first_response` history stays inflated] → the ship date is annotated in
  PostHog; insight descriptions already say so. Rewriting history would need respondent data we
  do not have.
- [Losing Plausible's pre-August landing series] → owner exports CSV from Plausible before
  cancelling; kept under `docs/marketing/` as a static record, not re-imported anywhere.
- [Dropping tables while an old instance still serves the funnel page] → staff-only page, seconds
  of overlap, acceptable (D7).
- [Client-side captures never fire for creators with blockers] → same limitation as every browser
  event we already have; the server-side pair (`responses_viewed`, `data_exported`) is unaffected.

## Migration Plan

1. Deploy code (migration adds `opened_by_kind`, drops the two acquisition tables).
2. Run `manage.py sync_posthog_person_properties --reclassify` once (repairs rows, sends
   `set_once` for all existing creators).
3. Delete Render cron `mapsurvey-acquisition-sync` and the web service's `PLAUSIBLE_SCRIPT_URL`;
   owner exports Plausible history and cancels the subscription.
4. In PostHog: annotate the ship date on the AARRR dashboard; add tiles "registrations by
   `first_source_bucket` → published" and the distribution events once data arrives.

Rollback: revert the PR. The `opened_by_kind` column is additive; the dropped tables come back
empty via the reversed migration and would need a re-run of the (deleted) sync — acceptable, since
the same numbers live in PostHog's GSC source.

## Open Questions

- None blocking. Whether to honour `show_branding` on the results page for a future paid tier is
  deferred to the pricing change.
