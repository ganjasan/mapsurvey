# htmx-promise-guard Specification (delta)

## ADDED Requirements

### Requirement: Programmatic htmx requests never surface unhandled promise rejections

`htmx.ajax()` SHALL be wrapped once, in `survey/assets/js/htmx_promise_guard.js`, so that the
promise it returns always has a rejection handler attached, while the original promise is
returned to the caller unchanged. A call site that chains `.then()` on the returned promise
SHALL provide its own rejection handler, because the guard does not cover derived promises.

#### Scenario: A failed request produces no unhandled rejection

- **WHEN** a programmatic `htmx.ajax()` request errors, aborts, times out, or finds no target
- **THEN** no `unhandledrejection` event fires; the failure remains observable through the
  htmx error events (`htmx:sendError`, `htmx:responseError`, `htmx:timeout`, `htmx:targetError`)

#### Scenario: Call-site semantics are unchanged

- **WHEN** a caller chains on or awaits the promise returned by the wrapped `htmx.ajax()`
- **THEN** it receives the original promise with its original settlement — a rejection is not
  converted into a fulfilment

#### Scenario: A chained .then carries a rejection handler

- **WHEN** any template or static JS chains `.then(` on an `htmx.ajax(...)` call
- **THEN** the statement carries a rejection handler (a second `.then` argument or a `.catch`),
  and the test suite fails naming the file when it does not

### Requirement: Every template that loads htmx also loads the guard

Any template whose source includes the htmx library SHALL include
`js/htmx_promise_guard.js` after it. The test suite SHALL fail, naming the file, when a
template loads htmx without the guard.

#### Scenario: A new base template cannot silently miss the guard

- **WHEN** a template contains an htmx `<script>` include but no `htmx_promise_guard.js`
  include after it
- **THEN** the test suite fails and names that template
