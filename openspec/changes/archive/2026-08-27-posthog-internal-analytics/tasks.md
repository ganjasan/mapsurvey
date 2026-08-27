# Tasks — stage 1 (base integration)

## 1. Settings

- [x] 1.1 Add to `mapsurvey/settings.py`, next to the Plausible block: `POSTHOG_PROJECT_KEY`
      (env, default `''`), `POSTHOG_API_HOST` (env, default `https://eu.i.posthog.com`).
- [x] 1.2 Add `POSTHOG_EXCLUDED_PREFIXES = ('/surveys/', '/r/')` with the comment explaining *why*
      those two are excluded — third-party audiences, and the guarantee behind `/trust/` line 95 —
      mirroring the note already written for `ACQUISITION_NON_MARKETING_PREFIXES`.

## 2. Context processor

- [x] 2.1 In `survey.context_processors.analytics`, return `POSTHOG_PROJECT_KEY` as `''` when
      `request.path` starts with any excluded prefix, and `POSTHOG_API_HOST` alongside it.
- [x] 2.2 Return `POSTHOG_PERSON` — `None` for anonymous, otherwise a dict of
      `distinct_id`/`email`/`username`/`date_joined` — so the template does no attribute walking.

## 3. Template

- [x] 3.1 Extend `survey/templates/partials/_analytics.html` with a `{% if POSTHOG_PROJECT_KEY %}`
      block holding the official snippet: `api_host` from context, `autocapture: true`,
      `disable_session_recording: true`, `person_profiles: 'identified_only'`.
- [x] 3.2 Emit the identify call only when `POSTHOG_PERSON` is present. Every interpolated value
      goes through `json_script` — never bare `{{ }}` inside a script literal.
- [x] 3.3 Touch no base template. All four heads already include the partial; the gate is the
      context. Adding a second partial would encode the privacy boundary as an omission.

## 4. Trust page and DPA (needs sign-off before merge)

Scope grew here on purpose. Adding a tracker to `/trust/` meant reading its claims closely, and
several were already false — independently of PostHog. Shipping a truthful tracker disclosure next to
untrue neighbouring claims would have been worse than not touching the page.

- [x] 4.1 `survey/templates/trust.html` line 37 — scope "No cookies used for tracking or analytics"
      to respondents.
- [x] 4.2 Line 40 — scope "No third-party trackers" to respondents, and add a bullet disclosing that
      creator-facing pages (landings, editor, account) use product analytics hosted in the EU.
- [x] 4.3 Leave line 95 alone — "no third-party scripts in the survey-taking flow". Verified during
      implementation to be **already inaccurate**: Plausible loads there and fires `survey_start`,
      `survey_section_complete` and `survey_complete`, and the pages pull Leaflet/FontAwesome/
      Bootstrap from public CDNs. Not this change's to fix; see the proposal for the two branches.
- [x] 4.4 Hosting section rewritten. Verified via the Render API that the web service, Celery worker,
      both cron jobs **and the `mapsurvey-db` database** are all `region: oregon`. "Frankfurt,
      Germany (EU)" and "no cross-border transfers outside the EEA" replaced with "Oregon, United
      States" and an explicit statement that data is transferred outside the EEA. Self-hosting
      reframed from a bonus into the answer for EU-residency requirements.
- [x] 4.5 Removed the Content Security Policy claim — there is no CSP header and no `django-csp`
      dependency. Replaced with the registration abuse defenses, which do exist.
- [x] 4.6 "Deleting your account removes all surveys, responses and personal information" — there is
      no self-serve account deletion view or URL. Changed to deletion on request, with the contact
      address. Survey deletion described as soft-delete plus scheduled purge, which is what the
      `mapsurvey-purge-trash` cron actually does.
- [x] 4.7 "Collects no personal data from people filling out surveys" — `SurveyEvent.metadata` stores
      the respondent's user-agent (512 chars) and raw referrer per session. Disclosed instead of
      denied.

## 4b. DPA template (`survey/assets/dpa/mapsurvey-dpa.pdf`)

The signable document was worse than the page, and is what a DPO actually reads.

