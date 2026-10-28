# Error tracking on PostHog (stage 3 of the internal-analytics plan)

## Why

Production errors are invisible. `LOGGING` (`settings.py`) sends WARNING+ to stdout, which reaches
Render's log stream and stops there: nothing aggregates, nothing alerts, nothing distinguishes "one
traceback once" from "forty creators hit this all morning". The lead who logged in and deleted their
map 13 seconds later was reconstructed from Render request logs by hand — and that was a *behaviour*
question. For an *error* question we currently cannot even do that much without scrolling raw logs.

This is stage 3 of `posthog-internal-analytics` (stage 1 shipped in PR #63; events flow from
production). Error tracking was planned there as a net-new capability — nothing is migrated, because
there is nothing to migrate.

Why now, before the activation-funnel events (stage 2): the AI survey generator is about to merge,
it is the largest new surface in months (LLM calls, Celery tasks, HTMX polling), and its failures
will land exactly where we currently cannot see them — background workers and client-side JS.

## What Changes

Three capture paths, one project (248938, Cloud EU), all gated on the same `POSTHOG_PROJECT_KEY`
that already gates the snippet — unset means everything below is inert:

- **Django request exceptions.** `posthog.integrations.django.PosthogContextMiddleware` (SDK
  `posthog==6.9.*`, pinned — see design) added after `AuthenticationMiddleware`. Its
  `process_exception` captures view exceptions with the authenticated user's pk as distinct id, so
  an error joins the same person timeline the snippet already writes.
- **Celery task exceptions.** A `task_failure` signal handler calling `capture_exception` with the
  task name tagged. The middleware cannot see the worker; without this, AI-generation failures stay
  invisible — precisely the ones we most need next month.
- **Client-side exceptions.** posthog-js exception autocapture, enabled per project settings /
  remote config (`window.onerror` + `onunhandledrejection`). No template change: the snippet from
  stage 1 already loads the SDK, and the same page gate applies — no snippet on `/surveys/` or
  `/r/`, therefore no client-side capture there either.

Alerting: an insight on `$exception` volume with a threshold alert to email, so a spike is a push,
not something discovered while reading dashboards.

## Boundary note (unchanged from stage 1)

Server-side capture fires on *our* code failing, wherever it fails — a 500 on a respondent page is
our defect and is captured. What must not happen is respondent *identification*: respondents are
anonymous (no account), so `process_exception` has no user to attach beyond request metadata, and
the request filter strips identifying tags on excluded paths (design §4). Client-side capture
follows the snippet and therefore never runs on respondent surfaces at all.

## Non-goals

- Named activation events (stage 2) — unchanged, still next.
- Retiring Plausible (stage 4) — unchanged, gated on the parallel-run comparison.
- Source maps / release tracking — static JS here is not bundled or minified beyond whitenoise; the
  stack traces are readable as-is.
- Replacing the `abuse` logger or Render log stream — stdout logging stays; PostHog is the
  aggregation layer, not the log of record.
- Uptime/health monitoring — different problem.
