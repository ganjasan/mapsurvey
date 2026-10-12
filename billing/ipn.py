"""PayPro Global IPN: verification, parsing, and the subscription state machine.

Everything here works on the raw form strings PayPro sent. Numbers are never
re-formatted before hashing -- the SIGNATURE is computed over the exact text --
and dates are parsed leniently but kept raw next to the parsed value.

Verification (developers.payproglobal.com → Webhooks → Webhook parameters):
  HASH      = MD5(ORDER_ID + SECRET_KEY)               (test orders: MD5("1"))
  SIGNATURE = SHA256(ORDER_ID + ORDER_STATUS + ORDER_TOTAL_AMOUNT + CUSTOMER_EMAIL
                     + VALIDATION_KEY + TEST_MODE + IPN_TYPE_NAME)
"+" is plain concatenation. Source IPs are a setting because PayPro may add one.
"""
import hashlib
import hmac
import ipaddress
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from typing import Mapping, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import events as ev
from .features import PLAN_PRO
from .models import (
    RENEWAL_AUTO, RENEWAL_MANUAL, STATUS_ACTIVE, STATUS_CHARGED_BACK, STATUS_FINISHED,
    STATUS_PAST_DUE, STATUS_REFUNDED, STATUS_SUSPENDED, STATUS_TERMINATED,
    CheckoutIntent, Subscription,
)

logger = logging.getLogger(__name__)

MD5_TEST_ORDER = 'c4ca4238a0b923820dcc509a6f75849b'  # MD5("1")

# IPN_TYPE_ID values. 18-20 are not documented.
ORDER_CHARGED = 1
ORDER_REFUNDED = 2
ORDER_CHARGED_BACK = 3
ORDER_DECLINED = 4
ORDER_PARTIALLY_REFUNDED = 5
SUBSCRIPTION_CHARGE_SUCCEED = 6
SUBSCRIPTION_CHARGE_FAILED = 7
SUBSCRIPTION_SUSPENDED = 8
SUBSCRIPTION_RENEWED = 9
SUBSCRIPTION_TERMINATED = 10
SUBSCRIPTION_FINISHED = 11
LICENSE_REQUESTED = 12
TRIAL_CHARGE = 13
ORDER_CHARGED_BACK_WON = 14
ORDER_CUSTOMER_INFORMATION_CHANGED = 15
INSTANT_LEAD_NOTIFICATION = 16
ORDER_ON_WAITING = 17
SUBSCRIPTION_PAYMENT_INFO_CHANGED = 21

TYPE_NAMES = {
    1: 'OrderCharged', 2: 'OrderRefunded', 3: 'OrderChargedBack', 4: 'OrderDeclined',
    5: 'OrderPartiallyRefunded', 6: 'SubscriptionChargeSucceed', 7: 'SubscriptionChargeFailed',
    8: 'SubscriptionSuspended', 9: 'SubscriptionRenewed', 10: 'SubscriptionTerminated',
    11: 'SubscriptionFinished', 12: 'LicenseRequested', 13: 'TrialCharge', 14: 'OrderChargedBackWon',
    15: 'OrderCustomerInformationChanged', 16: 'InstantLeadNotification', 17: 'OrderOnWaiting',
    21: 'SubscriptionPaymentInfoChanged',
}


class IpnVerificationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def body_sha256(payload: Mapping[str, str]) -> str:
    """Fingerprint of the payload without the resend marker, so a resend of the
    same event hashes like the original and is acknowledged, not re-applied."""
    items = sorted((k, v) for k, v in payload.items() if k != 'IS_RESENT')
    h = hashlib.sha256()
    for k, v in items:
        h.update(k.encode('utf-8'))
        h.update(b'=')
        h.update(str(v).encode('utf-8'))
        h.update(b'&')
    return h.hexdigest()


def expected_hash(order_id: str, secret_key: str, test_mode: bool) -> str:
    if test_mode:
        return MD5_TEST_ORDER
    return hashlib.md5(f'{order_id}{secret_key}'.encode('utf-8')).hexdigest()


def expected_signature(p: Mapping[str, str], validation_key: str) -> str:
    s = (
        f"{p.get('ORDER_ID', '')}{p.get('ORDER_STATUS', '')}{p.get('ORDER_TOTAL_AMOUNT', '')}"
        f"{p.get('CUSTOMER_EMAIL', '')}{validation_key}{p.get('TEST_MODE', '')}{p.get('IPN_TYPE_NAME', '')}"
    )
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _digest_eq(a: str, b: str) -> bool:
    return hmac.compare_digest((a or '').strip().lower(), (b or '').strip().lower())


def ip_allowed(client_ip: Optional[str]) -> bool:
    if not client_ip:
        return False
    try:
        ip = ipaddress.ip_address(client_ip.strip())
    except ValueError:
        return False
    for allowed in settings.PPG_IPN_ALLOWED_IPS:
        try:
            if ip == ipaddress.ip_address(allowed):
                return True
        except ValueError:
            continue
    return False