- [x] 4b.1 **Root cause first:** the PDF had no source in the repository — only a binary. That is how
      it kept asserting EU hosting: nobody could diff it, and fixing a sentence meant regenerating a
      binary by hand. Added `survey/assets/dpa/mapsurvey-dpa.html` as the source and
      `scripts/build_dpa.sh` (weasyprint) to render it. Edit HTML, run the script, commit both.
- [x] 4b.2 §5.4 sub-processor table said "Render Services, Inc. — Frankfurt, Germany (EU)". Corrected
      to Oregon, United States.
- [x] 4b.3 §5.4 listed Render only. Added the sub-processors actually in use, each verified rather
      than assumed: **Cloudflare** (`server: cloudflare` + `cf-ray` on mapsurvey.org, plus Turnstile),
      **Mapbox** (tiles fetched by the respondent's browser), **Plausible** (live in production —
      `plausible.io/js/pa-lwntAkTnmyk5UaA7Vjaw4.js`), **PostHog EU** (creator pages), **Namecheap
      Private Email** (`EMAIL_HOST=mail.privateemail.com`). `USE_S3` is unset, so no AWS entry.
      Added a paragraph covering the public CDNs that receive respondent IPs.
- [x] 4b.4 §4 technical data corrected: user-agent, referring page and UTM parameters are stored per
      session. The note no longer claims no personal identifiers are collected from respondents.
- [x] 4b.5 New §5.5 International Transfers — states plainly that using the hosted service transfers
      personal data outside the EEA, that no EU-region hosted deployment exists yet, and that
      self-hosting is the route for controllers who cannot accept that.
- [x] 4b.6 §2 now scopes the DPA to the hosted service, since a self-hosting controller has no
      processor relationship at all.
- [x] 4b.7 Version bumped 1.0 → 1.1; processor contact aligned to `konuchovartem@mapsurvey.org`
      (was `info@mapsurvey.org`).
- [x] 4b.8 §8 governing law: German law and exclusive jurisdiction of the Berlin courts, while the
      Processor is an individual operating from Kyrgyzstan. Not a deliberate choice by anyone — and
      the wider problem is that a signable Article 28 agreement was being handed out without legal
      review at all.
- [x] 4b.9 **The template is withdrawn.** `/trust/` now offers to agree a DPA on request instead of
      serving a PDF. The files moved from `survey/assets/dpa/` to `docs/legal/`, so `collectstatic`
      can no longer publish them — unlinking alone would have left the old URL alive in every email
      that ever contained it. Verified: the old path returns **404**.
- [x] 4b.10 The HTML source carries a visible "DRAFT — PENDING LEGAL REVIEW" banner and a comment
      listing the open questions: governing law, whether the processor should be a natural person at
      all given personal liability, whether SCCs must be annexed now that §5.5 admits US transfers,
      and whether the breach/DSR timelines are ones a one-person operation can meet.
- [x] 4b.11 Carried out of this change rather than done here. The DPA template was withdrawn:
      `survey/assets/dpa/` no longer exists and `/trust/` offers to agree one on request, with a
      test asserting the page does not distribute it. The legal review that must happen before
      anything is offered for signature again now lives on backlog #88 (DPA / AVV compliance
      pack), where the rest of that work already sits.

## 5. Configuration surfaces

- [x] 5.1 Document both variables in `.env.example` under `# --- Internal product analytics
      (PostHog) ---`, following the existing convention of commented-out keys plus an explanation of
      what unset means.
- [x] 5.2 Add `POSTHOG_PROJECT_KEY` and `POSTHOG_API_HOST` to the `mapsurvey` web service in
      `render.yaml` as `sync: false`. Not on the Celery worker or the acquisition cron — neither
      renders a page. (Stage 3 revisits the worker for server-side error capture.)
- [x] 5.3 `CLAUDE.md`: note the tracker next to the acquisition-metrics paragraph — what it covers,
      that respondent pages are deliberately excluded, that Plausible still runs, and above all that
      `SurveyEvent`/Performance/UTM are a *different system* that PostHog must never absorb.

## 6. Tests (`survey/tests.py`, GIVEN/WHEN/THEN)

- [x] 6.1 `PostHogSnippetTest`: unset key renders nothing on the landing page; set key renders the
      snippet with that key and host; a non-default `POSTHOG_API_HOST` reaches the snippet.
