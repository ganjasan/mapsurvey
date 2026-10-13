## 1. Model, abuse helpers, settings

- [x] 1.1 `DemoRequest` model in `survey/models.py` (`created_at`, `key` UUID unique, `email`, `source`, `name`, `organisation`, `project`, `timeline`, `details_at`, `user`) + migration
- [x] 1.2 `survey/abuse.py`: generic `check_limits(request, limits)` / `increment_limits(request, limits)`; registration helpers delegate to them; `demo_request_limits()` reading `DEMO_REQUEST_LIMIT_HOUR` / `DEMO_REQUEST_LIMIT_DAY`
- [x] 1.3 `mapsurvey/settings.py`: add the two limit settings (5 / 20); remove `BOOK_A_CALL_URL`; `survey/context_processors.py`: drop the key
- [x] 1.4 Move `_anonymous_distinct_id` to `survey/analytics_ids.py`; `pro_interest.py` imports it

## 2. Form, view, notifications, analytics

- [x] 2.1 `survey/demo_request.py`: `SOURCES`, `TIMELINE_CHOICES`, `DemoEmailForm`, `DemoDetailsForm`, `emit_demo_requested(request, row, stage)`
- [x] 2.2 `survey/tasks.py`: `notify_demo_request(request_id, stage)` rendering `demo_request/notify.{txt,html}` to `CONTACT_EMAIL`; enqueue on commit with inline fallback
- [x] 2.3 Views `demo_request` (`/demo/`) and `demo_request_details` (`/demo/<uuid:key>/`) in `survey/views.py`: honeypot, rate limit on step one, redirect, done state, 7-day expiry, 404 on unknown key; routes in `survey/urls.py`
- [x] 2.4 `survey/admin.py`: read-only `DemoRequestAdmin`

## 3. Templates and copy

- [x] 3.1 `survey/templates/demo.html` (three states: email, details, done) extending `base_landing.html`, `noindex`, honeypot, trust-page link; CSS in `landing.css`
- [x] 3.2 `demo_request/notify.txt` + `.html` with every field and the admin link
- [x] 3.3 `landing.html`: hero "Get Mapsurvey free" + "Request a demo" (`?src=hero`); "How to start" card labels and `?src=how_to_start`; fine print
- [x] 3.4 `services.html` (both buttons, `?src=services`), `for_educators.html` (`?src=educators`), `base_landing.html` footer (`?src=footer`) and remove the `book_call_clicked` listener
- [x] 3.5 Footer after Notion's in `base_landing.html`: brand + Jacobs quote, five columns (Product / Mapsurvey for / Use cases / Resources / Company), bottom row with languages, licence, ©; light styles and breakpoints in `landing.css`; keep every existing internal `href`
- [x] 3.6 `survey/locale/ru/LC_MESSAGES/django.po`: translations for every new/changed string; `compilemessages -l ru`

## 4. Tests and verification

- [x] 4.1 Update `LandingTwoPathsTest` and `ServicesPageTest` to the new labels/targets and the absence of `cal.com`; new `LandingFooterTest` for the five columns, the quote (EN + RU) and the demo link
- [x] 4.2 New `DemoRequestTest`: step one creates row + redirect, source normalisation, step two updates, skip, done/expired/404, pre-filled email for signed-in user, notification subjects (locmem mail), event emission with mocked posthog, honeypot, 429 on limit, registration limits unchanged
- [x] 4.3 `./run_tests.sh survey.tests.DemoRequestTest survey.tests.LandingTwoPathsTest survey.tests.ServicesPageTest survey.tests.RegistrationRateLimitTest` (or the matching class names) green; full `survey` run once at the end
- [x] 4.4 Render `/`, `/ru/`, `/demo/` locally and check the hero, both steps and the footer at 1280px and 360px
