# Design — PostHog error tracking (stage 3)

## Context

Stage 1 put posthog-js on creator-facing pages, identified creators by pk, and left two hooks this
stage picks up: the `POSTHOG_PROJECT_KEY` gate ("empty = everything off") and the person timeline
that server-side errors should join. There is no existing error aggregation to integrate with or
migrate from; `LOGGING` routes WARNING+ to stdout for Render and keeps doing so.

## Decisions

### 1. Pin `posthog==6.9.*` and record why an upgrade is not routine

posthog-python 7.x requires Python ≥3.10; this project runs 3.9 (Pipfile), so 6.9.3 is the newest
installable release. That would be a one-line note except for history: the Django middleware's
exception capture was *silently broken twice* (posthog-python #286, then regression #329 — versions
6.7.5–6.7.13 shipped without a working `process_exception`). Verified against the installed 6.9.3
that `process_exception` exists and calls `capture_exception`. The Pipfile pins `~=6.9` with a
comment; anyone bumping across 7.0 must bump Python first, and anyone downgrading must re-check the
middleware actually captures.

A test asserts `PosthogContextMiddleware.process_exception` exists — a canary against the exact
regression class that shipped twice upstream, and against a quiet downgrade.

### 2. Initialize the global client in `AppConfig.ready()`, disabled when unconfigured

The SDK's module-level client (`posthog.api_key = ...`) is what both the middleware and the Celery
handler use. It is configured in `SurveyConfig.ready()` from Django settings:

- `POSTHOG_PROJECT_KEY` unset → `posthog.disabled = True`. Not "don't configure": *explicitly
  disabled*, so a stray `capture_exception` call in a test or management command is a cheap no-op
  instead of an HTTP attempt with an empty key.
- `enable_exception_autocapture` stays **off**. It installs `sys.excepthook`/`threading.excepthook`
  process-wide; under gunicorn workers and Celery prefork that is redundant with the two explicit
  paths and makes double-capture likely (the middleware already reports request exceptions, the
  signal already reports task failures). Two deliberate hooks beat one global one we'd have to
  de-duplicate.

### 3. Celery: `task_failure` signal, not autocapture, not per-task try/except

`mapsurvey/celery.py` gains a `task_failure` receiver that tags the task name and id and calls
`capture_exception`. The signal is Celery's designed extension point for exactly this; it fires for
every task without touching task code, including tasks added later (the AI generator's). The
receiver guards on the disabled flag and swallows its own errors — an error reporter that can crash
the worker is worse than no reporter.

### 4. Respondent pages: capture the error, strip the identity

A 500 on `/surveys/...` is our defect; not capturing it would blind us on the highest-traffic
surface. But stage 1's rule — PostHog never receives respondent data — must survive. The middleware
default tags include `$current_url`, `$ip` (from X-Forwarded-For) and `User-Agent`; on respondent
pages those describe a respondent.

So the middleware is configured with a `POSTHOG_MW_TAG_MAP` that, for paths under
`POSTHOG_EXCLUDED_PREFIXES` (the same setting the snippet gate reads — one boundary, one list),
drops `$ip` and `$user_agent` and truncates `$current_url`/`$request_path` to the prefix
(`/surveys/`), keeping the error and its stack trace but no respondent-describing metadata.
Respondents are never identified persons, so there is no distinct-id leak to prevent — the
scrubbing covers the request metadata that *could* describe them.

`POSTHOG_MW_REQUEST_FILTER` additionally excludes `/admin/` (Django admin stack traces routinely
embed object reprs) and `/__debug__/` (debug toolbar).

### 5. Client-side autocapture is a project setting, not a template change

posthog-js exception autocapture is enabled in the PostHog project's Error tracking settings and
delivered via remote config to the already-loaded SDK. No template edit, and the stage 1 gate
composes for free: pages that never load the snippet can never capture client exceptions. The
`suppression rules` and rate limiting live in PostHog, where they can be tuned without a deploy.

### 6. Alerting is part of "done"

Error tracking that no one is told about is a dashboard, not an alarm. A trends insight on
`$exception` count with a threshold alert (email) is created in the project as part of rollout —
via MCP, so it is reproducible from the tasks file. Threshold starts crude (any exceptions > N per
hour); tuning follows real volume.

## Risks / trade-offs

- **Free tier is 100K exceptions/month.** A crash loop on a hot page could burn that in a day. The
  SDK batches and PostHog rate-limits per-issue bursts; the volume alert doubles as the cost alarm.
- **`$ip`/`$user_agent` scrubbing depends on tag names the SDK emits.** A canary test pins the
  middleware's `extract_tags` output keys so an SDK rename fails loudly instead of silently leaking.
- **Celery receiver adds latency to failure paths** — negligible (enqueue to the SDK's background
  queue), and only on failures.
- **Double capture** if someone later enables `enable_exception_autocapture` without reading this
  file; the design note plus the explicit `False` in `ready()` with a comment is the guard we have.

## Open questions

1. Alert destination — email to konuchovartem@ works today; Discord webhook via CDP destination
   later?
2. Should `$exception` events from PR previews (which have no key) ever be wanted? Currently
   impossible by construction; revisit only if a preview-debugging need appears.
