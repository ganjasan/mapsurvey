## Why

The "Book a 30-min call" CTA (Cal.com) is the only way a visitor can talk to us before registering, and it does not convert: in the last 60 days the landing page had 689 visitors, the booking buttons were clicked 3 times across all surfaces, and Cal.com has never recorded a booking. Picking a time slot and committing to a 30-minute call is too high a bar for a first contact. Notion's pattern — "Get X free" plus "Request a demo", where the demo request starts with nothing but an email — turns the same intent into a lead we can answer at our own pace. Issue #288.

## What Changes

- Hero primary button becomes **"Get Mapsurvey free"** (was "Create your Mapsurvey"); the same label on the "Build it yourself" card.
- Hero secondary button becomes **"Request a demo"** and leads to a new on-site page `/demo/`, in the same tab. No calendar.
- New two-step demo request at `/demo/`:
  - **Step 1 — email only.** Submitting it creates a `DemoRequest` row, emails `CONTACT_EMAIL`, emits a PostHog `demo_requested` event (`stage=email`). The lead exists from this moment, even if the visitor leaves.
  - **Step 2 — details** (name, organisation, what they plan to map, when). Submitting updates the same row, sends a second notification, emits `demo_requested` with `stage=details`. The step can be skipped.
- Every surface that linked to the booking page now links to `/demo/?src=<surface>`: hero, "How to start" ("Build it with us" card), `/services/` (both buttons), `/for-educators/`, the footer "Connect" column. The source is stored on the row so conversion by surface is measurable without client-side JavaScript.
- **BREAKING (configuration)**: the `BOOK_A_CALL_URL` setting, its context-processor key and the `book_call_clicked` click listener are removed. The Cal.com link lives only in our hand-written replies.
- Abuse defences reuse `survey/abuse.py`: honeypot field on both steps, per-IP rate limit on step 1 (`DEMO_REQUEST_LIMIT_HOUR` / `DEMO_REQUEST_LIMIT_DAY`), hits logged as `AbuseEvent`s. No Turnstile — a spam row costs us nothing, a CAPTCHA costs a lead.
- Requests are listed read-only in the Django admin.
- **Footer redesign after Notion's**: light background, brand + a short quote on the left, then five short columns with sentence-case titles — *Product*, *Mapsurvey for*, *Use cases*, *Resources*, *Company*. Every internal link the current footer carries stays (SEO internal linking and existing tests depend on them); they are regrouped instead of stacked in one 18-item "Product" list. "Request a demo" sits in *Product*. Language switch, licence and copyright move to a bottom row.
- Russian translations for every new or changed marketing string, so `/ru/` stays complete.

## Capabilities

### New Capabilities
- `demo-request`: the two-step `/demo/` form, the `DemoRequest` record, staff email notifications, the `demo_requested` analytics event, admin listing and abuse defences.

### Modified Capabilities
- `landing-page`: hero and "How to start" button labels and targets; footer structure and look; every marketing surface points at `/demo/` instead of `BOOK_A_CALL_URL`; the "Book-a-call target from configuration" requirement is removed.

## Impact

- **Code**: `survey/models.py` (+ migration), new `survey/demo_request.py` (form, limits, event, notification task), `survey/views.py`, `survey/urls.py`, `survey/admin.py`, `survey/abuse.py` (generic limit helpers extracted from the registration ones), `survey/tasks.py`, `survey/context_processors.py`, `mapsurvey/settings.py`.
- **Templates**: new `demo.html`, `demo_request/notify.{txt,html}`; edited `landing.html`, `services.html`, `for_educators.html`, `base_landing.html` (footer rewritten); `landing.css` for the form and the new footer.
- **i18n**: `survey/locale/ru/LC_MESSAGES/django.po` + compiled `.mo`.
- **Tests**: `LandingTwoPathsTest`, `ServicesPageTest` updated; new `DemoRequestTest`.
- **Config**: `BOOK_A_CALL_URL` env var on Render becomes inert (can be deleted later); two optional new env vars with sane defaults.
- **Analytics**: `book_call_clicked` stops arriving; `demo_requested` starts. The GTM daily skill and the AARRR dashboard are unaffected (neither reads `book_call_clicked`).
