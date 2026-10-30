"""PostHog event names for the paywall. Emitted through survey.product_events.emit
(never raises, no-op when PostHog is unconfigured) and always keyed on the
acting user -- the buyer, the canceller, the requester -- never on a respondent.
"""
PLAN_CHECKOUT_STARTED = 'plan_checkout_started'
PLAN_ACTIVATED = 'plan_activated'
PLAN_PAYMENT_FAILED = 'plan_payment_failed'
PLAN_CANCELLED = 'plan_cancelled'
PLAN_LAPSED = 'plan_lapsed'
PRO_HELP_REQUESTED = 'pro_help_requested'
# The Pro trial (change pro-trial-allowances): the owner's click, and the use
# that spent the last of one feature's allowance (once per feature).
TRIAL_CLAIMED = 'trial_claimed'
TRIAL_EXHAUSTED = 'trial_exhausted'
# Change pro-trial-auto: `trial_claimed` also fires for a trial started by a
# first Pro use, with `trigger` (click | feature key) and `auto`; the "ends in a
# week" mail is its own event.
TRIAL_ENDING_NOTIFIED = 'trial_ending_notified'

BILLING_EVENTS = (
    PLAN_CHECKOUT_STARTED, PLAN_ACTIVATED, PLAN_PAYMENT_FAILED,
    PLAN_CANCELLED, PLAN_LAPSED, PRO_HELP_REQUESTED, TRIAL_CLAIMED, TRIAL_EXHAUSTED,
    TRIAL_ENDING_NOTIFIED,
)


def emit(event, user_id, properties=None):
    from survey.product_events import emit as _emit
    _emit(event, user_id, properties)
