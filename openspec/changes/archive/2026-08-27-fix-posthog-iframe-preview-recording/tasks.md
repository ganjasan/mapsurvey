## 1. Server-side exclusion (D1)

- [x] 1.1 Add `POSTHOG_EXCLUDED_VIEW_NAMES = ('editor_section_preview', 'editor_survey_thanks_preview')` to `mapsurvey/settings.py`, directly below `POSTHOG_EXCLUDED_PREFIXES`, with a comment saying why a view name and not a path prefix (`/editor/surveys/<uuid>/public-results/preview/` is a different surface).
- [x] 1.2 In `survey/context_processors._posthog_key_for`, return `''` when `request.resolver_match.url_name` is in the new setting; treat a missing `resolver_match` as not excluded.

## 2. Client-side belt (D2)

- [x] 2.1 In `survey/templates/partials/_analytics.html`, wrap the `posthog.init(...)` block (and the identify call that follows it) in `if (window.top === window.self)`, leaving the stub loader outside the guard so `window.posthog` still exists for the guarded `posthog.capture` calls elsewhere.
- [x] 2.2 Comment the guard with what it defends against — a second recorder in one tab writing into one session — so it is not "simplified" away later.

## 3. Tests

- [x] 3.1 Test: with a project key configured, `GET` on `reverse('editor_section_preview', ...)` renders no PostHog key. Reverse by name so a rename in `urls.py` that misses the setting fails here.
- [x] 3.2 Test: same for `reverse('editor_survey_thanks_preview', ...)`.
- [x] 3.3 Test: the editor page that frames the preview still renders the key (guards against over-broad exclusion).
- [x] 3.4 Test: the rendered snippet contains the framed-document guard, so removing it fails the suite.
- [x] 3.5 Confirm the existing PostHog tests (`/surveys/`, `/r/`, unconfigured key, identify) still pass unchanged.

## 4. Documentation

- [x] 4.1 Update the PostHog section of `CLAUDE.md`: the respondent-boundary rule now has two enforcement points — path prefix and view name — and the editor preview iframes are named as the case the prefix cannot express.

## 5. Verification

- [x] 5.1 `./run_tests.sh survey`: 1604 tests, OK (skipped=1), 869s. Baseline was the same suite minus the 4 tests added here; no pre-existing test changed behaviour.
- [x] 5.2 Browser check: the top-level document loads `array.js` and initialises PostHog; both nested iframes load no PostHog script and report `__loaded: false`. Run on public pages rather than the editor — the browser extension blocks setting a session cookie and typing a password into a field is out of bounds, so the editor-side exclusion is covered by tasks 3.1-3.3 instead.
- [x] 5.3 PostHog annotation 112344 created 2026-08-27, project scope, marker at the merge time (06:59:31Z), noting the ~3x drop in editor `$pageview` counts is measurement error going away.
