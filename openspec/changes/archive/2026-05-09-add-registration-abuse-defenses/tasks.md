## 1. Infrastructure and dependencies

- [x] 1.1 Add `django-ratelimit` and `django-redis` to `Pipfile` `[packages]`; install in venv
- [x] 1.2 Verify the locked Django version (4.2.27) supports `django-redis`
- [x] 1.3 Add `CACHES` block to `mapsurvey/settings.py` using `django_redis.cache.RedisCache` with `LOCATION=os.environ["REDIS_URL"]` (fallback `"redis://localhost:6379/1"`); `IGNORE_EXCEPTIONS=True` for graceful degradation
- [x] 1.4 Add `RATELIMIT_FAIL_OPEN = True` to settings (defense-in-depth: in addition we wrap `is_ratelimited()` in try/except in the view to swallow ANY backend exception)
- [x] 1.5 Add `LOGGING` block to settings with one `abuse` parent logger routing to console at WARNING level. Sub-loggers (`abuse.captcha`, `abuse.ratelimit`, `abuse.honeypot`) propagate via Python's logger hierarchy. Note: `disable_existing_loggers=False` keeps Django's own loggers untouched
- [x] 1.6 Add Turnstile env-var settings: `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `CLOUDFLARE_TRUSTED`, `REGISTRATION_RATE_LIMIT_HOUR=3`, `REGISTRATION_RATE_LIMIT_DAY=10`. **Note**: `ABUSE_HONEYPOT_FIELD` setting was dropped during Phase 7 review — the field name `"website"` is now a constant `HONEYPOT_FIELD_NAME` in `survey/abuse.py` (configurability buys nothing real, no collision risk on the upstream form)
- [x] 1.7 Update `.env.example` with new env vars; document Cloudflare's always-pass dev keys
- [x] 1.8 Update `render.yaml`: add `REDIS_URL` (`fromService: type=redis name=mapsurvey-redis property=connectionString`), add `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` with `sync: false`, add `CLOUDFLARE_TRUSTED=True`, `REGISTRATION_RATE_LIMIT_HOUR=3`, `REGISTRATION_RATE_LIMIT_DAY=10`

## 2. Cloudflare IP middleware

- [x] 2.1 Add `CloudflareIPMiddleware` class to `survey/middleware.py` alongside `ActiveOrgMiddleware`. Sets `request.cf_ip` from `HTTP_CF_CONNECTING_IP` when `settings.CLOUDFLARE_TRUSTED` is true; otherwise from `REMOTE_ADDR`. Does NOT modify `request.META["REMOTE_ADDR"]`
- [x] 2.2 Insert `'survey.middleware.CloudflareIPMiddleware'` into `MIDDLEWARE` at position 1 (after `SecurityMiddleware`, before `WhiteNoiseMiddleware`)
- [x] 2.3 Unit test `CloudflareIPMiddlewareTest.test_trusted_environment_uses_cf_connecting_ip` — asserts `request.cf_ip == "5.6.7.8"` when `CLOUDFLARE_TRUSTED=True` and request has `HTTP_CF_CONNECTING_IP: 5.6.7.8`
- [x] 2.4 Unit test `CloudflareIPMiddlewareTest.test_untrusted_environment_falls_back_to_remote_addr`

## 3. AbuseEvent model and helper

- [x] 3.1 Add `AbuseEvent` model to `survey/models.py` with fields: `defense` (CharField, choices, db_index), `ip` (GenericIPAddressField, null=True, blank=True), `user_agent` (TextField, blank=True), `detail` (TextField, blank=True), `created_at` (DateTimeField, auto_now_add, db_index). `Meta.ordering = ['-created_at']`. Choices: `('captcha', 'ratelimit', 'honeypot', 'email_domain')`
- [x] 3.2 Generate migration: `python manage.py makemigrations survey --name abuseevent` → `0031_abuseevent.py`
- [x] 3.3 Verify migration applies cleanly (verified by 614-test suite running on fresh test DB)
- [x] 3.4 Create `survey/abuse.py`. Add `def client_ip(request)` returning `getattr(request, 'cf_ip', None) or request.META.get('REMOTE_ADDR', '')`. Also add `ratelimit_key(group, request)` adapter function for django-ratelimit's `(group, request)` callable signature
- [x] 3.5 In `survey/abuse.py`, add `def log_abuse_event(defense, request, detail="")` that creates one `AbuseEvent` row and emits one log line on `logging.getLogger(f"abuse.{defense}")` at WARNING. Wraps `AbuseEvent.objects.create()` in try/except so a DB outage does NOT propagate (defense response must reach the client even when audit log write fails — Phase 7 fix C3)

## 4. Turnstile siteverify

- [x] 4.1 In `survey/abuse.py`, add `def verify_turnstile(token, remote_ip)` using stdlib `urllib.request.urlopen` against `https://challenges.cloudflare.com/turnstile/v0/siteverify` with a 5-second timeout. **Stdlib chosen over `requests` to avoid adding a dependency**
- [x] 4.2 Function returns `True` only when response JSON has `success: true`; returns `False` on any `URLError`, `TimeoutError`, `OSError`, `ValueError`/`JSONDecodeError`, or non-success response
- [x] 4.3 Function bypasses the API call (returns `True`) when `settings.TURNSTILE_SECRET_KEY` is empty (local dev story)
- [x] 4.4 Unit tests in `VerifyTurnstileTest`: `test_empty_secret_returns_true_without_http_call`, `test_missing_token_returns_false_when_secret_set`, `test_siteverify_success_returns_true`, `test_siteverify_rejection_returns_false`, `test_network_error_fails_closed`

