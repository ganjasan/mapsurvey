# "Publish draft" does nothing at all when the compatibility-check fetch fails

**Type**: bug
**Priority**: medium
**Area**: frontend
**Created**: 2026-09-28

## Description

One `Failed to fetch` event in PostHog error tracking on 2026-09-25: a **new creator, arrived
from ChatGPT, browser Brave**, clicked **Publish draft** and the compatibility-check request in
`checkAndPublishDraft` (`survey/templates/editor/partials/_lifecycle_scripts.html:130`) never
completed. What blocked it is unknown — network, or Brave Shields eating the request.

The promise chain has **no `.catch` and no `r.ok` check**:

- a network failure rejects the first `.then` — nothing handles it, the button silently does
  nothing, no modal, no message;
- a non-JSON error response (a 500 page) would throw inside `r.json()` with the same silence.

`doPublishDraft` (line 147) — the POST that actually publishes — has `alert()` paths for HTTP
error statuses but also **no `.catch`** on either of its two fetch chains, so a network failure
there is equally mute.

A silently dead button on the *primary path to publishing* is exactly the kind of drop-off the
funnel work is chasing (reg→publish is the strong leg; a creator who clicks Publish and sees
nothing happen may just leave). One event so far, but the failure mode punishes precisely the
ad-blocker-heavy audience we know we have (see the PostHog proxy rationale in CLAUDE.md).

## Reproduce

1. Open a survey with a draft, DevTools → Network → set the `check-compatibility/` request to
   be blocked (or go offline).
2. Click **Publish draft**.
3. Nothing happens: no modal, no error, console shows the unhandled rejection.

## Fix

- Add `.catch` (and an `r.ok` guard before `r.json()`) to `checkAndPublishDraft` with a visible
  message — e.g. `alert('Could not reach the server to check the draft. Check your connection
  and try again.')` or an inline error near the button, matching how `doPublishDraft` already
  alerts on error statuses.
- Give both fetch chains in `doPublishDraft` the same `.catch`.
- One place to fix: `survey_detail.html` only calls the function via its two Publish buttons
  and includes this same partial (line 405) — the chain is not duplicated anywhere.

## Notes

- Found in the same error-tracking review as
  [improvement-error-tracking-signal-quality.md](improvement-error-tracking-signal-quality.md)
  (item 5 of the 2026-09-28 pass).
- Promoted on 2026-09-28
