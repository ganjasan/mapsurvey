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

BILLING_EVENTS = (
    PLAN_CHECKOUT_STARTED, PLAN_ACTIVATED, PLAN_PAYMENT_FAILED,
    PLAN_CANCELLED, PLAN_LAPSED, PRO_HELP_REQUESTED,
)


def emit(event, user_id, properties=None):
    from survey.product_events import emit as _emit
    _emit(event, user_id, properties)
