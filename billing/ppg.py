"""PayPro Global REST API client -- the actions the billing page can ask for.

All endpoints are POST JSON to https://store.payproglobal.com/api/<Group>/<Method>
authenticated by `vendorAccountId` + `apiSecretKey` in the body, and the
caller's IP must be whitelisted by PayPro. The response envelope is
{"response", "request", "errors": [...], "isSuccess": bool}; `isSuccess=false`
arrives with HTTP 200, so the flag is what we check. The echoed `request`
contains the secret and is dropped before anything is logged or returned.

`is_configured()` is the switch the billing page reads: without an API key the
page offers links into the PayPro customer account instead of these actions.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = 'https://store.payproglobal.com/api'
DATE_FORMAT_ISO = 'a'  # yyyy-MM-ddTHH:mm:ss.fff

RENEWAL_TYPE_MANUAL = 1
RENEWAL_TYPE_AUTO = 2


class PPGApiError(Exception):
    def __init__(self, endpoint, errors, http_status=None):
        self.endpoint, self.errors, self.http_status = endpoint, errors, http_status
        super().__init__(f'{endpoint}: {errors} (http={http_status})')

    def messages(self):
        """Flatten PayPro's errors[] into strings for the page."""
        out = []
        if isinstance(self.errors, list):
            for e in self.errors:
                if isinstance(e, dict):
                    msgs = e.get('propertyErrorMessages') or []
                    prop = e.get('propertyWithError') or ''
                    out.extend(f'{prop}: {m}' if prop else str(m) for m in msgs)
                else:
                    out.append(str(e))
        elif self.errors:
            out.append(str(self.errors))
        return out or ['PayPro Global rejected the request.']


def is_configured():
    return bool(settings.PPG_API_SECRET_KEY and settings.PPG_VENDOR_ACCOUNT_ID)


def _clean(d):
    return {k: v for k, v in d.items() if v is not None}


def _post(endpoint, body, timeout=30.0):
    payload = _clean(body)
    payload['vendorAccountId'] = int(settings.PPG_VENDOR_ACCOUNT_ID)
    payload['apiSecretKey'] = settings.PPG_API_SECRET_KEY
    req = urllib.request.Request(
        f'{API_BASE}/{endpoint}', data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        raise PPGApiError(endpoint, e.read().decode('utf-8', 'replace')[:500], e.code) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise PPGApiError(endpoint, str(e)) from e
    try:
        data = json.loads(raw.decode('utf-8'))
    except ValueError:
        raise PPGApiError(endpoint, raw[:500].decode('utf-8', 'replace'), status)
    data.pop('request', None)
    if not data.get('isSuccess', False):
        raise PPGApiError(endpoint, data.get('errors'), status)
    return data


def subscription_details(subscription_id):
    return _post('Subscriptions/GetSubscriptionDetails',
                 {'subscriptionId': int(subscription_id), 'dateFormat': DATE_FORMAT_ISO})


def suspend(subscription_id, *, cancellation_reason_id=None, reason_text=None, send_customer_notification=True):
    """Reversible cancel (PayPro status Suspended)."""
    return _post('Subscriptions/Suspend', {
        'subscriptionId': int(subscription_id), 'cancellationReasonId': cancellation_reason_id,
        'reasonText': reason_text, 'sendCustomerNotification': send_customer_notification})


def renew(subscription_id, *, reason_text):
    """Only a Suspended subscription; an overdue one is charged immediately."""
    return _post('Subscriptions/Renew', {'subscriptionId': int(subscription_id), 'reasonText': reason_text})


def change_product(subscription_id, product_id, *, send_customer_notification=True):
    """Switch period/plan; takes effect at the next charge, date unchanged."""
    return _post('Subscriptions/ChangeProduct', {
        'subscriptionId': int(subscription_id), 'productId': int(product_id),
        'sendCustomerNotification': send_customer_notification})


def send_onetime_login_email(*, customer_email=None, order_id=None):
    """15-minute passwordless link into the PayPro customer account."""
    return _post('Customers/SendOnetimeLoginEmail',
                 {'customerEmail': customer_email, 'orderId': int(order_id) if order_id else None})


def store_products(product_ids):
    return _post('Products/GetStoreProducts', {'productIds': [int(p) for p in product_ids]})
