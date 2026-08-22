## Context

`public_results_preview` (`survey/public_results_editor.py:126`) is decorated with
`@survey_permission_required('editor')`. That decorator (`survey/permissions.py:108`) rejects every
non-editor before the view body runs, in two different ways:

- anonymous → `redirect('login')`, discarding the requested path;
- authenticated but outside the survey's active organization → `raise Http404`.

Both are correct for an editor endpoint. The problem is that this particular URL escapes into the
wild: it is what a creator sees in the address bar while configuring the results page, and it is
what they copy when they want to share results. The public destination `/r/<slug>/`
(`survey/views.py:1420`) exists and works, but nothing connects the two.

Constraints the design has to respect:

- `/r/<slug>/` serves a page only when `is_published=True`; `unlisted` pages are reachable there but
  carry `noindex`. The fallback must not become a way to reach an unpublished page.
- `_get_or_create_page` **creates** a `PublicResultsPage` row as a side effect. It must not be
  called on a path an anonymous visitor can trigger.
- The preview is also loaded inside an iframe in the editor (`public_results.html:241`) under
  `@xframe_options_sameorigin`. That path belongs to the owner and must keep working unchanged.
- Merges reach production within minutes and there is no staging gate, so a behavioural change on a
  public URL needs a kill switch.

## Goals / Non-Goals

**Goals:**
- A visitor following a shared preview link reaches the published results page instead of a login
  wall or a 404.
- A visitor who does end up at the login page returns to where they were headed after signing in.
- Creators have an obvious "copy the public link" action, so the address bar stops being the
  shareable-link source.
- The change is reversible from the Render dashboard without a deploy.

**Non-Goals:**
- Changing who may view a results page. Publication state and `visibility` semantics are untouched.
- Making the preview URL itself publicly renderable — it stays editor-only; it merely forwards.
- Retroactively cleaning up the accounts this trap already created. They are real rows with real
  consent records; deleting them is a separate decision.
- Rewriting the registration redirect to `/editor/surveys/new/?welcome=1`. That destination is right
  for actual creators; the bug is that non-creators were funnelled into registration at all.

## Decisions

### 1. Handle the fallback inside the view, not inside the decorator

`public_results_preview` drops `@survey_permission_required('editor')` and performs its own check
using the existing helpers `get_effective_survey_role` and `_check_survey_role`. On denial it looks
for a published `PublicResultsPage` and redirects to it; if there is none, it reproduces the
decorator's original outcome (anonymous → login, otherwise → 404).

*Alternative considered*: add a `fallback=` hook to `survey_permission_required`. Rejected — the
decorator guards roughly forty editor endpoints, and a general-purpose escape hatch on a permission
primitive is exactly the kind of thing that later gets used somewhere it shouldn't. One view needs
this behaviour; the exception belongs in that view.

*Alternative considered*: a middleware or a custom 404 handler that pattern-matches editor URLs and
looks for a results page. Rejected — it puts survey routing logic in the error path, where it is
invisible during review and fires for genuine 404s too.

Because the decorator is removed, the view becomes responsible for the checks the decorator used to
guarantee: trashed surveys (`deleted_at`) must stay excluded, and the survey must be looked up by
UUID exactly as before. This is the main correctness risk in the change and needs explicit tests
rather than trust.

### 2. Redirect only when a published page exists

The fallback fires when `PublicResultsPage.objects.filter(survey=survey, is_published=True)` returns
a row — reading only, never `_get_or_create_page`. `visibility` is deliberately not consulted: an
`unlisted` page is one the creator chose to hand out by link, which is precisely the situation being
rescued, and `/r/<slug>/` already serves it. Unpublished → previous behaviour, unchanged.

### 3. `?next=` via `redirect_to_login`

`survey_permission_required` replaces `redirect('login')` with
`django.contrib.auth.views.redirect_to_login(request.get_full_path())`. Django's login view already
validates `next` against allowed hosts, so this introduces no open-redirect surface. This is a
whole-editor improvement and is in scope because the same missing `?next=` is what turned a wrong
link into a registration.

### 4. Kill switch

