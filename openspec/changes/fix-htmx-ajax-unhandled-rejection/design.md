# Design — fix-htmx-ajax-unhandled-rejection

## Context

htmx 1.9.10's `htmx.ajax()` builds its returned promise around `maybeCall(resolve)` /
`maybeCall(reject)` and calls **`reject()` with no argument** on: missing target
(`htmx:targetError`), invalid path, `xhr.onerror` (network failure), `xhr.onabort` (the browser
aborts in-flight XHRs on navigation) and `xhr.ontimeout` (verified in the 1.9.10 source, lines
3046/3278/3342/3349/3356). Declarative `hx-*` requests create no promise — only the programmatic
API does. We call `htmx.ajax()` from 10 sites; only one attaches any handler to the result
(`question_form_modal.html` chains `.then()`, no rejection handler). Every other rejection is
unhandled and reaches PostHog as `Non-Error promise rejection captured with value: undefined`,
with no stack (`synthetic: true`) — permanently undiagnosable from the report alone.

Per-page fixes are the trap named in memory (`lesson_l10n_numbers_break_inline_js`: guards
pinned to a list of pages miss the page added next week).

## Goals / Non-Goals

**Goals:**
- No programmatic htmx request can surface an unhandled promise rejection, on any current or
  future page, without each call site having to remember anything.
- Failures stay observable exactly where htmx reports them: the `htmx:sendError` /
  `htmx:responseError` / `htmx:timeout` events.

**Non-Goals:**
- No global `unhandledrejection` listener that swallows events before PostHog — that would hide
  real defects, not just this undiagnosable one.
- No upgrade of htmx (2.x changes semantics; separate change if ever).
- No PostHog suppression rule — a generic `UnhandledRejection` rule would also drop future real
  rejections from other code (see backlog #186 note).

## Decisions

1. **Wrap `htmx.ajax` once, centrally** (`survey/assets/js/htmx_promise_guard.js`), rather than
   adding `.catch()` at 10 call sites. The wrapper attaches a no-op `.catch()` to the returned
   promise — which marks *that promise* handled — and returns the original promise, so call-site
   semantics (chaining, return values) are byte-identical. Alternative considered: returning
   `p.catch(noop)` instead — rejected because it converts rejection into fulfilment and would
   run callers' `.then()` callbacks on failure.
2. **The guard is a static file included right after each htmx `<script>`** in the three base
   templates that load htmx, not an inline snippet — one source, testable, and a canary can
   enforce the pairing (any template loading htmx must include the guard).
3. **The one chained site keeps its own rejection handler.** A no-op catch on the base promise
   does not cover promises *derived* from it: `htmx.ajax(...).then(f)` creates a second promise
   that still rejects unhandled. `question_form_modal.html`'s draft POST therefore passes a
   rejection callback to `.then(onOk, onErr)`; both arms clear `form._draftPending`, otherwise a
   failed draft POST would leave the flag stuck and block every later type-pick from saving a
   draft (a small live bug in its own right).
4. **Tests are source scans** (the #202 / template-hygiene pattern): the Django test client
   cannot execute browser JS, so the suite asserts (a) the guard file wraps `htmx.ajax` and
   attaches a catch, (b) every template whose source loads `htmx.org` also includes
   `htmx_promise_guard.js` after it, (c) the chained call site carries a rejection handler.

## Risks / Trade-offs

- [Swallowed rejections hide a *typo* — e.g. a bad target selector rejects silently] → htmx
  already fires `htmx:targetError` and logs to console in that case; development behaviour is
  unchanged, only the production noise goes.
- [A future call site chains `.then()` and reintroduces the leak] → the source-scan test fails
  any `htmx.ajax(...).then(` in the tree whose statement carries no rejection handler
  (single-argument `.then` with no following `.catch`).
- [CDN copy of htmx changes] → the guard no-ops when `window.htmx?.ajax` is absent; pages
  degrade exactly as they do today without htmx.

## Migration Plan

Deploy is a normal release (`collectstatic` picks up the new file). No data, no kill switch —
rollback is reverting the commit. After a quiet week in PostHog, resolve issue
`01a019b5-a2f8…6318` and close backlog #194 as fixed (its observation window then measures this
change, not #202).

## Open Questions

None.
