## Context

`DirectActivationView` (survey/views.py) overrides `post` to render its own failure pages and to
sign the user in on the genuine inactive → active transition. It calls `self.activate(form)`
instead of `self.form_valid(form)`; the library sends `signals.user_activated` only from
`form_valid`. Our `emit_activation_event` receiver therefore never fired.

## Goals / Non-Goals

**Goals:** the live `creator_activated_account` event, with `timestamp_source='live'`, for every
successful activation; a test on the real POST path.

**Non-Goals:** changing activation UX, the auto-login rule, or the error branches.

## Decisions

**Send the library signal, not `pe.emit` directly.** `signals.user_activated.send(sender=self.__class__,
user=activated_user, request=request)` keeps one code path for anything subscribed to activation,
now and later, and mirrors what `form_valid` does. It is sent only after `activate()` returned a
user, i.e. on the genuine transition — the `already_activated` branch raises before this line and
correctly emits nothing.

**Backfill stays as it is.** Re-running `backfill_posthog_events` after deploy fills the missing
months with the existing proxy timestamps; the live event takes over from the deploy. Insights that
care about activation *timing* keep filtering `timestamp_source = 'live'`, as they already do.

## Risks / Trade-offs

- [A receiver that raises would now abort the activation response] → `emit` swallows its own
  errors by design; the only other receiver today is the same emitter. Documented in the view.
- [Double emission if `form_valid` is ever reintroduced] → the test asserts exactly one event.

## Migration Plan

Deploy; run `python manage.py backfill_posthog_events` once in the production container; the
AARRR "Activation" row reads correctly from the next refresh. Rollback: revert the one call.
