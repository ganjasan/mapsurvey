"""Checkout link construction. The only place a PayPro URL is assembled.

`https://store.payproglobal.com/checkout?products[1][id]=<id>&…`: our
identifiers ride in `x-*` parameters (echoed back in ORDER_CUSTOM_FIELDS),
the buyer's details are prefilled, and `ipn-domain` names the environment so
PayPro delivers the webhook to the host the click came from (the Integration
tab holds a wildcard rule for previews). Test mode is a URL parameter -- there
is no sandbox -- so it is added only where `PPG_TEST_MODE` says so.
"""
from urllib.parse import urlencode

from django.conf import settings

CHECKOUT_BASE = 'https://store.payproglobal.com/checkout'
CUSTOMER_ACCOUNT_URL = 'https://cc.payproglobal.com/Customer/Account/Login'

PRODUCT_MONTHLY = 'pro_monthly'
PRODUCT_YEARLY = 'pro_yearly'
PRODUCT_KEYS = (PRODUCT_MONTHLY, PRODUCT_YEARLY)


class CheckoutUnavailable(Exception):
    """No PayPro products configured: the Upgrade controls do not exist."""


def products_configured():
    return bool(settings.PPG_PRODUCTS) and all(settings.PPG_PRODUCTS.get(k) for k in PRODUCT_KEYS)


def product_id(product_key):
    try:
        return int(settings.PPG_PRODUCTS[product_key])
    except (KeyError, TypeError, ValueError):
        raise CheckoutUnavailable(product_key)


def renewal_url(ppg_subscription_id):
    """PayPro's renewal checkout: pays an outstanding rebill and/or replaces the
    payment method of a subscription. The link in our "Payment failed" banner."""
    return f'{CHECKOUT_BASE}?subscr-id={ppg_subscription_id}'


def ipn_domain(request):
    """Host PayPro should route this order's webhooks to. A setting wins (a
    staging host registered in the Integration tab), then Render's own
    hostname, then whatever the request came in on."""
    configured = getattr(settings, 'PPG_IPN_DOMAIN', '') or ''
    if configured:
        return configured
    render_host = getattr(settings, 'RENDER_EXTERNAL_HOSTNAME', '') or ''
    if render_host:
        return render_host
    return request.get_host().split(':')[0] if request is not None else ''


def build_checkout_url(*, product_key, organization, user, nonce, language=None, request=None, quote=False):
    pid = product_id(product_key)
    params = [(f'products[1][id]', str(pid))]
    if language:
        params.append(('language', language.split('-')[0].upper()))
    if user is not None:
        if user.email:
            params.append(('billing-email', user.email))
        if user.first_name:
            params.append(('billing-first-name', user.first_name))
        if user.last_name:
            params.append(('billing-last-name', user.last_name))
    if product_key == PRODUCT_YEARLY:
        # The yearly product is the one a municipality buys: company name and
        # tax number on the invoice, and a PDF quote that can go through procurement.
        params.append(('use-company-purchase', 'true'))
        if quote:
            params.append(('display-quote', 'true'))
            params.append(('quote-mode', 'editable'))
    custom = {
        'x-org_id': str(organization.pk),
        'x-user_id': str(user.pk) if user is not None else '',
        'x-plan': product_key,
        'x-nonce': str(nonce),
    }
    for k, v in custom.items():
        if ',' in v or '=' in v:
            # ORDER_CUSTOM_FIELDS comes back as "x-a=1,x-b=2"; these characters would break parsing.
            raise ValueError(f'custom field {k} must not contain "," or "="')
        if v:
            params.append((k, v))
    domain = ipn_domain(request)
    if domain:
        params.append(('ipn-domain', domain))
    if settings.PPG_TEST_MODE:
        params.append(('use-test-mode', 'true'))
        params.append(('secret-key', settings.PPG_SECRET_KEY))
    return f'{CHECKOUT_BASE}?{urlencode(params, safe="[]")}'
