# Proposal: Skip server-side PostHog capture for bot requests

## Why

An audit of PostHog error tracking (2026-08-21) found the top "issue" — `Http404` from
`survey/access_control.py`, 58 occurrences / 58 "users" in 6 days — was 95% crawler noise.
Render request logs for the same window show 78 of 82 hits on draft-survey URLs came from
bot user-agents (Googlebot and friends re-crawling URLs we used to submit in the sitemap
before `sitemap-excludes-unpublished`). PostHog assigns each anonymous server-side capture
its own distinct id, so scanners masquerade as a crowd of affected users, and every future
error-tracking review starts with an archaeology dig to separate people from crawlers.
This is the same failure mode already documented for `DemoOpen` bot inflation.

## What Changes

`_posthog_skip_request` (the `POSTHOG_MW_REQUEST_FILTER` hook in `mapsurvey/settings.py`)
gains a bot check: requests whose `User-Agent` matches a known crawler marker, or carries
no `User-Agent` at all, are not tracked. Returning `False` from the request filter bypasses
the middleware's capture context entirely, so bot-triggered exceptions never reach PostHog.

The filter must live in the request filter, not `before_send` or the tag map: on respondent
surfaces (`/surveys/`, `/r/`) the tag map scrubs `$user_agent` before capture, so a
downstream hook has nothing left to classify by.

Out of scope: client-side JS capture (bots rarely execute it), Celery failures (no
user-agent exists there), and the `DemoOpen` bot inflation (separate model, separate fix).

## Impact

- `mapsurvey/settings.py` — bot-marker tuple + one branch in `_posthog_skip_request`
- `survey/tests.py` — filter tests in `PostHogErrorTrackingTest`
- Spec delta: `error-tracking` capability (adds to the still-active
  `posthog-error-tracking` change's ADDED requirements; merge at archive time)

Trade-off accepted: a genuine 500 triggered *only* by a bot goes unreported. Real defects
that affect people surface through human traffic; a defect only bots can trigger is, for
error-tracking purposes, indistinguishable from the noise this change removes.
