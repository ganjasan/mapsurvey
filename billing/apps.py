from django.apps import AppConfig


class BillingConfig(AppConfig):
    """Pro subscriptions sold through PayPro Global (change paywall-payproglobal, #268).

    PayPro is the Merchant of Record: checkout, cards, tax, invoices and refunds
    live there. This app owns the three things that are ours -- the checkout
    link out, the verified webhook in, and the entitlement derived from what the
    webhooks said. Nothing in here reads PayPro at request time.
    """
    name = 'billing'
    default_auto_field = 'django.db.models.BigAutoField'