## 5. RegistrationAbuseForm

- [x] 5.1 In `survey/abuse.py`, add `class RegistrationAbuseForm(RegistrationForm)`
- [x] 5.2 Add honeypot `website` field. **Diverges from initial spec**: uses `forms.TextInput` with inline-style hiding (`position:absolute;left:-9999px` in template) rather than `forms.HiddenInput`. TextInput-with-CSS catches a wider class of bots (those that ignore `<input type="hidden">` but fill all `<input type="text">`)
- [x] 5.3 ~~Add `cf_turnstile_response` field~~ → **Implementation moved to view layer** per design D3. Cloudflare's widget posts as `cf-turnstile-response` (with dash, not Python-friendly). View reads `request.POST["cf-turnstile-response"]` directly and calls `verify_turnstile()`. No form field needed
- [x] 5.4 ~~Override `clean_website` to set `_honeypot_triggered`~~ → **Honeypot check moved to view's `post()` BEFORE `form.is_valid()`** (Phase 7 fix C1). A bot submitting filled honeypot AND invalid form data would otherwise see a form-error 200, fingerprinting the defense. Now: read `request.POST.get(HONEYPOT_FIELD_NAME)` directly in view, fake-success regardless of other field validity
- [x] 5.5 ~~Override `clean_cf_turnstile_response`~~ → **Validation in view per design D3** (see 5.3). View calls `verify_turnstile()` after `form.is_valid()` passes; on rejection adds form error and re-renders
- [x] 5.6 ~~Form takes `client_ip` kwarg~~ → **No longer needed** since Turnstile validation moved to view. View calls `client_ip(request)` directly when invoking `verify_turnstile()`. Form stays minimal (just adds honeypot field)

## 6. AbuseProtectedRegistrationView

- [x] 6.1 In `survey/views.py`, add `class AbuseProtectedRegistrationView(AsyncEmailRegistrationView)` after the existing class
- [x] 6.2 Set `form_class = RegistrationAbuseForm`
- [x] 6.3 ~~Override `get_form_kwargs`~~ → **Not needed** since form no longer takes `client_ip` kwarg (per task 5.6 divergence)
- [x] 6.4 ~~Apply `@method_decorator(@ratelimit)`~~ → **Imperative `is_ratelimited()` calls in `dispatch()`** per design D4. Loops over `(group, rate, retry_after, detail)` tuples for hour and day windows. Cleaner than two stacked decorators because it lets us write the `AbuseEvent` row before responding 429. Wrapped in try/except for fail-open semantics on cache backend exceptions (defense-in-depth on top of `RATELIMIT_FAIL_OPEN`)
- [x] 6.5 In `dispatch`, when a window's `is_ratelimited` returns True: call `log_abuse_event('ratelimit', request, detail)` (where detail is `'hour'` or `'day'`) and return `HttpResponse(..., status=429)` with `Retry-After` header set to the window's TTL (3600 or 86400)
- [x] 6.6 Override `post`: **Phase 7 fix C1** — check `request.POST.get(HONEYPOT_FIELD_NAME)` BEFORE `form.is_valid()`. If non-empty: `log_abuse_event('honeypot', request, 'filled')` and `redirect('django_registration_complete')`. Then call `form.is_valid()` for the rest of validation. After form is valid, call `verify_turnstile()`; on rejection log `('captcha', detail)` where detail is `'missing_token'` or `'siteverify_rejected'`, add form error, return `form_invalid()`
- [x] 6.7 (covered by 6.6 — captcha branch logs and re-renders form via `form_invalid`)
- [x] 6.8 Override `get_context_data` to inject `TURNSTILE_SITE_KEY` from settings into template context (only renders the widget when set, see template task 7.3)
- [x] 6.9 Update `mapsurvey/urls.py`: import changed to `AbuseProtectedRegistrationView`, path updated. URL name `django_registration_register` preserved

## 7. Registration template

