# Tasks — fix-htmx-ajax-unhandled-rejection

## 1. Guard

- [x] 1.1 Create `survey/assets/js/htmx_promise_guard.js`: wrap `window.htmx.ajax` so the
      returned promise gets a no-op `.catch()` attached and the original promise is returned;
      no-op safely when `window.htmx`/`htmx.ajax` is absent.
- [x] 1.2 Include the guard `<script>` immediately after the htmx include in
      `survey/templates/editor/editor_base.html`, `survey/templates/editor.html`,
      `survey/templates/base_survey_template.html`.

## 2. Chained call sites

- [x] 2.1 `question_form_modal.html` draft POST: pass a rejection handler to `.then(onOk, onErr)`;
      both arms clear `form._draftPending` so a failed draft POST does not block later type-picks.
- [x] 2.2 `survey_detail.html` save-on-close draft POST (found by the 3.3 scan): rejection handler
      resets `form._qtpSavedOnClose` so the next close retries the save.

## 3. Tests

- [x] 3.1 Canary: guard file exists, wraps `htmx.ajax`, attaches a catch.
- [x] 3.2 Source scan: every template loading `htmx.org` includes `htmx_promise_guard.js` after it.
- [x] 3.3 Source scan: any `htmx.ajax(...).then(` in templates/assets carries a rejection handler.

## 4. Verify

- [x] 4.1 `./run_tests.sh survey` green — 2142 tests, OK (skipped=1).
- [x] 4.2 Browser check of the mechanism against the real htmx 1.9.10 build (Playwright, standalone
      page, one source element per request): a network-failed `htmx.ajax()` produced 1
      `unhandledrejection` without the guard and 0 with it; `htmx:sendError` still fired; a
      caller's own rejection handler still received the rejection. Not re-checked in the running
      editor — the guarded code path is identical there.
- [ ] 4.3 After deploy: no new events on PostHog issue `01a019b5-a2f8-7730-8ac0-b1734cfb6318` for a
      week → resolve it and close backlog #194.
