# Design — fix-publish-fetch-silent-failure

## Context

`_lifecycle_scripts.html` renders inline JS on `editor/survey_detail.html` for lifecycle
transitions. `checkAndPublishDraft()` fetches `editor_check_compatibility` and opens one of
two modals; `doPublishDraft(force)` POSTs `editor_publish_draft`, following redirects,
reloading on OK, alerting on error statuses. Neither chain has a `.catch`; the first also
calls `r.json()` without checking `r.ok`. Error dialogs on this surface are plain `alert()`
today.

## Goals / Non-Goals

- **Goal**: a creator who clicks Publish always gets feedback — modal, reload, or a visible
  error message. Nothing else changes.
- **Non-Goals**: no redesign of the alert-based error UX; no retry logic; no change to the
  server endpoints; no touching the modal flows.

## Decisions

1. **`alert()` for the failure message**, not a new inline error element. Every existing
   error path in this file already alerts; a minimal fix stays in that idiom. Alternative
   (an inline banner) rejected as scope creep for a two-function patch.
2. **One shared handler** `publishFetchFailed()` in the partial, used as `.catch` by all
   three chains, with one translatable message via `{% trans %}` (the file already renders
   through Django templates): "Could not reach the server. Check your connection and any
   ad blocker, then try again." Mentioning the ad blocker is deliberate — the one real event
   came from Brave, and our creator audience skews blocker-heavy.
3. **`r.ok` guard in `checkAndPublishDraft`**: non-OK → throw into the same catch, never
   `r.json()` a 500 page. `doPublishDraft` keeps its status-specific handling; `.catch` there
   covers only network-level rejects and unexpected throws.
4. **Guard test = template-content assertions** on the rendered `survey_detail` page (login
   as owner, GET, assert the handler name and `.catch(` wiring are present). Inline JS has no
   server-side behavioral handle (lesson `shared-partial-global-rename`: template tests can't
   see JS execute), so the test pins the presence of the wiring; the runtime behavior is to be
   checked once by hand in a browser with the request blocked (tasks 3.2).

## Risks / Trade-offs

- [Catch also fires on programming errors inside the `.then` chain] → acceptable: today those
  are equally silent; a generic message beats nothing, and PostHog JS autocapture still
  records the underlying exception.
- [`alert()` on mobile Safari/brave quirks] → alert is already the error idiom on this page;
  no new risk.

## Migration Plan

Template-only change; deploys with the next release, no migration, rollback = revert.

## Open Questions

None.
