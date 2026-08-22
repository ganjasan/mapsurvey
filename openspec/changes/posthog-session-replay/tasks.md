## 1. The switch

- [x] 1.1 Add `POSTHOG_SESSION_REPLAY` to `mapsurvey/settings.py`, read from the environment,
      defaulting to off; comment why the emergency stop must not need a deploy (mounted disk, one
      instance, no zero-downtime deploys) and why a fork must not inherit our recording posture
- [x] 1.2 Publish it through `survey.context_processors.analytics` alongside the existing PostHog
      context

## 2. Snippet

- [x] 2.1 In `_analytics.html`, make `disable_session_recording` follow the setting instead of being
      hardcoded `true`
- [x] 2.2 Add the `session_recording` config with `maskAllInputs: true`; do not add
      `maskTextSelector: '*'` — grey rectangles cannot answer "which control did they hunt for", and
      the intended line is *what the user typed* vs *what the product showed*
- [x] 2.3 Comment the masking decision in the template, so a later "make replays more useful" edit
      has to argue with a stated policy rather than an unexplained flag. Note the comment must not
      name the text-masking option literally: the test asserts that option appears nowhere in the
      response, and a JS comment inside `<script>` is part of the response — caught by the test on
      the first run

## 3. Trust page

- [x] 3.1 Add the recording disclosure to `survey/templates/trust.html`: editor sessions recorded,
      typed content masked, 30-day retention, respondents never recorded
- [x] 3.2 Run the template-comment guard test immediately after editing — `{# #}` is single-line

## 4. Tests

- [x] 4.1 Recording disabled by default: the rendered snippet disables session recording when the
      setting is unset
- [x] 4.2 Recording enabled: the snippet stops disabling it and carries `maskAllInputs`
- [x] 4.3 Recorded request URLs are stripped of their query string, and neither request bodies nor
      headers are enabled
- [x] 4.4 `/surveys/` and `/r/` carry no snippet and no recording config with recording enabled
- [x] 4.5 Trust-page assertions for all four disclosure claims
- [x] 4.6 Run the full suite and record the delta against the pre-change baseline — 1273 tests,
      OK (1 skipped), up from 1248 before this change and no failures introduced

## 5. PostHog project settings (dashboard or MCP — after the code is deployed)

- [ ] 5.1 `session_recording_opt_in: true`
- [ ] 5.2 `session_recording_url_trigger_config` → `/editor/`, so marketing visitors are never
      recorded (the respondent boundary is the snippet exclusion, not this)
- [ ] 5.3 `session_recording_sample_rate: 1.00` — no sampling; at ~12 active people a sample means
      waiting weeks to see the behaviour we are trying to explain
- [ ] 5.4 `session_recording_masking_config` — mirror the client policy server-side
- [ ] 5.5 `session_recording_retention_period: 30d`
- [ ] 5.6 `recording_domains` → the production origin, so a fork or preview holding a real key
      cannot record into the production project
- [x] 5.7 Leave `capture_console_log_opt_in` and `capture_performance_opt_in` ON — both already are.
      Verified rather than assumed: our frontend logs nothing but a clipboard failure, the recorder
      defaults `recordBody`/`recordHeaders` to false, and the one real leak (place search sending
      `?q=<typed text>`) is closed client-side by `maskRequestFn`

## 6. Enable and verify

- [ ] 6.1 Deploy with `POSTHOG_SESSION_REPLAY` unset — a no-op by construction
- [ ] 6.2 Set `POSTHOG_SESSION_REPLAY=True` on the Render web service (the worker renders no
      templates and does not need it)
- [ ] 6.3 Open the editor as a real creator, then confirm a recording exists in PostHog
- [ ] 6.4 Watch that recording and confirm typed text plays back masked — this is the check that
      the whole privacy story rests on, and it cannot be done from the config alone
- [ ] 6.5 Visit a survey page under `/surveys/` and confirm no recording is produced
- [ ] 6.6 Visit a marketing page and confirm no recording is produced (URL trigger holding)
- [ ] 6.7 Judge whether masked playback is actually readable. If it is not, the fix is per-selector
      unmasking of specific non-personal fields, never `maskAllInputs: false`

## 7. Use it

- [ ] 7.1 Watch the sessions behind the existing `$dead_click` and `$rageclick` events — 15 of them
      as of 2026-08-17, each already a flagged "clicked and nothing happened"
- [ ] 7.2 Write down what was found as backlog items, one per stuck point, rather than leaving it in
      a recording nobody re-watches
- [ ] 7.3 Separately from replay: build a heatmap over `/editor/` from the autocapture data already
      being collected, which is the cheaper half of "used the feature or never found it"
