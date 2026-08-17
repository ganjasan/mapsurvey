# Watch the editor being used, without watching what gets typed into it

## Why

We know creators leak out of the editor and we do not know where. `survey/funnel.py` says 53% of
registrations ever create a survey and 38% ever add a question; it cannot say what the other half
saw before they left. The evidence we do have is all indirect and arrived late: a creator copied 12
blocks by hand and cut 9 versions in a day and we found it by reading survey structure, and a lead
logged in and deleted their map 13 seconds later, visible only in Render's request log.

The second question is narrower and cheaper: do creators *use* the features, or do they not *find*
them. Autocapture already answers part of it — clicks are being recorded, and PostHog has flagged 12
`$dead_click` and 3 `$rageclick` events in two days, which is literally "clicked something that did
nothing" and "clicked angrily". What the click stream cannot tell us is what the person was trying
to do at the time. That is what replay is for.

The decisive fact is scale. Over the last 30 days — PostHog has only been live for two of them —
there are 121 `$pageview` events from 12 people and 307 `$autocapture` events from 9. At that volume
a recording is not a data-mining problem, it is a handful of sessions a day that a human can watch
end to end. Sampling and clever trigger arithmetic exist to solve a volume problem we do not have.

Recording was left off deliberately in `posthog-internal-analytics`: it needs a masking policy and a
reviewed privacy statement. This change is those two things, plus the switch.

## What Changes

- **Recording enabled on our own surfaces only.** The snippet stops passing
  `disable_session_recording: true`. `POSTHOG_EXCLUDED_PREFIXES` already keeps the snippet off
  `/surveys/` and `/r/`, so no respondent can be recorded — that boundary is unchanged and is what
  makes this proposal defensible at all.
- **Recording is scoped to the editor by URL trigger, not by sampling.** Marketing pages are
  answered by Plausible and by `$pageview`; recording anonymous landing visitors would collect video
  of people we have no relationship with, to answer a question we are not asking. 100% of editor
  sessions, 0% of everything else.
- **Everything typed is masked by default.** `maskAllInputs` on, so field *contents* never leave the
  browser — question wording, respondent-facing text, organisation names, email addresses in account
  forms. Interface text stays visible, which is what makes a recording readable: we need to see
  which control someone hunted for, not what they wrote in it.
- **Console logs and recorded requests stay on, with one hole plugged.** Both were initially going
  to be switched off as "side channels", and that was checked rather than assumed: our entire
  frontend contains one `console.error` about a failed clipboard write, and the recorder's own
  defaults keep request bodies and headers off, so what is captured is a URL and its timings. A
  console error is usually the answer to "clicked and nothing happened", which is the question
  being asked. The single genuine leak is ours — `map_place_search.js` sends what the creator typed
  as `?q=...`, so a masked field would reappear inside a recorded request URL — and it is closed by
  a `maskRequestFn` that strips the query string from every recorded request.
- **Recording is pinned to our origin.** `recording_domains` set to the production host, so a fork,
  a local checkout or a PR preview running with a real key cannot start recording.
- **A defined retention.** 30 days — the shortest PostHog offers, and long enough for the question
  ("where did creators get stuck this month") that motivates the change.
- **`/trust/` says that we record editor sessions**, what is masked, how long recordings are kept,
  and that respondents are never recorded. A page that describes analytics but omits screen
  recording is worse than one that never mentioned analytics.

## Capabilities

### New Capabilities

- `session-replay`: when the browser records a session, what is masked, which surfaces are eligible,
  how long recordings live, and what the trust page must say about all of it.

## Impact

**Code**

- `survey/templates/partials/_analytics.html` — drop `disable_session_recording`, add the
  `session_recording` masking config
- `mapsurvey/settings.py` / `survey/context_processors.py` — a setting gating recording, so it can
  be turned off without a deploy and stays off wherever the key is absent
- `survey/templates/trust.html` — the disclosure
- `survey/tests.py` — masking present, recording absent on respondent surfaces, disclosure present

**PostHog project settings (dashboard or MCP, not the repo)**

- `session_recording_opt_in: true`
- `session_recording_url_trigger_config` → `/editor/`
- `session_recording_sample_rate: 1.00`
- `session_recording_masking_config` — server-side mirror of the client masking policy
- `session_recording_retention_period: 30d`
- `recording_domains` → the production origin
- `capture_console_log_opt_in` and `capture_performance_opt_in` stay `true` (already are)

**Not affected**

- Respondents. The snippet does not load on `/surveys/` or `/r/`, so there is nothing to record
  there — and this change does not touch `POSTHOG_EXCLUDED_PREFIXES`.
- `SurveyEvent` / `TrackedLink` / `PerformanceAnalyticsService`, as ever.
- The reverse proxy from `posthog-reverse-proxy`: recordings ride the same first-party host, which
  is a side benefit — replay payloads are large and are exactly what a blocker would drop.

## Risk

Recording is the most invasive thing we have ever pointed at a user, and the users here are our own
customers. Three things keep it proportionate: it is off where respondents are, it captures no typed
content, and it is disclosed on the page we send security teams to. If any of those three stops
being true, the feature should be turned off rather than renegotiated — hence the setting that
disables it without a deploy.