`PUBLIC_RESULTS_PREVIEW_FALLBACK` (default `True`) gates decision 2 only. Off = the pre-change
denial behaviour, so a bad interaction can be reverted from Render without a deploy. The `?next=`
change and the editor UI are not gated: neither can produce a worse outcome than the current state.

### 5. Editor affordance

`_survey_nav_tabs.html` and `public_results.html` get a copy-to-clipboard control showing the
`/r/<slug>/` URL, using the existing `editor_clipboard.js`. The current "Preview" link is relabelled
so it no longer reads as the shareable artifact. The copy control appears only when the page is
published — offering a link that 404s would recreate the same class of problem.

### 6. Branded, context-aware 404

The denial branch (decision 1) ends in `404` for a signed-in outsider when nothing is published, and plain survey-not-found (`/surveys/<name>/`, `/r/<slug>/` for a deleted or unpublished survey) already 404s. Django serves its default server page there. Add `survey/templates/404.html` — with `APP_DIRS=True` and `DEBUG=False` Django picks it up automatically, no `handler404` wiring needed.

The template branches on `request.path` (available because `django.template.context_processors.request` is enabled): paths under `/surveys/`, `/r/`, `/editor/surveys/` get copy naming the likely causes — not published yet, deleted, or wrong link — while every other path gets generic wording. A single global template with survey copy would mislabel a mistyped landing URL as a missing survey; branching keeps the survey message where it belongs.

The page is **standalone** — it does not extend `base_landing.html`. Everything (styles, wordmark) is inline, with no `{% static %}` assets, no site nav, and no footer. A 404 must render correctly precisely when something is wrong, including when the marketing CSS pipeline is unavailable; embedding the landing chrome makes the error page depend on the same static assets whose absence it might be reporting. (Observed during review: a `DEBUG=False` preview served the landing template with its hashed CSS 404ing, leaving the page unstyled.) Self-contained also matches how GitHub and similar sites present 404s — a focused page, not the full site shell.

*Alternative considered*: a custom `handler404` view that classifies the path in Python. Rejected — the template already has `request`, and a view adds a URLconf entry and a code path that only formats a string. If the branching ever grows beyond a prefix check, revisit.

## Risks / Trade-offs

- **Removing the decorator silently drops a guard** (trashed-survey exclusion, org scoping) →
  tests assert each dropped guard individually, including a trashed survey with a published results
  page, which must not redirect.
- **A visitor now learns that a survey exists** where they previously got a 404 → the redirect only
  ever points at a page the creator published for public consumption, so nothing is disclosed that
  `/r/<slug>/` does not already disclose to anyone with the slug.
- **Registration counts drop after release** and could read as a traffic regression → the drop is
  the fix working. Note the release date when reading the funnel dashboard; `signup-attribution`
  rows for these visitors currently carry `raw_referrer` of `mapsurvey.org/accounts/register/`.
- **The iframe preview breaks for the owner** if the permission check is subtly different from the
  decorator's → the owner path is exercised by an explicit test asserting a `200` and the preview
  template, not merely "not a redirect".
- **Trade-off: the preview URL keeps two behaviours** (render for editors, forward for everyone
  else) and is therefore harder to reason about than a single-purpose endpoint. Accepted: the
  alternative is asking every creator who already shared the link to re-share it.

## Migration Plan

No migration, no model change. Deploy is a plain merge to `master`.

Rollback: set `PUBLIC_RESULTS_PREVIEW_FALLBACK=False` on the `mapsurvey` service — this restores the
current denial behaviour without reverting the commit. Full revert is a normal git revert; nothing
persists state that would survive it.

Post-release check: request the `Sótão` preview URL as a signed-out client and confirm a `302` to
`/r/sotao/`. That is the exact URL known to be in circulation.

## Open Questions

- Should the redirect carry a marker (e.g. `?from=preview`) so we can count how often shared preview
  links are still being followed? It would quantify how widespread the mis-sharing is beyond this one
  creator, at the cost of an uglier URL. Leaning yes, as a `SurveyEvent`-side metric rather than a
  query parameter.
- Should `Skelozard` be told his shared link was broken and given the right one? Product/outreach
  call, not a code change — but the survey has 106 responses and an audience that is still arriving.
