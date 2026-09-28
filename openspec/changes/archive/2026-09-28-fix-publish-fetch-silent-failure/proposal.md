# Fix: "Publish draft" is silently dead when a fetch fails

## Why

PostHog error tracking caught a `Failed to fetch` on 2026-09-25: a new creator (arrived from
ChatGPT, browser Brave) clicked **Publish draft** and nothing happened — the
compatibility-check request was blocked (network or Brave Shields) and the promise chain in
`checkAndPublishDraft` has no `.catch` and no `r.ok` guard, so the failure is swallowed.
`doPublishDraft` — the POST that actually publishes — alerts on HTTP error statuses but also
lacks `.catch` on both of its fetch chains. A silently dead button on the primary path to
publishing hits exactly our ad-blocker-heavy creator audience (the reason PostHog is served
through a first-party proxy). Backlog #190.

## What Changes

- `checkAndPublishDraft` (`survey/templates/editor/partials/_lifecycle_scripts.html:130`) gets
  an `r.ok` guard before `r.json()` and a `.catch` that shows a clear, visible message instead
  of doing nothing.
- Both fetch chains in `doPublishDraft` (same file, line 147) get the same `.catch` for
  network-level failures; their existing HTTP-status `alert()` paths stay as they are.
- A guard test asserts the partial keeps its error handlers (template-content test, the only
  server-side handle on inline JS — same style as existing template guard tests).

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `draft-copy-lifecycle`: publishing a draft SHALL never fail silently — a failed
  compatibility check or publish request MUST surface a visible error to the creator.

## Impact

- One template: `survey/templates/editor/partials/_lifecycle_scripts.html` (included only by
  `editor/survey_detail.html`; the chain is not duplicated anywhere).
- One test module: `survey/tests.py` (new guard test).
- No backend, model or URL changes.