def verify(payload: Mapping[str, str], client_ip: Optional[str]):
    """Raise IpnVerificationError unless IP, SIGNATURE and HASH all check out.
    Returns the list of checks that passed (for the event row)."""
    if not ip_allowed(client_ip):
        raise IpnVerificationError('ip')
    test_mode = payload.get('TEST_MODE', '0') == '1'
    if not settings.PPG_VALIDATION_KEY:
        raise IpnVerificationError('validation_key_unset')
    if not _digest_eq(payload.get('SIGNATURE', ''), expected_signature(payload, settings.PPG_VALIDATION_KEY)):
        raise IpnVerificationError('signature')
    if not settings.PPG_SECRET_KEY:
        raise IpnVerificationError('secret_key_unset')
    if not _digest_eq(payload.get('HASH', ''), expected_hash(payload.get('ORDER_ID', ''), settings.PPG_SECRET_KEY, test_mode)):
        raise IpnVerificationError('hash')
    return ['ip', 'signature', 'hash']


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S',
    '%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y', '%d-%b-%Y', '%Y-%m-%d',
)


def parse_ppg_datetime(value: Optional[str]):
    """PayPro's webhook date format is not documented; the API's "a" format is
    yyyy-MM-ddTHH:mm:ss.fff. Try ISO first, then the formats the control panel
    uses. Naive values are taken as UTC. None when nothing matches -- the raw
    string is stored regardless."""
    if not value:
        return None
    value = value.strip()
    dt = parse_datetime(value)
    if dt is None:
        for fmt in _DATE_FORMATS:
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = dt.replace(tzinfo=dt_timezone.utc)
    return dt


def parse_custom_fields(value: str) -> dict:
    """ORDER_CUSTOM_FIELDS: 'x-a=1' or 'x-a=1,x-b=2' per the docs' examples.
    The checkout builder refuses values containing ',' or '=' for this reason."""
    out = {}
    for pair in (value or '').split(','):
        if '=' in pair:
            k, v = pair.split('=', 1)
            out[k.strip()] = v.strip()
    return out


@dataclass
class IpnEvent:
    raw: dict
    type_id: int
    type_name: str
    order_id: str
    test_mode: bool
    is_resent: bool
    product_id: str
    subscription_id: str
    customer_id: str
    customer_email: str
    custom: dict = field(default_factory=dict)

    @property
    def org_id(self):
        v = self.custom.get('x-org_id', '')
        return int(v) if v.isdigit() else None

    @property
    def nonce(self):
        return self.custom.get('x-nonce') or ''

    @property
    def buyer_user_id(self):
        v = self.custom.get('x-user_id', '')
        return int(v) if v.isdigit() else None


