## 1. Attribution capture and classifier

- [ ] 1.1 Extend `_REFERRER_BUCKETS` in `survey/events.py` with `ai` and `search_other`; add UTM-based promotion to `ai` (`utm_source` matching chatgpt.com/openai/perplexity/gemini/claude) in a `classify_source(referrer, utm)` helper used by both capture and reclassify
- [ ] 1.2 Add `FirstTouchMiddleware` (`survey/middleware.py`): marketing paths only, writes signed `ms_ft` cookie (90 days, HttpOnly, SameSite=Lax) with referrer host, bucket, UTM triple, landing path; never records the site's own host; never sets on `/surveys/`, `/r/`, `/editor/`, `/admin/`
- [ ] 1.3 Rewrite `persist_signup_attribution`: cookie first, legacy session second, no fallback to the current request's referrer; store `landing_path` (new nullable field on `SignupAttribution`, migration)
- [ ] 1.4 Tests (GIVEN/WHEN/THEN): AI referrer, AI via UTM only, DuckDuckGo, Google/Bing unchanged, internal hop never recorded, first touch survives cookie-only visit, respondent paths set no cookie

## 2. Attribution to PostHog

- [ ] 2.1 In `signals.py` `emit_registration_event`: read the user's `SignupAttribution` and pass `$set_once` with `first_source_bucket`, `first_referrer_host`, `first_utm_source`, `first_utm_medium`, `first_utm_campaign`, `first_landing_path` (no raw URL); fail-open
- [ ] 2.2 `sync_posthog_person_properties`: add the six first-touch properties via `posthog.set_once`; add `--reclassify` that recomputes `source_bucket` from `raw_referrer` + UTM with the new classifier (own host → `direct`) and saves the rows before sending
- [ ] 2.3 Tests: event payload contains `$set_once` and no raw referrer; reclassify repairs an internal-referrer row; PostHog disabled is a no-op

## 3. First response means an external respondent

- [ ] 3.1 Add `SurveySession.opened_by_kind` (`external|owner|collaborator|preview`, default `external`) + migration
- [ ] 3.2 Set the kind at the three creation sites in `survey/views.py` (language-select, section entry, editor preview) via one helper `session_kind_for(request, survey)` using `created_by` and `SurveyCollaborator`
- [ ] 3.3 Rewrite `emit_first_response_event`: fire only for kind `external`, only when no earlier non-deleted external session exists, add `respondent_kind='external'`
- [ ] 3.4 Tests: owner test then respondent → one event at the respondent; second respondent → none; preview never counts; payload unchanged apart from `respondent_kind`

## 4. Distribution and return events

- [ ] 4.1 Add constants to `product_events.py`: `SHARE_LINK_COPIED`, `QR_SHOWN`, `EMBED_COPIED`, `RESPONSES_VIEWED`, `DATA_EXPORTED`
- [ ] 4.2 Server-side: `pe.emit(RESPONSES_VIEWED)` in the editor responses view; `pe.emit(DATA_EXPORTED, format=…)` in `download_data` and `export_survey`
- [ ] 4.3 Client-side: guarded `posthog.capture` on copy-link, QR and embed controls in the editor share UI with `survey_id` and `surface`; no slug/URL in properties
- [ ] 4.4 Tests: server events emitted once per request with `survey_id`; template renders the guard `window.posthog && posthog.capture`; responses served unchanged when PostHog is disabled

## 5. Badge on the public results page

- [ ] 5.1 Include `partials/_made_with_mapsurvey.html` with `medium="results"` in `public_results.html` below the page content
- [ ] 5.2 Test: `/r/<slug>/` contains the badge with `utm_source=viral_loop&utm_medium=results` and the href holds no slug or id

## 6. Remove Plausible

- [ ] 6.1 Delete the Plausible block from `_analytics.html`, the three `plausible(...)` calls in `base_survey_template.html` and `survey_thanks.html`, `PLAUSIBLE_SCRIPT_URL` from `settings.py` and `context_processors.py`
- [ ] 6.2 Update `/trust/` Data Privacy section per spec (no third-party analytics on respondent pages, PostHog + first-party attribution cookie on creator pages); regenerate the DPA from the HTML source
- [ ] 6.3 Update tests that asserted the Plausible snippet or the trust wording; add the "respondent pages contain no third-party analytics script" assertion for survey, thanks and results pages

## 7. Retire the acquisition sync

- [ ] 7.1 Delete `survey/acquisition.py`, `management/commands/sync_acquisition_metrics.py`, the `AcquisitionService` acquisition/channel/freshness methods in `funnel.py`, and their tests; keep `DemoOpen` and `record_demo_open`
- [ ] 7.2 Remove `AcquisitionDaily` and `AcquisitionSyncState` models + DROP migration; remove `GSC_*`, `PLAUSIBLE_API_KEY`, `PLAUSIBLE_SITE_ID`, `ACQUISITION_*` settings and `.env.example` entries; drop `google-api-python-client`/`google-auth` from `Pipfile` if nothing else imports them
- [ ] 7.3 Funnel dashboard template: replace the acquisition block, channel breakdown and freshness panel with the link card to PostHog dashboard 941308; keep registrations-by-source (now showing `ai` / `search_other`) and demo opens
- [ ] 7.4 Remove the `mapsurvey-acquisition-sync` cron from `render.yaml`
- [ ] 7.5 Update `CLAUDE.md` (Acquisition metrics section → PostHog warehouse sources; Plausible mention in analytics section), `loadtest/README.md`/docs mentioning Plausible, `openspec/specs/acquisition-metrics-sync` Purpose after archive

## 8. Verification and rollout

- [ ] 8.1 Run the survey suite once before and once after; summarise the delta
- [ ] 8.2 Drive in a browser: register via a landing visit with `?utm_source=test` in a fresh profile, confirm `SignupAttribution` and the `$set_once` payload in PostHog live events; open own published survey then an incognito one, confirm a single `survey_first_response`
- [ ] 8.3 After merge (owner): run `sync_posthog_person_properties --reclassify` against prod; delete Render cron `mapsurvey-acquisition-sync` and `PLAUSIBLE_SCRIPT_URL` on the web service; export Plausible CSV to `docs/marketing/analytics/` and cancel the subscription
- [ ] 8.4 PostHog: annotate the ship date on dashboard 941308; add tiles "registrations by `first_source_bucket` → published" and the distribution events once live data exists