- [x] 7.1 In `registration_form.html`, wrap honeypot field rendering in `{% if field.name == "website" %}` block with inline-style hiding (`position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden`) and `aria-hidden="true"`. The label is rendered visually-hidden too. Other fields render normally. **Diverges from `{% if not field.is_hidden %}` approach** — see task 5.2 rationale
- [x] 7.2 Add the Turnstile JS script tag (loaded only when `TURNSTILE_SITE_KEY` is set, gated by `{% if TURNSTILE_SITE_KEY %}`)
- [x] 7.3 Add the Turnstile widget div before the submit button: `<div class="cf-turnstile" data-sitekey="{{ TURNSTILE_SITE_KEY }}"></div>`
- [x] 7.4 Add privacy notice paragraph below widget: `"This form is protected by Cloudflare Turnstile."` + privacy link
- [x] 7.5 Visual verification — `curl http://localhost:8000/accounts/register/` confirms widget renders, honeypot input is in DOM but hidden via inline style

## 8. Tests

- [x] 8.1 Three test classes added to `survey/tests.py`: `CloudflareIPMiddlewareTest`, `VerifyTurnstileTest`, `RegistrationAbuseDefenseTest`. All use GIVEN/WHEN/THEN docstrings
- [x] 8.2 `test_clean_signup_creates_user_when_turnstile_disabled` — empty honeypot + dev-bypass → 302 + User created
- [x] 8.3 `test_filled_honeypot_returns_fake_success_no_user_no_email` — `website="bot"` → 302 + 0 users + 0 emails + 1 honeypot AbuseEvent row. Plus `test_filled_honeypot_with_invalid_form_data_still_returns_fake_success` covers Phase 7 fix C1 edge case
- [x] 8.4 `test_invalid_turnstile_blocks_with_form_error_and_logs_event` — secret set, mocked siteverify rejects → 200 form re-render + 0 users + 1 captcha AbuseEvent row
- [x] 8.5 `test_rate_limit_blocks_after_threshold` — 4 POSTs with hourly limit=1 → 4th gets 429 + `Retry-After` + ratelimit AbuseEvent row. Plus `test_daily_limit_blocks_after_threshold` for the daily window
- [x] 8.6 (covered by 8.2 — same scenario)
- [x] 8.7 Tests use `@override_settings(CACHES={LocMemCache})` for rate-limit isolation. `setUp()` calls `cache.clear()` to prevent counter leakage when tests share a real Redis backend
- [x] 8.8 Full survey test suite passes — `Ran 617 tests in 168s — OK` (614 pre-existing + 3 new beyond initial set)
- [x] 8.9 Additional coverage tests: `test_log_abuse_event_swallows_db_error` (Phase 7 fix C3), `test_cache_unreachable_fails_open` (covers spec scenario "Cache backend unreachable fails open"), `test_ratelimit_fires_before_turnstile_check` (covers spec scenario "Rate limit triggered short-circuits Turnstile")

## 9. Manual verification on staging

- [x] 9.1 Render env vars set on `mapsurvey` web service (TURNSTILE_SITE_KEY, TURNSTILE_SECRET_KEY) via Render MCP. **Code deploy still pending** until commit + PR + merge to master
- [x] 9.2 Real `TURNSTILE_SITE_KEY=0x4AAAAAADL7rIPe_GpiUH5A` and `TURNSTILE_SECRET_KEY` set on Render. `CLOUDFLARE_TRUSTED=True` will arrive via render.yaml on next blueprint sync
- [x] 9.3 Manual browser sign-up on production with real Turnstile challenge — verified by user (visual confirmation widget clears, registration completes)
- [x] 9.4 Activation email arrival on prod — verified by user
- [x] 9.5 Prod curl test (`https://mapsurvey.org/accounts/register/`) with `website=trap` → HTTP 302 to `/accounts/register/complete/`, no User created, AbuseEvent(defense='honeypot', ip=193.34.225.177) row written
- [x] 9.6 Prod curl rate-limit test — POSTs from same IP exceed hourly limit → HTTP 429 with `Retry-After: 3600`, AbuseEvent(defense='ratelimit', detail='hour') rows written
- [x] 9.7 Render log tail confirmed all 3 abuse loggers writing WARNING lines: `abuse.honeypot`, `abuse.captcha`, `abuse.ratelimit`. Bonus: real-world bot caught at 08:10:27 (ip=31.40.204.150, Chrome/41 on Win 7 UA, filled honeypot) within 4 minutes of deploy going live

## 10. Documentation and cleanup

- [x] 10.1 Update `CLAUDE.md` Architecture section with one-line note describing `survey/abuse.py`, `AbuseProtectedRegistrationView`, and the three layered defenses
- [x] 10.2 Add `specs/render-deployment/spec.md` delta in change folder listing 6 new env vars (`TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `CLOUDFLARE_TRUSTED`, `REGISTRATION_RATE_LIMIT_HOUR`, `REGISTRATION_RATE_LIMIT_DAY`, `REDIS_URL`) with WHEN/THEN scenarios. Updated `proposal.md` Modified Capabilities to reflect this
- [x] 10.3 `openspec validate add-registration-abuse-defenses` → valid
- [x] 10.4 All spec scenarios covered: see test mapping in 8.x. Three previously uncovered scenarios (Daily limit, Cache unreachable fails open, Rate limit short-circuits Turnstile) added in 8.9