def parse(payload: Mapping[str, str]) -> IpnEvent:
    p = dict(payload)
    try:
        type_id = int(p.get('IPN_TYPE_ID', ''))
    except ValueError:
        raise IpnVerificationError('type')
    return IpnEvent(
        raw=p, type_id=type_id, type_name=p.get('IPN_TYPE_NAME') or TYPE_NAMES.get(type_id, ''),
        order_id=p.get('ORDER_ID', ''), test_mode=p.get('TEST_MODE', '0') == '1',
        is_resent=p.get('IS_RESENT') == '1', product_id=p.get('PRODUCT_ID', ''),
        subscription_id=p.get('SUBSCRIPTION_ID', ''), customer_id=p.get('CUSTOMER_ID', ''),
        customer_email=p.get('CUSTOMER_EMAIL', ''),
        custom=parse_custom_fields(p.get('ORDER_CUSTOM_FIELDS', '')),
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def product_key_for(product_id: str):
    for key, pid in settings.PPG_PRODUCTS.items():
        if str(pid) == str(product_id):
            return key
    return None


def resolve_organization(event: IpnEvent):
    """Our identifiers first, PayPro's second, the buyer's email last.

    Returns (organization, intent). The intent is the CheckoutIntent matching
    x-nonce when there is one -- used to record the order id on it and to
    find the buyer for analytics."""
    from survey.models import Membership, Organization

    intent = None
    if event.nonce:
        try:
            intent = CheckoutIntent.objects.filter(nonce=event.nonce).select_related('organization').first()
        except (ValueError, ValidationError):
            intent = None  # not one of ours; a tampered or foreign x-nonce

    org = None
    if event.org_id is not None:
        org = Organization.objects.filter(pk=event.org_id).first()
    if org is None and intent is not None:
        org = intent.organization
    if org is None and event.subscription_id:
        sub = Subscription.objects.filter(ppg_subscription_id=event.subscription_id).select_related('organization').first()
        if sub is not None:
            org = sub.organization
    if org is None and event.customer_email:
        m = (Membership.objects.filter(role='owner', user__email__iexact=event.customer_email)
             .select_related('organization').order_by('organization_id').first())
        if m is not None:
            org = m.organization
    return org, intent


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

@dataclass
class Applied:
    subscription: Optional[Subscription]
    analytics: list  # [(event_name, user_id, properties)]
    error: str = ''


def _renewal(event):
    v = (event.raw.get('SUBSCRIPTION_RENEWAL_TYPE') or '').strip().lower()
    if v.startswith('auto') or v == '2':
        return RENEWAL_AUTO
    if v.startswith('manual') or v == '1':
        return RENEWAL_MANUAL
    return ''


def _period_end_from(event, key='SUBSCRIPTION_NEXT_CHARGE_DATE'):
    raw = event.raw.get(key, '') or ''
    return parse_ppg_datetime(raw), raw


def _buyer_id(event, org, intent):
    if event.buyer_user_id is not None:
        return event.buyer_user_id
    if intent is not None and intent.user_id:
        return intent.user_id
    from survey.models import Membership
    m = Membership.objects.filter(organization=org, role='owner').order_by('joined_at').first()
    return m.user_id if m else None


def _current(org):
    return Subscription.objects.current().filter(organization=org).order_by('-created_at').first()


def _for_event(org, event):
    """The subscription an event is about: by PayPro id first, else the current one."""
    if event.subscription_id:
        sub = Subscription.objects.filter(organization=org, ppg_subscription_id=event.subscription_id).order_by('-created_at').first()
        if sub is not None:
            return sub
    return _current(org)


def apply(event: IpnEvent, org, intent=None, now=None) -> Applied:
    """Apply a verified, non-duplicate event to the organisation's subscription.
    Pure Python over the parsed event; the caller holds the transaction and
    emits `analytics` after commit."""
    now = now or timezone.now()
    analytics = []
    t = event.type_id

    if t in (ORDER_CHARGED, TRIAL_CHARGE):
        return _apply_charge(event, org, intent, now)

    sub = _for_event(org, event)
    if sub is None:
        # A rebill/suspension for a subscription we never saw the initial order of
        # (webhook lost, product configured later). Record for a human.
        return Applied(None, [], error='no_subscription')

    props = {'org_id': org.pk, 'plan': sub.plan_code, 'product': sub.product_key, 'ppg_subscription_id': sub.ppg_subscription_id}
    if event.order_id:
        sub.ppg_last_order_id = event.order_id

    if t == SUBSCRIPTION_CHARGE_SUCCEED:
        sub.status = STATUS_ACTIVE
        end, raw = _period_end_from(event)
        if end is not None:
            sub.current_period_end, sub.current_period_end_raw = end, raw
        sub.failed_attempts = 0
        sub.payment_failed_reported_for = ''
        if event.raw.get('INVOICE_LINK'):
            sub.last_invoice_url = event.raw['INVOICE_LINK'][:500]
        if _renewal(event):
            sub.renewal_type = _renewal(event)
    elif t == SUBSCRIPTION_CHARGE_FAILED:
        if sub.status == STATUS_ACTIVE:
            sub.status = STATUS_PAST_DUE
        attempts = event.raw.get('SUBSCRIPTION_NUMBER_OF_FAILED_ATTEMPTS', '')
        sub.failed_attempts = int(attempts) if attempts.isdigit() else sub.failed_attempts + 1
        cycle = event.order_id or event.raw.get('SUBSCRIPTION_NEXT_CHARGE_DATE', '')
        if sub.payment_failed_reported_for != cycle:
            sub.payment_failed_reported_for = cycle
            analytics.append((ev.PLAN_PAYMENT_FAILED, _buyer_id(event, org, intent), {**props, 'attempts': sub.failed_attempts}))
    elif t == SUBSCRIPTION_SUSPENDED:
        sub.status = STATUS_SUSPENDED
        _record_cancellation(sub, event)
        analytics.append((ev.PLAN_CANCELLED, _buyer_id(event, org, intent), {**props, 'how': 'suspended', 'reason_id': sub.cancellation_reason_id}))
    elif t == SUBSCRIPTION_RENEWED:
        sub.status = STATUS_ACTIVE
        end, raw = _period_end_from(event)
        if end is not None and end > now:
            sub.current_period_end, sub.current_period_end_raw = end, raw
        sub.failed_attempts = 0
    elif t == SUBSCRIPTION_TERMINATED:
        sub.status = STATUS_TERMINATED
        _record_cancellation(sub, event)
        analytics.append((ev.PLAN_CANCELLED, _buyer_id(event, org, intent), {**props, 'how': 'terminated', 'reason_id': sub.cancellation_reason_id}))
    elif t == SUBSCRIPTION_FINISHED:
        sub.status = STATUS_FINISHED
        sub.current_period_end, sub.current_period_end_raw = now, event.raw.get('SUBSCRIPTION_FINISH_DATE', '')
    elif t == ORDER_REFUNDED:
        sub.status = STATUS_REFUNDED
        sub.current_period_end = now
        sub.action_reason = event.raw.get('ACTION_REASON', '') or sub.action_reason
    elif t == ORDER_CHARGED_BACK:
        sub.status = STATUS_CHARGED_BACK
        sub.current_period_end = now
        sub.needs_review = True
        sub.action_reason = event.raw.get('ACTION_REASON', '') or sub.action_reason
    elif t == ORDER_CUSTOMER_INFORMATION_CHANGED:
        if event.customer_email:
            sub.customer_email = event.customer_email
    elif t == ORDER_CHARGED_BACK_WON:
        # Recorded on the event row; a human restores access, never this code.
        pass
    # 4, 5, 12, 16, 17, 21 and anything undocumented: stored, no state change.

    if event.raw.get('SUBSCRIPTION_STATUS_ID') and t not in (ORDER_REFUNDED, ORDER_CHARGED_BACK):
        # Keep PayPro's own status id visible for support even where our status
        # is a finer projection (past_due is PayPro's "Active" with failures).
        pass
    sub.pending_change = ''
    sub.pending_change_until = None
    sub.save()
    return Applied(sub, analytics)


def _record_cancellation(sub, event):
    rid = event.raw.get('SUBSCRIPTION_CANCELLATION_REASON_ID', '')
    if rid.isdigit():
        sub.cancellation_reason_id = int(rid)
    if event.raw.get('ACTION_REASON'):
        sub.action_reason = event.raw['ACTION_REASON'][:2000]


def _apply_charge(event, org, intent, now):
    """OrderCharged / TrialCharge.

    With a SUBSCRIPTION_ID we have never seen: a new subscription (the initial
    order), superseding whatever was current. With one we have: a reference
    charge or a re-delivered initial order -- update, never duplicate. Without
    one: a one-time product we do not sell; recorded, nothing granted."""
    if not event.subscription_id:
        return Applied(None, [], error='not_a_subscription')

    existing = Subscription.objects.filter(organization=org, ppg_subscription_id=event.subscription_id).order_by('-created_at').first()
    product_key = product_key_for(event.product_id)
    if existing is None and product_key is None:
        return Applied(None, [], error='unknown_product')

    trial = event.type_id == TRIAL_CHARGE or event.raw.get('IS_ON_TRIAL_PERIOD') == '1'
    end, raw = _period_end_from(event, 'TRIAL_PERIOD_TILL' if trial else 'SUBSCRIPTION_NEXT_CHARGE_DATE')
    if end is None and trial:
        end, raw = _period_end_from(event)
    analytics = []

    if existing is None:
        current = _current(org)
        if current is not None:
            current.superseded_at = now
            current.save(update_fields=['superseded_at', 'updated_at'])
        sub = Subscription(organization=org, plan_code=PLAN_PRO, product_key=product_key,
                           ppg_product_id=event.product_id, ppg_subscription_id=event.subscription_id,
                           ppg_initial_order_id=event.order_id)
        buyer = _buyer_id(event, org, intent)
        analytics.append((ev.PLAN_ACTIVATED, buyer, {
            'org_id': org.pk, 'plan': PLAN_PRO, 'product': product_key, 'nonce': event.nonce,
            'trial': trial, 'test_mode': event.test_mode, 'ppg_subscription_id': event.subscription_id,
            'renewal_type': _renewal(event), 'payment_method': event.raw.get('PAYMENT_METHOD_NAME', ''),
        }))
    else:
        sub = existing
        if product_key:
            sub.product_key, sub.ppg_product_id = product_key, event.product_id

    sub.status = STATUS_ACTIVE
    sub.failed_attempts = 0
    sub.payment_failed_reported_for = ''
    if end is not None:
        sub.current_period_end, sub.current_period_end_raw = end, raw
    if trial:
        sub.trial_until = end
    sub.ppg_last_order_id = event.order_id or sub.ppg_last_order_id
    sub.ppg_customer_id = event.customer_id or sub.ppg_customer_id
    sub.customer_email = event.customer_email or sub.customer_email
    if _renewal(event):
        sub.renewal_type = _renewal(event)
    if event.raw.get('INVOICE_LINK'):
        sub.last_invoice_url = event.raw['INVOICE_LINK'][:500]
    sub.pending_change = ''
    sub.pending_change_until = None
    sub.save()

    if intent is not None and intent.consumed_at is None:
        intent.consumed_at = now
        intent.order_id = event.order_id
        intent.save(update_fields=['consumed_at', 'order_id'])
    return Applied(sub, analytics)
