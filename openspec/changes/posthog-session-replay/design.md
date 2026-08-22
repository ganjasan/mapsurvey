## Context

Session replay is configured in two places at once, and getting the split wrong is the main way this
lands badly:

- **The client** (`survey/templates/partials/_analytics.html`) decides whether recording is possible
  at all and what is masked before anything leaves the browser. Today it passes
  `disable_session_recording: true`, which overrides every server-side setting — this is why the
  replay-triggers page in the PostHog dashboard currently has no effect whatsoever.
- **The project settings** decide whether recording is switched on, where it starts, how long
  recordings are kept, and which origins may record at all.

Masking has to happen client-side to mean anything: a server-side masking rule is a promise about
what PostHog does with data it already received, whereas `maskAllInputs` means the characters never
leave the browser. For a page whose selling point is that its claims are checkable, only the second
kind is worth writing down.

Verified against the current project (not assumed):

- 30-day volume: 121 `$pageview` from 12 people, 307 `$autocapture` from 9, 12 `$dead_click`,
  3 `$rageclick`. PostHog has been live for two of those days.
- The settings API exposes `session_recording_opt_in`, `session_recording_url_trigger_config`,
  `session_recording_masking_config`, `session_recording_sample_rate`,
  `session_recording_retention_period` (`30d`/`90d`/`1y`/`5y`), `recording_domains`,
  `capture_console_log_opt_in` and `capture_performance_opt_in`.
- The snippet loads on our surfaces only; `POSTHOG_EXCLUDED_PREFIXES` (`/surveys/`, `/r/`) is
  enforced in the context processor.

## Goals / Non-Goals

**Goals:**

- See where creators stall in the editor, with enough context to tell "did not find it" from
  "found it and it did not work".
- Record nothing that a creator typed.
- Make the whole thing switchable off without a deploy.
- Keep `/trust/` an accurate description of the product after the change, not before it.

**Non-Goals:**

- Recording respondents. Not now, not behind a flag.
- Recording anonymous marketing traffic.
- Sampling, minimum durations, or event-trigger arithmetic — all are answers to a volume problem
  that does not exist at 12 people a month.
- Replacing autocapture analysis. Heatmaps and `$dead_click` answer "is this control ever used" far
  more cheaply than watching video, and they keep working whether or not this ships.

## Decisions

### 1. A `POSTHOG_SESSION_REPLAY` setting, defaulting off

