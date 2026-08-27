## Why

The editor's Live preview panel loads a real respondent page inside an `<iframe>`, and that page
carries the PostHog snippet: `/editor/surveys/<uuid>/preview/<section>/` renders
`survey_section.html` → `base_survey_template.html`, which includes `partials/_analytics.html`.
`POSTHOG_EXCLUDED_PREFIXES` does not catch it — the path begins with `/editor/`, not `/surveys/`.
The same holds for `/editor/surveys/<uuid>/thanks-preview/`.

So one browser tab runs two PostHog clients writing into one session. Two consequences, measured
over the seven days to 2026-08-27:

- **Session replay is unwatchable.** The iframe's recorder emits its own viewport (avg 472px,
  as narrow as 0px when the pane is collapsed) into the same recording as the editor's (avg
  1616px). The player interleaves both streams, so the recording flips between the mobile and
  the desktop layout every few seconds. The mobile editor work did not cause this — it made an
  always-present defect visible, because at 380px the respondent page now looks decisively
  different from the same page in a wide pane.
- **Editor usage numbers are inflated by ~3x.** 1169 of 1799 `$pageview` events under `/editor/`
  are iframe loads, not people. Every keystroke-triggered preview refresh counts as a page view,
  and the narrow viewport makes them look like mobile creators in web analytics.

## What Changes

- The PostHog snippet stops rendering on the editor's preview surfaces
  (`editor_section_preview`, `editor_survey_thanks_preview`). They are respondent surfaces shown
  to a creator; the existing rule that respondent surfaces are never tracked already covers them
  in spirit, only the path-prefix test misses them.
- The exclusion is keyed on the resolved view name rather than a path prefix, because these URLs
  are nested under `/editor/` and no prefix can separate them from the editor pages we do want to
  measure.
- A client-side belt: `_analytics.html` does not initialise PostHog when the document is framed
  (`window.top !== window.self`). This catches any preview surface added later whose author does
  not know about the view-name list.
- No change to what the top-level editor records, to Plausible, or to error capture.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `product-analytics`: adds a requirement that the editor's preview iframes are excluded from
  tracking, alongside the existing path-prefix exclusion of respondent surfaces.

## Impact

- `survey/context_processors.py` — `analytics()` gains a view-name test next to the prefix test.
- `mapsurvey/settings.py` — new `POSTHOG_EXCLUDED_VIEW_NAMES` setting next to
  `POSTHOG_EXCLUDED_PREFIXES`.
- `survey/templates/partials/_analytics.html` — framed-document guard around `posthog.init()`.
- `survey/tests.py` — coverage for both preview URLs and for the top-level editor page staying
  tracked.
- Historical data is not corrected: recordings and `$pageview` rows already collected keep the
  mixed streams. Editor pageview counts will drop sharply after deploy; that drop is the
  measurement error going away, not a usage regression.
