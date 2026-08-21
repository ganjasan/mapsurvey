# Tasks

## 1. Implementation

- [x] 1.1 Add `POSTHOG_BOT_UA_MARKERS` and the bot branch to `_posthog_skip_request` in `mapsurvey/settings.py`
- [x] 1.2 Add filter tests to `PostHogErrorTrackingTest` in `survey/tests.py` (bot UA excluded, empty UA excluded, browser UA still tracked)

## 2. Verification

- [x] 2.1 Run the PostHog test class and the full survey suite once (16/16, then 1372 OK, 1 skipped)
