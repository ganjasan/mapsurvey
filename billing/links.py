"""Payment links made for an organisation by staff — for the buyer who has no
Mapsurvey account (a council's finance clerk, a client's procurement).

The link is the same checkout URL the Upgrade button builds, tied to the
organisation through `x-org_id` and a `CheckoutIntent`; whoever pays with it,
Pro lands on that organisation. No buyer email is prefilled: PayPro asks.
Used by the admin page and the `billing_link` management command.
"""
from django.conf import settings

from . import checkout as co
from . import events as ev
from .models import CheckoutIntent


def make_payment_link(organization, product_key, *, quote=False, staff_user=None, request=None):
    if product_key not in co.PRODUCT_KEYS:
        raise ValueError(product_key)
    if not co.products_configured():
        raise co.CheckoutUnavailable('PPG_PRODUCTS is not configured')
    quote = bool(quote) and product_key == co.PRODUCT_YEARLY
    intent = CheckoutIntent.objects.create(organization=organization, user=None, product_key=product_key, quote=quote)
    url = co.build_checkout_url(product_key=product_key, organization=organization, user=None,
                                nonce=intent.nonce, language='en', request=request, quote=quote)
    ev.emit(ev.PLAN_CHECKOUT_STARTED, staff_user.pk if staff_user else None,
            {'org_id': organization.pk, 'plan': product_key, 'nonce': str(intent.nonce), 'quote': quote,
             'source': 'staff_link', 'test_mode': bool(settings.PPG_TEST_MODE)})
    return intent, url
