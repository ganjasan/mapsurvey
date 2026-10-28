# Fix htmx.ajax unhandled promise rejection

## Why

PostHog error tracking shows `UnhandledRejection: Non-Error promise rejection captured with
value: undefined` — 10 events (2026-08-19 … 2026-09-25) from five creators across Chrome, Edge
and Safari, 9 of 10 on the Responses page (backlog #194). The events carry no stack at all
(`synthetic: true`), so each report is undiagnosable noise that also masks real defects in the
panel. The source is htmx 1.9.10: `htmx.ajax()` returns a promise that it rejects with a **bare
`reject()`** (value `undefined`) on network error, abort (user navigates mid-request), timeout,
missing target and invalid path. Every programmatic `htmx.ajax(...)` call without a rejection
handler — 10 call sites, concentrated on the Responses page and the editor, exactly the reported
geography — produces this event whenever a request fails or is abandoned.

## What Changes

- New static asset `survey/assets/js/htmx_promise_guard.js`: wraps `window.htmx.ajax` once so
  every returned promise gets a no-op rejection handler attached (the promise itself is still
  returned unchanged for callers). Failures remain observable through the htmx error events
  (`htmx:sendError`, `htmx:responseError`, `htmx:timeout`), which is where htmx reports them.
- The guard is included immediately after the htmx `<script>` in all three base templates that
  load htmx: `editor/editor_base.html`, `editor.html`, `base_survey_template.html`.
- The one call site that chains `.then()` on the `htmx.ajax` promise
  (`question_form_modal.html`, draft POST) gets a rejection handler of its own, because a derived
  promise is not covered by the guard on the base promise; on failure it also clears
  `_draftPending` so the next type-pick can retry the draft.
- Canary test pins the contract: the guard file wraps `htmx.ajax`, and every template that loads
  htmx also includes the guard after it (a new base template cannot silently miss it).

## Capabilities

### New Capabilities

- `htmx-promise-guard`: programmatic htmx requests never surface unhandled promise rejections;
  every base template that loads htmx also loads the guard.

### Modified Capabilities

<!-- none — no existing spec's requirements change -->

## Impact

- `survey/assets/js/htmx_promise_guard.js` (new; needs `collectstatic`)
- `survey/templates/editor/editor_base.html`, `survey/templates/editor.html`,
  `survey/templates/base_survey_template.html` (one `<script>` include each)
- `survey/templates/editor/partials/question_form_modal.html` (rejection handler on the chained
  `.then`)
- `survey/tests.py` (guard/canary tests)
- After deploy: PostHog issue `01a019b5-a2f8-7730-8ac0-b1734cfb6318` and backlog #194 close once
  no new events arrive.
