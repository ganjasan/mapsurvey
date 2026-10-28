## 1. Templates

- [x] 1.1 `editor/editor_base.html` — 7 tags, none have it; every editor page inherits this file
- [x] 1.2 `editor/analytics_dashboard.html` — 3 tags; this is the page that produced the two blanked
      errors
- [x] 1.3 `base_survey_template.html` — 3 of its 6 tags are missing it. A fourth had
      `crossorigin=""`, which the HTML spec treats as `anonymous` but which reads like an oversight;
      made explicit
- [x] 1.4 `public_results.html` — 3 tags
- [x] 1.5 `survey_language_select.html` — 2 tags
- [x] 1.6 `editor/survey_share.html` — 1 tag
- [x] 1.7 `django_registration/registration_form.html` — the Turnstile tag; keep `async defer` as
      they are
- [x] 1.8 Leave `base.html` alone — its 3 tags already carry the attribute

## 2. Guard

- [x] 2.1 Add a test that walks `survey/templates/**/*.html`, finds `<script src="https://…">` and
      asserts each carries `crossorigin`. Fail with the file path and URL, so CI output alone tells
      whoever added the tag what to do
- [x] 2.2 Confirm the guard actually fails on a tag without the attribute before trusting it — a
      guard that passes vacuously is worse than no guard. Verified by removing the attribute from
      `editor/survey_share.html`: the guard failed naming that file and the exact URL, and went
      green again on restore. A second test pins the tag-matching itself, so the regex cannot
      quietly stop matching and look like "all templates are fine"

## 3. Verify

- [x] 3.1 Run the full suite and record the delta — 1321 tests, OK (1 skipped); 2 new, no
      failures introduced
- [ ] 3.2 After deploy, load `/editor/` and the analytics page and confirm in the network tab that
      every CDN script still returns 200 — the failure mode of this change is a script the browser
      refuses, and it would look like a broken page, not a failed test
- [ ] 3.3 Wait for the analytics page to throw again and read the real error. It fired twice in a
      two-minute session, so this should not take long

## 4. Follow-up (not this change)

- [ ] 4.1 Diagnose whatever the analytics page is actually throwing, and decide whether it deserves
      its own change. Candidates to check first: chart.js against an empty dataset, leaflet.heat
      with no points, leaflet.draw initialising against a map that is not ready
- [ ] 4.2 Separately consider Subresource Integrity across all CDN tags — 7 have `integrity` today
      and 19 do not. Different risk (a re-published version takes the site down), different decision
