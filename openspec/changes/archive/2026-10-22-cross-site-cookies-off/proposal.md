## Why

Since embed-surveys (#286, live 2026-10-13) every visitor's session and CSRF cookies carried
`SameSite=None; Secure; Partitioned`, not only the framed ones. The Facebook and Instagram in-app
browsers on iOS do not keep a `Partitioned` cookie, so their section POSTs failed CSRF (403) on six
published customer surveys — on the Facebook-shared council survey 9 answered of 127 sessions on
launch day — and Chromium creators who already had a plain `csrftoken` now carried two cookies of
that name, so every JavaScript POST in the editor that reads `document.cookie` failed too (#388).
The owner set `CROSS_SITE_COOKIES=0` on 2026-10-22 15:48 UTC; this change makes that the code's
default and cleans up the cookies the nine days left behind. Separately, the worker signs the
abuse-review link with a `SECRET_KEY` of its own, so the link 404s on the web service.

## What Changes

- `CROSS_SITE_COOKIES` defaults to off everywhere; `PartitionedCookieMiddleware` adds
  `Partitioned` only when it is on. Embedding keeps working through `EmbedSessionMiddleware`'s
  cookie-less carrier, which is what Safari and iOS used all along.
- With the switch off, the same middleware removes the stale partitioned `sessionid` and
  `csrftoken` from browsers that still send them next to the plain ones.
- The worker takes `SECRET_KEY` from the `mapsurvey-shared` environment group instead of
  generating its own, so links it signs verify on the web service.
- Changelog entry for creators.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `survey-embedding`: the cookie requirement flips its default and gains the clean-up.

## Impact

- `mapsurvey/settings.py`, `survey/middleware.py`, `render.yaml`, `survey/tests.py`,
  `survey/changelog/`, `CLAUDE.md`.
- Operations: `SECRET_KEY` of the web service must be added to the `mapsurvey-shared` group by
  hand before the Blueprint sync removes the worker's own.
