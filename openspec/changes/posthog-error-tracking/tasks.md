# Tasks — stage 3 (error tracking)

## 1. Dependency

- [x] 1.1 Add `posthog = "~=6.9"` to the Pipfile with the comment: 7.x needs Python ≥3.10 (we run
      3.9), and 6.7.5–6.7.13 shipped with broken Django exception capture (#286/#329) — do not
      loosen the pin in either direction without reading design §1.
- [x] 1.2 `pipenv lock` / install so `Pipfile.lock` carries 6.9.3.

## 2. Client initialization

- [x] 2.1 In `survey/apps.py` `SurveyConfig.ready()`: configure the module-level client from
      settings — `api_key`, `host`; when the key is empty set `posthog.disabled = True`.
      `enable_exception_autocapture` stays off, with the comment from design §2 (double-capture
      under gunicorn/Celery).
- [x] 2.2 `sync_mode` stays default (background queue); no flush handling needed in views.

## 3. Django middleware

- [x] 3.1 Add `posthog.integrations.django.PosthogContextMiddleware` to `MIDDLEWARE` after
      `AuthenticationMiddleware`.
- [x] 3.2 `POSTHOG_MW_REQUEST_FILTER`: skip `/admin/` and `/__debug__/`.
- [x] 3.3 `POSTHOG_MW_TAG_MAP`: for paths under `POSTHOG_EXCLUDED_PREFIXES`, drop `$ip` and
      `$user_agent`, truncate `$current_url`/`$request_path` to the matched prefix.
- [x] 3.4 `POSTHOG_MW_EXTRA_TAGS`: none for now — the middleware's defaults plus the user pk
      fallback are enough; email already arrives via the snippet's identify.

## 4. Celery

- [x] 4.1 `task_failure` receiver in `mapsurvey/celery.py`: guard on `posthog.disabled`, tag
      `celery_task_name`/`celery_task_id`, `capture_exception`, swallow all exceptions of its own.

## 5. Configuration surfaces

- [x] 5.1 `render.yaml`: add `POSTHOG_PROJECT_KEY` and `POSTHOG_API_HOST` (`sync: false`, no
      preview inheritance) to the **`mapsurvey-celery` worker** — stage 1 deliberately left the
      worker out; this stage is the reason it comes in.
- [x] 5.2 `.env.example`: extend the PostHog block — the same key now also enables server-side
      error capture; unset still means fully off.
- [x] 5.3 `CLAUDE.md`: one paragraph next to the stage-1 note: three capture paths, the scrubbing
      rule on excluded prefixes, and the 6.9 pin with its reason.

## 6. Tests (`survey/tests.py`, GIVEN/WHEN/THEN, next to the PostHog classes)

- [x] 6.1 Canary: `PosthogContextMiddleware.process_exception` exists and the installed version is
      6.9.x (design §1).
- [x] 6.2 `ready()` with empty key leaves `posthog.disabled` True; with a key set configures
      api_key/host.
- [x] 6.3 Tag map: a `/surveys/<uuid>/...` path loses `$ip`/`$user_agent` and truncates URL tags;
      a `/editor/` path keeps its tags untouched.
- [x] 6.4 Request filter: `/admin/...` and `/__debug__/...` return False; `/surveys/...` returns
      True (captured, scrubbed — not skipped).
- [x] 6.5 Celery receiver: with a mocked client, a task failure captures with task-name tag; a
      raising capture call does not propagate.
- [x] 6.6 The middleware is present in `settings.MIDDLEWARE` after `AuthenticationMiddleware`.

## 7. Verification

- [x] 7.1 Full `./run_tests.sh survey` — 1093 tests, OK (1 skipped).

      **Caught only by the full suite:** the first green run of the new tests hid a defect that
      broke 17 existing ones. With no key configured, `posthog`'s lazy `setup()` raises
      `ValueError("API key is required")` *before* it checks the `disabled` flag, so every test
      that raises on purpose died inside the error reporter. Fixed by gating
      `POSTHOG_MW_CAPTURE_EXCEPTIONS` and the request filter on the key, with
      `test_reporter_is_inert_when_unconfigured` as the regression guard.
- [x] 7.2 Verified end to end against project 248938 by raising through the real middleware stack
      and then querying the events back out:

      | | `/editor/probe-boom/` | `/surveys/probe-uuid-9999/…` |
      |---|---|---|
      | `$request_path` | `/editor/probe-boom/` | `/surveys/` |
      | `$current_url` | full URL | `/surveys/` |
      | `$ip_address` | `203.0.113.99` | absent |
      | `$user_agent` | `ProbeAgent/1.0` | absent |

      Celery path confirmed separately: `celery_task_name = survey.tasks.probe_task`.

      **A real leak was found here, not in review:** the scrubber popped `$ip` while the SDK emits
      `$ip_address`, so behind Cloudflare (which always sets `X-Forwarded-For`) a respondent's IP
      would have been transmitted. The unit test passed because it fed the scrubber hand-written
      tag names — testing the assumption against itself. Tests now build tags through the SDK's own
      `extract_tags`, and `test_sdk_tag_names_are_what_we_scrub` pins the names against the
      installed SDK.

## 8. Project-side setup

- [ ] 8.1 Enable client-side exception autocapture in project settings (Error tracking section).
      **User's call — it changes what is collected from real users' browsers.**
- [x] 8.2 ~~Trends insight on `$exception` volume plus a threshold alert.~~ Superseded: the GitHub
      integration is connected instead (kind `github`, account `ganjasan`, no errors), so an error
      tracking issue becomes a GitHub issue in the repo we already work in. No new vendor, no
      channel to pick, and the follow-up lands where the work lands.

      **Known trade-off, deliberately accepted:** this is pull, not push. Nothing notifies us when
      volume spikes — we find out when we look at PostHog or when an issue is filed by hand. Good
      enough while traffic is small; revisit if an incident is discovered late. Design §6 said
      alerting was "part of done", and this consciously relaxes that.

## 9. Rollout

- [ ] 9.1 Merge; set the two variables on `mapsurvey-celery` in Render (web already has them).
- [ ] 9.2 Confirm a production exception appears in error tracking; confirm the alert fires on the
      test threshold, then set the real threshold.
