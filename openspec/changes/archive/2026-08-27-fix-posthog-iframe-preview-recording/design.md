# Design

## Context

`survey.context_processors._posthog_key_for` decides whether a page gets the PostHog snippet. It
answers one question — "is this our audience?" — with one test: does the path start with a prefix
in `POSTHOG_EXCLUDED_PREFIXES` (`/surveys/`, `/r/`).

That test is a proxy for the real rule, and the proxy breaks on the editor's preview iframes. They
serve genuine respondent surfaces — `editor_section_preview` renders `survey_section.html`, which
extends `base_survey_template.html`; `editor_survey_thanks_preview` renders `survey_thanks.html`,
which extends `base.html` — but their URLs live under `/editor/`, where we deliberately do want
tracking. No prefix separates the two.

Measured on production over the seven days to 2026-08-27: 1169 of 1799 `$pageview` events under
`/editor/` come from `.../preview/...` paths, at an average viewport width of 472px against 1616px
for real editor pages. The narrow stream is the iframe; it lands in the same session as the page
that frames it.

Two other preview surfaces were checked and are already clean, which is why they appear nowhere
below: `editor_question_preview_live` renders the standalone `question_preview_frame.html`, and
`public_results_preview` renders the standalone `public_results.html`. Neither extends a base
template, so neither includes `partials/_analytics.html`.

## Goals / Non-Goals

**Goals**

- A preview iframe starts no PostHog client: no session recording stream, no page view, no
  identify.
- The editor page that frames the preview keeps everything it records today.
- A preview surface added later is excluded by default rather than by its author remembering.

**Non-Goals**

- Correcting the data already collected. Mixed recordings and inflated `$pageview` rows stay as
  they are; this change only stops new ones.
- Touching Plausible, server-side error capture, or `SurveyEvent`/`TrackedLink` — the
  customer-facing analytics that measure respondents on the customer's behalf.
- Reworking `POSTHOG_EXCLUDED_PREFIXES`. The prefix test is correct for what it covers; this adds
  a second test beside it.

## Decisions

### D1: Exclude by resolved view name, not by path

`POSTHOG_EXCLUDED_VIEW_NAMES` holds `('editor_section_preview', 'editor_survey_thanks_preview')`,
read in `_posthog_key_for` from `request.resolver_match.url_name`.

*Why not a path pattern.* `/editor/surveys/<uuid>/preview/<section>/` could be matched with a
regex, but the segment `preview` is not reserved: `/editor/surveys/<uuid>/public-results/preview/`
already exists and is a different surface, and a future `/editor/surveys/<uuid>/preview-settings/`
would silently lose tracking. The view name is the identity Django itself uses, and it changes
only when someone edits `urls.py` — where the list is easy to find.

*Why not a flag passed from the view.* The exclusion must hold for templates nobody edits when
adding a surface; putting it in the view means every new preview view re-decides it. The whole
reason the prefix test lives in the context processor (see `settings.py`) applies unchanged.

*Failure mode.* `request.resolver_match` is `None` before URL resolution — an error page rendered
by middleware, for instance. Treat that as "not excluded": tracking a page we meant to track is
the recoverable direction, silently losing the editor is not.

### D2: A framed document initialises nothing

`_analytics.html` wraps `posthog.init(...)` in `if (window.top === window.self)`.

This is a belt, not the mechanism. D1 is what fixes today's two URLs; D2 is what makes the class
of bug non-recurring, because it does not depend on anyone maintaining a list. It is also strictly
correct on its own terms: a framed document never has an independent session to record, so a
second client in the same tab is never what we want.

The guard sits around `init`, not around the whole snippet. The stub loader still runs, so
`window.posthog` exists and any `posthog.capture(...)` a page makes degrades to a queued no-op
rather than a `ReferenceError`. `survey/assets/js/` already guards its capture calls on
`window.posthog` being present, and this keeps that contract true.

*Cross-origin note.* Reading `window.top === window.self` never throws — only reaching into
`window.top`'s document does. No try/catch needed.

### D3: Keep returning an empty key

`_posthog_key_for` already expresses "not our page" as an empty key, so one `{% if %}` in the
template covers both "unconfigured" and "excluded". The new test returns the same way. This keeps
the assertion available to tests unchanged: an excluded response contains no project key anywhere.

## Risks / Trade-offs

- **Editor page views drop ~3x after deploy.** This will look like a traffic regression on the
  PostHog dashboards, and the drop lands mid-series with no annotation. Mitigation: the tasks
  include a PostHog annotation on deploy day, so whoever reads the chart next month sees why.
- **The view-name list can go stale.** If `urls.py` renames `editor_section_preview`, the
  exclusion stops applying and nothing fails loudly. D2 catches it in the browser, and the test
  added in this change reverses the URL by name, so a rename that misses the setting fails the
  suite rather than the dashboards.
- **D2 changes behaviour for every framed page, not just previews.** Deliberate. We have no
  surface that is meant to be measured while framed.

## Migration Plan

Single deploy, no data migration, no kill switch. The change only removes tracking from surfaces
that should never have had it; the rollback is a revert. `POSTHOG_EXCLUDED_VIEW_NAMES` is a
constant in `settings.py` rather than an environment variable, matching
`POSTHOG_EXCLUDED_PREFIXES` — the respondent boundary is not an operational dial.

## Open Questions

None.
