## Context

`CreatorPreferences.ui_language` (empty = follow the browser) is written by
`set_creator_language` and read by `CreatorLanguageCookieMiddleware`. PostHog person properties for
creators are set two ways: `$set_once` on `creator_registered` for first-touch, and
`sync_posthog_person_properties` (`posthog.set`) for current state such as `segment`/`plan`.

## Decisions

**`posthog.set`, not `$set_once`, and not an event.** Language is current state that a creator
can change; `set` overwrites, which is what we want, and it needs no event to ride on. A
`product_events.set_person_properties(user_id, props)` helper mirrors `emit`: silent no-op when
PostHog is disabled, never raises.

**Empty string is sent as `''`, not omitted.** "Follows the browser" is a real state and the
majority today; omitting it would make the breakdown look like most creators have no value.

**Backfill through the existing sync command.** It already builds one property dict per creator;
`ui_language` joins `segment`/`plan`. One run after deploy covers the 357 existing creators.

## Risks / Trade-offs

- [`ui_language` says what was chosen, not what the browser shows for creators who never chose]
  → accepted; that group is the `''` bucket and is read as "browser default (mostly English)".

## Migration Plan

Deploy; run `manage.py sync_posthog_person_properties` once in the production container.
