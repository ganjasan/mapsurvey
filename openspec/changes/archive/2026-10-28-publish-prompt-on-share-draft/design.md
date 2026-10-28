# Design — publish-prompt-on-share-draft

## Context

`share_page` (`survey/share_views.py`) is gated by `@survey_permission_required('editor')`
and renders `editor/survey_share.html`. The publish transition lives in
`editor_survey_transition` (`@survey_permission_required('owner')`, `@require_POST`,
reads `status` from POST, validates via `survey.can_transition_to()`). The public survey
URL `/surveys/<uuid>/` is gated by `check_survey_access()`, which raises `Http404` for any
non-public status — owners/editors bypass this check, which is why the Draft 404 is
invisible to the creator.

## Decisions

### Gate on `status == 'published'`, not on a broader "shareable" heuristic
The public survey URL is reachable only when `status == 'published'`. `testing` is
reachable solely through the one-time test token (not the plain UTM link), and
`closed`/`archived` are not open for responses. So the single correct predicate for
"this public link works" is `status == 'published'`. Everything else shows the banner.

### Reuse `editor_survey_transition`, publish via `fetch` + reload
No new endpoint. The inline button POSTs `status=published` to the existing transition
URL. Because that endpoint redirects to `editor_survey_detail` (Build) on a normal POST,
we instead POST with `fetch` and `location.reload()` on success — keeping the creator on
Share, where the now-unlocked links appear. This mirrors the widget's `doTransition`
but controls the post-publish destination.

### Owner-only Publish; editors get a hint
`editor_survey_transition` requires `owner`. A non-owner editor can open Share but cannot
publish, so the button is shown only when `effective_role == 'owner'` and
`can_transition_to('published')` is allowed; otherwise the banner tells the editor to ask
the owner. The view computes `can_publish = survey.can_transition_to('published')[0]`.

### Status-specific banner copy
- `draft` → "still a Draft … the public link returns a 404 until you publish."
- `testing` → "in Testing … the public link isn't live yet — publish to open for responses."
- `closed` / `archived` → informational ("no longer open for responses"); Publish shown
  only if the transition is actually allowed.

## Risks / Trade-offs

- Hiding the tracking form until publish means a creator cannot pre-build campaign links
  while still drafting. Accepted per product decision — the incident-prevention value
  (never hand out a 404 link) outweighs pre-building convenience.
- `fetch`-based publish needs the CSRF token; taken from the cookie like the thanks
  editor autosave.

## Migration

None — presentation-only, no schema or endpoint changes.

## Open Questions

- Whether to extend the same guardrail to the dashboard "open survey" affordance and QR
  generation is out of scope here (noted in the backlog item as "consider").
