# Http404 is reported to PostHog error tracking as if it were a defect

**Type**: bug
**Priority**: medium
**Area**: infra
**Created**: 2026-08-17

## Description

`PosthogContextMiddleware` reports every view exception, and in Django `Http404` is ordinary
control flow, not an error. In the first two days after error tracking shipped (2026-08-15),
**16 of 19 captured events were `Http404`** — 84% of the panel. Every one of them was a
crawler requesting an unpublished survey.

The panel is therefore already useless for its purpose. A real `500` would arrive and sit
below a wall of 404s, and any alerting built on event volume would fire on bot traffic.

Found while investigating the sitemap defect (`sitemap-excludes-unpublished`). Deferred out
of that change because it is a bug in the error reporter, not in what we publish, and should
not ride along with a change to public URLs.

## Proposed Approach

Filter by exception type in `_posthog_skip_request` / the middleware's capture path
(`mapsurvey/settings.py:318`), which today filters only by request path (`/admin/`,
`/__debug__/`). Candidates to drop: `Http404`, `PermissionDenied`, `SuspiciousOperation` —
all of them outcomes Django defines, not failures.

Check what the SDK offers before hand-rolling: the middleware may expose an
exception-level hook, in which case the filter belongs there rather than in a request filter
that never sees the exception.

## Notes

- Capture paths and the scrubbing rules are documented in `CLAUDE.md` under "Error tracking".
- `POSTHOG_MW_CAPTURE_EXCEPTIONS` is gated on `POSTHOG_PROJECT_KEY`, so tests and PR previews
  are unaffected either way.
- The `posthog` package is pinned `~=6.9`; `PostHogErrorTrackingTest` has canary tests that
  pin SDK tag names, and a similar canary is warranted for whatever hook this uses.
- Sibling issue, already fixed separately: the 404s themselves came from
  `openspec/changes/sitemap-excludes-unpublished/`.
