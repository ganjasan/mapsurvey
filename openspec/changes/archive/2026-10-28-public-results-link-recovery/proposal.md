## Why

Creators share the results page by copying the URL out of their browser's address bar while
sitting in the editor, which yields the editor-only preview URL
`/editor/surveys/<uuid>/public-results/preview/` instead of the public `/r/<slug>/`. That URL is
guarded by `survey_permission_required('editor')`, so every visitor who follows it is bounced to
`/accounts/login/` — with no `?next=`, so the destination is lost — and, if they register to get
past the wall, lands on `Http404` because the survey belongs to someone else's organization.

This is observed behaviour, not a hypothetical. On 2026-08-18 the creator of survey `Sótão`
(a live survey with 106 responses) published a results page and shared the preview link. Three
visitors followed it, each registered an account trying to get through, and each hit two 404s
afterwards; one abandoned entirely, two only reached the results by guessing their way into the
survey itself and clicking through the thanks page. Those three accounts, plus a fourth that never
confirmed its email, made up four of the six registrations that week — inflating the registration
count with people who never wanted an account and depressing the "registration → first survey"
activation rate, which was in truth 2 of 2 for genuine creators.

Every creator who shares a results page can reproduce this, so the leak recurs and corrupts the
funnel each time.

## What Changes

- A visitor without editor rights on the preview URL is redirected to the survey's published public
  results page (`/r/<slug>/`) instead of being blocked. This applies to anonymous visitors (who are
  currently sent to login) and to signed-in users from another organization (who currently get a
  404).
- When no published results page exists to redirect to, the previous behaviour stands: anonymous →
  login, signed-in non-member → 404. The recovery path only exists where there is a genuine public
  destination.
- The login redirect in `survey_permission_required` carries `?next=`, so a visitor who does log in
  arrives where they were headed rather than on the dashboard. This fixes the whole editor surface,
  not just the preview URL.
- The editor gains an explicit, primary way to copy the public results link, so copying from the
  address bar is no longer the path of least resistance. The existing "Preview" control is
  visibly distinguished from the shareable link.
- **Non-goal**: no change to who may *view* a results page. An unpublished or `unlisted` page stays
  exactly as reachable as it is today; this change only rescues visitors when a public destination
  already exists.

## Capabilities

### New Capabilities
- `public-results-link-sharing`: how a creator obtains a shareable results link, and what happens to
  a visitor who follows an editor-only preview link instead of the public one.

### Modified Capabilities
- `survey-editor`: unauthenticated access to editor URLs must preserve the requested destination
  through the login redirect rather than discarding it.

## Impact

- `survey/public_results_editor.py` — `public_results_preview` gains a non-editor fallback path;
  it can no longer rely on the decorator to reject every non-editor.
- `survey/permissions.py` — `survey_permission_required` appends `?next=` to the login redirect.
  Shared by every editor view, so the blast radius is the whole editor.
- `survey/templates/editor/public_results.html` and
  `survey/templates/editor/partials/_survey_nav_tabs.html` — copy-link affordance and clearer
  labelling of "Preview".
- Funnel metrics: registrations driven by this trap disappear, so `creator_registered` counts drop
  slightly while activation rate rises. Worth noting when reading week-over-week numbers after
  release — the improvement is measurement correction, not growth.
- No migration, no model change, no new dependency.
