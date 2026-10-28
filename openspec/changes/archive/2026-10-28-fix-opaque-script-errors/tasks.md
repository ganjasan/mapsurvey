# Tasks: fix-opaque-script-errors

## 1. Identify the script

- [x] 1.1 Scan every `<script src>` in the shipped templates — exactly one external script lacks `crossorigin`: Plausible in `partials/_analytics.html`
- [x] 1.2 Corroborate with the data: all 107 events land on pages that include the analytics partial, none on respondent pages, which do not include it
- [x] 1.3 Clear the earlier suspect — Tawk sets an invalid `crossorigin` value (`*`), but an invalid keyword maps to anonymous, and Tawk's own errors already arrive fully described
- [x] 1.4 Confirm `plausible.io` sends `access-control-allow-origin: *` for the exact URL production serves — without that header the attribute would stop the script executing

## 2. Fix

- [x] 2.1 Add `crossorigin="anonymous"` to the Plausible tag, with a comment recording why it is not optional

## 3. Guard

- [x] 3.1 Scan the shipped templates and fail on any external `<script src>` missing `crossorigin`
- [x] 3.2 Ignore same-origin and `{% static %}` sources — they need no CORS negotiation
- [x] 3.3 Pin the scanner itself, so a regex that matched nothing could not make 3.1 pass forever

## 4. Verification

- [x] 4.1 `./run_tests.sh survey` — compare against the 1778-test / OK baseline
- [x] 4.2 Confirm the guard fails without the fix
- [ ] 4.3 After deploy, watch the issue for a week: the count should NOT drop, but new events should carry a message and a file. Re-triage whatever appears — a real defect may have been hiding in this group
