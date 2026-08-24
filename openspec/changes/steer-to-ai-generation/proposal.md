## Why

The create page's AI draft is the intended primary path, but it competes with a
zero-effort "Create empty" button while asking the creator to fill a four-field brief —
classic blank-page cost, and the cheapest click wins. First-week telemetry after the AI
launch (12 AI vs 2 manual creations, then a weekend of manual-only) is too small to call
a trend, but the asymmetry is structural: skipping AI costs one click, using it costs a
paragraph. On mobile the wizard makes it worse in the other direction — a creator who has
already chosen "Skip and start from scratch" is still forced through the "Where?" map step
they didn't ask for. And we cannot currently distinguish "saw the AI panel and skipped it"
from "never reached the create page", so steering effects are unmeasurable.

## What Changes

- **Empty-path intercept**: when the goal field is non-empty and the creator clicks
  "Create empty" (desktop) or "Skip and start from scratch" (wizard step 1), show a soft
  inline prompt — "You already described your project — draft it with AI (~10 s)?" — with
  "Generate draft" and "Create empty anyway". Shown at most once per page load; declining
  proceeds to the empty path with no further friction. With a blank goal nothing changes.
- **Single-field brief**: the goal textarea (autofocused) becomes the whole visible brief;
  audience, map target, and use-case chips collapse under an "Add details (optional)"
  disclosure, expanded automatically when any of them already carries a value.
- **Mobile wizard: empty path skips the map step**: choosing "Skip and start from scratch"
  on wizard step 1 submits the empty creation immediately (default map framing) and lands
  in the editor, instead of continuing to the "Where?" step. The draft path keeps the
  map step unchanged.
- **Instrumentation**: emit intercept funnel events (shown / accepted / declined) so the
  steering can be judged against `ai_draft_requested` and `survey_created`
  (`creation_method`) instead of anecdote. Page reach keeps riding the existing
  `$pageview` on `/editor/surveys/new/`.
- **Kill switch**: the intercept and brief collapse ship behind one env-var flag
  (default on) — merges reach production in minutes and this page is the top of the
  registration-to-survey funnel.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-survey-generation`: the "AI brief panel on the create page" requirement changes —
  the panel presents a single goal field with the remaining brief fields behind an
  optional disclosure, and the "Create empty path remains behaviorally unchanged in all
  cases" clause is amended: with a filled goal the empty action first shows a dismissible
  inline offer to generate (decline proceeds empty; blank goal stays unchanged).
- `survey-editor`: the "Survey creation" requirement changes — on the mobile wizard the
  empty action on step 1 creates the survey directly with the default map framing and
  redirects to the editor, bypassing the map step.
- `creator-funnel-events`: adds the intercept events (shown / accepted / declined) with
  the surface (desktop / wizard) as a property; brief content itself is never sent.

## Impact

- `survey/templates/editor/survey_create.html` — intercept UI + JS, disclosure markup,
  wizard step-1 empty submit, autofocus.
- `survey/assets/css/editor-mobile.css` (or the page's inline styles) — disclosure and
  intercept styling in both layouts.
- `mapsurvey/settings.py` + context processor — the kill-switch env var.
- PostHog capture (client-side, editor surface only) for the intercept events; no change
  to the customer-facing `SurveyEvent` system.
- `survey/tests.py` — create-page rendering tests, wizard-path tests, guard tests for the
  flag-off state. Existing "Create empty works with an untouched brief" tests must keep
  passing (blank goal ⇒ no intercept).
- No model or migration changes. Server-side create/generate endpoints unchanged except
  possibly reading the flag.
