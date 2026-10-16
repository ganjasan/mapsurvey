## Why

Creator pages give no sign that a click registered: no progress indicator while the next page
loads and no busy state on buttons. PostHog (30 days) puts the p75 largest contentful paint of
Responses at 3.0 s and p90 at 4.3 s, Create at 2.1 s / 2.8 s, Build at 1.5 s / 2.1 s; one in four
Responses opens waits over 3 s looking at an unchanged page. Session replays show people
clicking again — the same form submitted several times, the same button pressed repeatedly —
which is the direct cost of the silence (issue #337).

## What Changes

- A thin top progress bar on every creator page built on `base.html` or
  `editor/editor_base.html`: shown ~150 ms after a same-origin link click or a native form
  submit, so fast navigations show nothing; shown for HTMX requests that run longer than
  ~300 ms (polling requests excluded); finished when the page unloads or the HTMX request
  completes, including on error.
- A submit button that sends a request (native form submit or HTMX submit) is disabled at once
  and shows a busy state (spinner in place of its icon, `aria-busy`), so the same form cannot be
  sent twice from the keyboard or the mouse. A second native submit of the same form while the
  first is in flight is suppressed. The button is restored when the HTMX request finishes or
  the page is restored from the back/forward cache.
- One shared partial (`partials/_loading_feedback.html`) carrying one stylesheet and one script
  (`js/loading_feedback.js`), included by the two creator base templates; no per-page code.
  The script exposes `window.LoadingFeedback` (`start`, `done`, `busy(button)`) for the few
  JS call sites that drive their own `fetch`.
- A template hygiene test pins the contract: both creator bases include the partial, the
  respondent base (`base_survey_template.html`) and the marketing base do not.
- An in-app changelog entry announces the bar.

Out of scope: respondent pages (`/surveys/`, `/r/`), the marketing site, and the AI drafting
wait, which has its own progress screen.

## Capabilities

### New Capabilities
- `creator-loading-feedback`: the top progress bar and submit-button busy state on creator
  pages — when they appear, when they do not, how they end.

### Modified Capabilities
<!-- none: no existing requirement changes -->

## Impact

- `survey/templates/base.html`, `survey/templates/editor/editor_base.html`: one include each.
- New: `survey/templates/partials/_loading_feedback.html`,
  `survey/assets/js/loading_feedback.js`, `survey/assets/css/loading-feedback.css`.
- New `survey/changelog/2026-10-15-visible-loading-bar.html`.
- Tests in `survey/tests.py` (`LoadingFeedbackTest`, SimpleTestCase over the template and
  static sources, in the style of `HtmxPromiseGuardTest`).
- No model, URL, settings or dependency changes. Works with and without HTMX on the page
  (the dashboard loads HTMX itself, the auth pages load none).
