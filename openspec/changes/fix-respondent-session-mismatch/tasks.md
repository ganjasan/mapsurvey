## 1. Session validation in `survey_section`

- [x] 1.1 Replace the two create-session branches with one validated path: load the cookie's
      session (`select_related('survey')`), honour it only if it exists, is not `is_deleted`, and
      its survey is the canonical or a version of it; otherwise create a fresh session against
      canonical with `session_start` + `record_demo_open`, as today.
- [x] 1.2 Derive `session_survey` from the validated session, keeping version routing.

## 2. Section lookup

- [x] 2.1 Replace the bare `.get()` with `.filter(...).first()`; on miss, drop
      `survey_session_id` and redirect to the survey entry point.

## 3. Tests

- [x] 3.1 Cross-survey GET: stale session from survey A + direct section link to survey B → 200,
      new session for B (was 500).
- [x] 3.2 Cross-survey POST: submitting B's section with A's session cookie → answers land in a
      B session (was 500 — adorion's exact case).
- [x] 3.3 Soft-deleted session → new session created, answers do not land in the deleted one.
- [x] 3.4 Version routing: session on an archived version still serves that version's section.
- [x] 3.5 Unknown section name → redirect to `/surveys/<uuid>/`, no 500.
- [x] 3.6 Run the survey test suite; compare against baseline. 1505 tests, OK (skipped=1) — same as baseline.