Recording becomes possible only when the setting is truthy *and* a project key exists. Two reasons
to spend a setting on this rather than hardcoding it: the emergency stop must not require a deploy
(and this deployment's deploys are not zero-downtime — a mounted disk and one instance), and a
self-hosted or forked install must not inherit our recording posture from our source.

Rejected: relying on `session_recording_opt_in` in the PostHog project alone. That switch lives in a
dashboard nobody reviews and is invisible to anyone reading the repository — including a
self-hoster, and including us in six months.

### 2. Masking policy: all inputs, query strings stripped, console kept

`maskAllInputs: true` in the client's `session_recording` config. Field contents never leave the
browser: question wording, section names, organisation names, and the email address on account
forms.

Interface text stays unmasked. Masking everything (`maskTextSelector: '*'`) produces a video of grey
rectangles moving around, which cannot answer "which control did they hunt for" — the question the
recording exists for. The line is therefore *what the user typed* versus *what the product showed*,
which is also the line that matters for personal data: our chrome is the same for everyone, their
text is theirs.

`capture_console_log_opt_in` and `capture_performance_opt_in` stay **on**. The first draft of this
design turned them off as "side channels", which did not survive checking:

- The whole frontend contains exactly one console call — `console.error('Clipboard write failed', e)`
  in `editor_clipboard.js`. We log no user content anywhere. What the console does carry is other
  people's errors (Leaflet, our own code when it throws), and a console error is usually the answer
  to "clicked and nothing happened" — the exact question `$dead_click` raises and replay is meant to
  settle.
- "Network payloads" conflated two different settings. Reading the shipped recorder bundle, its
  defaults are `recordHeaders: false` and `recordBody: false`; bodies are a separate project setting
  (`session_recording_network_payload_capture_config`, currently null). What performance capture
  records is the request URL and its timings.

That leaves one real leak, and it is ours rather than PostHog's: `map_place_search.js` builds its
request as `'q=' + encodeURIComponent(query)`, so the text a creator typed into the place search —
masked in the replay itself — would ride along intact inside a recorded request URL. The same bundle
exposes `maskRequestFn`, called for every captured request, where a falsy return drops the request
and any returned object is what gets stored. Stripping the query string there closes the leak
without giving up the timings:

```js
maskRequestFn: function (request) {
    request.name = String(request.name || '').split('?')[0];
    return request;
}
```

Turning both channels off would have been the easier decision and the worse one: it costs the most
useful diagnostic signal to avoid a leak that is one line to close.

### 3. Scope by URL trigger, not by sampling

`session_recording_url_trigger_config` matches `/editor/`. Recording starts when a creator reaches
the editor and does not start anywhere else, so marketing visitors — mostly anonymous people with no
relationship to us — are never recorded.

Rejected: `sample_rate < 1`. Sampling exists to control volume, and there is no volume. At a handful
of sessions a day, a 10% sample means waiting weeks to see a single instance of the behaviour we are
trying to explain.

Rejected: an event trigger such as "record only sessions that fire `$rageclick`". Tempting, but it
can only start the recording once the problem has already happened, and the interesting part is the
thirty seconds before.

Note the redundancy with the snippet exclusion: `/surveys/` and `/r/` carry no snippet, so they
cannot record regardless. The URL trigger is not what protects respondents — the exclusion is. The
trigger protects anonymous visitors to our own marketing pages, which the exclusion does not cover.

### 4. `recording_domains` pinned to production

Empty means "any origin". With a real key present, that would let a local checkout, a PR preview or
a fork start recording into the production project. Pinning the origin makes the blast radius of a
leaked key smaller and is free.

### 5. Retention 30 days

The shortest PostHog offers. The question this change answers is "where did creators get stuck this
month"; a recording older than that has no consumer, and every extra day is something we would have
to justify on `/trust/`. Longer retention should be argued for by a use case, not chosen as a
default.

### 6. `/trust/` before the switch, not after

The page currently describes product analytics but says nothing about screen recording. The
disclosure ships in the same change as the capability, and names four things: that editor sessions
are recorded, that typed content is masked, that recordings are kept 30 days, and that respondents
are never recorded. The last is the one an institutional buyer actually cares about, and it is the
one we can defend by pointing at `POSTHOG_EXCLUDED_PREFIXES`.

## Risks / Trade-offs

- **Masking is a client-side promise that could regress silently** → A test asserts the rendered
  config carries the masking flags. A regression that removes them fails the suite rather than
  quietly starting to record keystrokes.
- **"Interface text is visible" is a judgement call, and the editor renders user content as
  interface** (a saved question title is displayed, not just typed) → Partly accepted, partly
  bounded: recordings are limited to 30 days, restricted to signed-in creators looking at their own
  data, and disclosed. If a specific screen turns out to expose something sensitive, the answer is a
  `maskTextSelector` for that screen, not a policy rewrite.
- **A creator may reasonably object to being recorded at all** → `/trust/` states it, and the
  setting can turn it off globally without a deploy. If we ever gain an enterprise customer who
  needs recording off for their org specifically, that is a per-organisation flag and a separate
  change; nothing here forecloses it.
- **Recording payloads are large and ride the analytics path** → They ride the first-party proxy
  from `posthog-reverse-proxy`, which is where a blocker would otherwise drop them. Volume is
  bounded by the URL trigger and by there being ~12 active people.
- **Turning this on in the dashboard while the client flag is still set does nothing, silently** →
  Ordering is explicit in `tasks.md`: client first, project settings second, verification third.

## Migration Plan

1. Ship the code with `POSTHOG_SESSION_REPLAY` unset — a no-op deploy.
2. Set the project settings (opt-in, URL trigger, sample rate 1.00, masking, retention 30d,
   recording domains, console/network off).
3. Set `POSTHOG_SESSION_REPLAY=True` on the Render web service.
4. Verify on a real editor session: a recording appears, typed text is masked in playback, and no
   recording is produced by a `/surveys/` visit.

**Rollback**: unset the environment variable. Existing recordings are then subject to retention; if
they need to go sooner, `session-recording-bulk-delete` exists.

## Open Questions

- **Does masked playback stay useful?** Unknown until watched. If grey boxes make the editor
  unreadable, the fix is per-selector unmasking of specific non-personal fields — never a blanket
  `maskAllInputs: false`.
- **Do we need `$rageclick`/`$dead_click` to link to their recordings?** They already carry session
  ids, so this is likely free; confirm once recordings exist.