- [x] 6.2 Exclusion: with the key set, a real respondent URL under `/surveys/` and a real `/r/` URL
      render no snippet, while landing, editor and account pages do. Assert against genuinely routed
      URLs, not synthetic paths — that is what makes a future route move fail loudly.
- [x] 6.3 Co-existence: with both trackers configured, a respondent page still renders Plausible and
      not PostHog.
- [x] 6.4 Identify: authenticated request carries `distinct_id` = user pk plus the three person
      properties; anonymous request has no identify call and no email in the body.
- [x] 6.5 Escaping: a username containing `</script>` and a quote does not break the script block.
- [x] 6.6 Place the new class next to the existing Plausible tests (`survey/tests.py`, ~line 9860).

## 7. Verification

- [x] 7.1 `./run_tests.sh survey` — 1067 tests, OK (1 skipped), no regressions. The 20 new tests
      account for the whole delta against the 1047 recorded by the previous change.
- [x] 7.2 Manual check with `run_dev.sh` against the real Cloud EU project (248938), verified both
      in the browser and by querying the ingested events back out of PostHog:
      - `/trust/` loads `array.js`, `config.js`, `surveys.js`, `web-vitals.js` from
        `eu-assets.i.posthog.com`; `POST https://eu.i.posthog.com/i/v0/e/` returns **200**.
      - Effective config confirmed live on posthog-js **1.417.1**: `capture_pageview: true`,
        `capture_pageleave: "if_capture_pageview"`, `autocapture: true`,
        `person_profiles: "identified_only"`, `disable_session_recording: true`.
      - `$pageview`, `$autocapture` and `$web_vitals` all arrive, each carrying the `/trust/` URL.
      - `/surveys/<uuid>/section1/`: `window.posthog` is `undefined`, no PostHog script tags, the
        key is absent from the HTML — and **no event in the project carries a `/surveys/` URL**.
        Asserted by querying `events` directly, not by reading markup.
      - `/editor/` while signed in renders the identify payload
        `{"distinct_id": "1", "email": …, "username": …, "date_joined": …}`.

      **Measurement gotcha, recorded so it is not re-diagnosed as a bug:** a first pass showed
      `$pageleave` arriving but no `$pageview`, which looks exactly like a broken config. It was the
      check that was wrong, not the code — `$pageleave` is sent via `sendBeacon` on unload while
      `$pageview` sits in the normal batch queue, so navigating between pages within a second or two
      loses the queued events. Stay on the page ~10s before asserting.

## 8. Rollout

- [x] 8.1 Merge with the key unset — safe by construction, nothing is emitted.
- [x] 8.2 Set `POSTHOG_PROJECT_KEY` on the `mapsurvey` service in Render only after the `/trust/`
      wording is signed off (task 4).
- [x] 8.3 Confirm events arrive and that **no** event carries a `/surveys/` or `/r/` path.
      Verified 2026-08-27 against production: 2938 `$pageview` events over 30 days, none of them
      on a `/surveys/` or `/r/` path.
- [x] 8.4 Let it run alongside Plausible; record how the two pageview series relate. That comparison
      is the entry condition for stage 4. Outcome: the two series are not directly comparable —
      Plausible's script also loads on `/surveys/`, so roughly half its entries are customers'
      respondents, while PostHog deliberately excludes them. Stage 4 (`posthog-replaces-plausible`)
      therefore cannot be a straight swap and stays a separate change; see section 9.

## 9. Follow-up stages (separate changes — not done here)

- [ ] 9.1 `posthog-activation-funnel` — named events for register → survey created → question added
      → published → first response, carrying `creation_method` so the AI generator's path is
      distinguishable. Blocks the "how did AI onboarding change the funnel" question.
- [ ] 9.2 `posthog-error-tracking` — `posthog-js` exception autocapture plus `posthog-python` wired
      into `LOGGING`. Net-new; the only stage that needs the server-side SDK.
- [ ] 9.3 `posthog-replaces-plausible` — repoint the `plausible` source of
      `sync_acquisition_metrics`, drop `PLAUSIBLE_*`, remove the script. Gated on 8.4. GSC untouched.
