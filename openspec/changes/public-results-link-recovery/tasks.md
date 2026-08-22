## 1. Login redirect keeps its destination

- [x] 1.1 Replace `redirect('login')` in `survey_permission_required` (`survey/permissions.py:120`) with `redirect_to_login(request.get_full_path())`; same fix applied to `org_permission_required`, which carried the identical defect
- [x] 1.2 Test: an anonymous request to a survey-scoped editor URL redirects to the login page with `next` set to the requested path
- [x] 1.3 Test: signing in from that redirect lands on the originally requested URL, not the dashboard

## 2. Preview view handles non-editors itself

- [x] 2.1 Add `PUBLIC_RESULTS_PREVIEW_FALLBACK` to `settings.py` (default `True`) and document it in `.env.example`
- [x] 2.2 Remove `@survey_permission_required('editor')` from `public_results_preview` and perform the survey lookup in-view, excluding `deleted_at`, returning `404` for an unknown UUID
- [x] 2.3 Compute the effective role in-view via `get_effective_survey_role` / `_check_survey_role` (helper `_may_edit`, which also re-asserts the active-org check); render the preview unchanged when the role suffices
- [x] 2.4 On insufficient role, look up `PublicResultsPage.objects.filter(survey=..., is_published=True)` read-only and redirect to `/r/<slug>/` when found — never call `_get_or_create_page` on this path
- [x] 2.5 On insufficient role with no published page, reproduce the prior denial: anonymous → `redirect_to_login`, otherwise `404`
- [x] 2.6 Gate only the redirect branch on `PUBLIC_RESULTS_PREVIEW_FALLBACK`

## 3. Tests for the guards the decorator used to provide

- [x] 3.1 Anonymous visitor + published page → `302` to `/r/<slug>/`
- [x] 3.2 Authenticated outsider + published page → `302` to `/r/<slug>/`
- [x] 3.3 Published `unlisted` page → still `302` to `/r/<slug>/`
- [x] 3.4 Unpublished page: anonymous → login, authenticated outsider → `404`
- [x] 3.5 Trashed survey with a published page → no redirect to `/r/<slug>/`
- [x] 3.6 Unknown UUID → `404`
- [x] 3.7 Non-editor request against a survey with no page row creates no `PublicResultsPage` (assert row count before/after)
- [x] 3.8 Owner → `200` rendering the preview template with `preview` set, both when the page is published and when it is not
- [x] 3.9 Owner response still permits same-origin framing
- [x] 3.10 `PUBLIC_RESULTS_PREVIEW_FALLBACK=False` → anonymous visitor with a published page goes to login
- [x] 3.11 A `viewer`-role member is not an editor: forwarded to the public page rather than shown the preview

## 4. Editor affordance

- [x] 4.1 Add a copy-public-link control to `editor/public_results.html`, shown only when the page is published (plain `navigator.clipboard.writeText`, matching `_survey_nav_tabs.html` — `editor_clipboard.js` is the question/section buffer, not a text-copy helper)
- [x] 4.2 Relabel the existing "Preview" control in `editor/public_results.html` and `editor/partials/_survey_nav_tabs.html` so it does not read as the shareable link
- [x] 4.3 Test: configuration tab for a published page offers the `/r/<slug>/` copy control; for an unpublished page it does not
- [x] 4.4 Run the template comment guard test after editing templates
- [x] 4.5 Rename the editor nav tab "Publish" → "Public results" in `_survey_nav_tabs.html`; align the page title and the "manage in the … space" hint so nothing still calls it "Publish" (it collides with the survey's own "Publish — open for responses")
- [x] 4.6 Test: the survey nav renders a "Public results" tab and no "Publish" tab label
- [x] 4.7 Rename the other two tabs to remove the Results/Public-results collision: "Build" → "Survey", "Results" → "Responses"; align in-page headings (`survey_detail.html` context bars, both editable and read-only) and the text links that point at the responses tab (`survey_share.html`, `_lifecycle_scripts.html`). Internal `active_tab` codes unchanged.
- [x] 4.8 Test: the nav renders Survey / Responses / Public results and none of Build / Results / bare Publish

## 5. Branded 404 for unavailable surveys

- [x] 5.0a Add `survey/templates/404.html` as a **standalone**, self-contained page (inline styles, no static assets, no site nav/footer — so it renders even when the marketing CSS pipeline is down; theme-aware); branch on `request.path` — survey prefixes (`/surveys/`, `/r/`, `/editor/surveys/`) get the "unpublished / deleted / wrong link" copy, everything else generic
- [x] 5.0b Offer a link to the public survey list and, when authenticated, to the dashboard
- [x] 5.0c Test: `/r/<unknown>/` returns 404 with the survey-specific copy
- [x] 5.0d Test: a non-survey unknown path returns 404 without survey-specific wording
- [x] 5.0e Test: 404 renders correctly with `DEBUG=False` (the handler only uses `404.html` then); run the template comment guard test

## 6. Verify and ship

- [x] 6.1 Re-ran `./run_tests.sh survey` after 404 + tab-rename — 1246 tests OK
- [ ] 6.2 After deploy, request `/editor/surveys/058bd0df-3433-4887-85e9-23faf5b3ad0e/public-results/preview/` signed-out and confirm `302` to `/r/sotao/`
- [ ] 6.3 Note the release date alongside the funnel dashboard, so the expected drop in `creator_registered` is read as the fix working rather than a traffic regression
