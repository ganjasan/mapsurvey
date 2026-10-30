"""Builders for PayPro webhook payloads with valid HASH and SIGNATURE."""
import hashlib
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from billing.models import STATUS_ACTIVE, Subscription

from survey.models import Membership, Organization

SECRET = 'secret-key-test'
VALIDATION = 'validation-key-test'
PRODUCTS = {'pro_monthly': 1001, 'pro_yearly': 1002}
PPG_IP = '198.199.123.239'

PPG_SETTINGS = dict(
    PPG_SECRET_KEY=SECRET, PPG_VALIDATION_KEY=VALIDATION, PPG_PRODUCTS=PRODUCTS,
    PPG_ACCEPT_TEST_IPN=False, PPG_TEST_MODE=False, PPG_API_SECRET_KEY='', PPG_VENDOR_ACCOUNT_ID='',
    PPG_IPN_DOMAIN='', RENDER_EXTERNAL_HOSTNAME='',
)


def make_org(name='Billing Org', owner_username='bill_owner'):
    org = Organization.objects.create(name=name, slug=name.lower().replace(' ', '-'))
    owner = User.objects.create_user(username=owner_username, password='pass', email=f'{owner_username}@example.test',
                                     first_name='Ann', last_name='Lee')
    Membership.objects.create(user=owner, organization=org, role='owner')
    return org, owner


def trial_used_elsewhere(*orgs):
    """Make each workspace NOT startable (change pro-trial-auto): every owner has
    already used their trial in a throwaway workspace, expired. Tests of what a
    Free workspace without a trial is refused call this; otherwise the first
    Pro use would start the owner's trial."""
    from django.utils import timezone

    from ..models import GRANT_KIND_TRIAL, EntitlementGrant

    past = timezone.now() - timedelta(days=200)
    for org in orgs:
        for m in Membership.objects.filter(organization=org, role='owner').select_related('user'):
            if EntitlementGrant.objects.filter(kind=GRANT_KIND_TRIAL, claimed_by=m.user).exists():
                continue
            spare = Organization.objects.create(name=f'Spent {m.user.username}', slug=f'spent-{m.user.pk}')
            EntitlementGrant.objects.create(organization=spare, kind=GRANT_KIND_TRIAL, claimed_by=m.user,
                                            starts_at=past, expires_at=past + timedelta(days=90))


def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000')


def payload(type_id, type_name, *, order_id='5001', subscription_id='954874', product_id=1002,
            email='bill_owner@example.test', org_id=None, nonce='', test_mode=False, total='490.00',
            status='Processed', next_charge=None, extra=None):
    """A minimal but complete IPN body as PayPro would POST it, signed."""
    next_charge = next_charge or (timezone.now() + timedelta(days=365))
    custom = []
    if org_id is not None:
        custom.append(f'x-org_id={org_id}')
    if nonce:
        custom.append(f'x-nonce={nonce}')
    custom.append('x-plan=pro_yearly')
    p = {
        'IPN_TYPE_ID': str(type_id), 'IPN_TYPE_NAME': type_name,
        'ORDER_ID': order_id, 'ORDER_STATUS_ID': '5', 'ORDER_STATUS': status,
        'ORDER_TOTAL_AMOUNT': '0' if test_mode else total,
        'PRODUCT_ID': str(product_id), 'ORDER_ITEM_NAME': 'Mapsurvey Pro',
        'CUSTOMER_ID': '777', 'CUSTOMER_EMAIL': email, 'CUSTOMER_FIRST_NAME': 'Ann', 'CUSTOMER_LAST_NAME': 'Lee',
        'ORDER_CUSTOM_FIELDS': ','.join(custom),
        'SUBSCRIPTION_ID': subscription_id, 'SUBSCRIPTION_STATUS_ID': '1', 'SUBSCRIPTION_STATUS_NAME': 'Active',
        'SUBSCRIPTION_NEXT_CHARGE_DATE': iso(next_charge), 'SUBSCRIPTION_RENEWAL_TYPE': 'Auto',
        'SUBSCRIPTION_NUMBER_OF_BILLING_CYCLES': '1', 'PAYMENT_METHOD_ID': '2', 'PAYMENT_METHOD_NAME': 'Visa',
        'INVOICE_LINK': 'https://invoice.example.test/1', 'TEST_MODE': '1' if test_mode else '0',
    }
    if extra:
        p.update(extra)
    return sign(p)


def sign(p, secret=SECRET, validation=VALIDATION):
    p = dict(p)
    p['HASH'] = (hashlib.md5(b'1').hexdigest() if p.get('TEST_MODE') == '1'
                 else hashlib.md5(f"{p['ORDER_ID']}{secret}".encode()).hexdigest())
    s = (f"{p['ORDER_ID']}{p['ORDER_STATUS']}{p['ORDER_TOTAL_AMOUNT']}{p['CUSTOMER_EMAIL']}"
         f"{validation}{p['TEST_MODE']}{p['IPN_TYPE_NAME']}")
    p['SIGNATURE'] = hashlib.sha256(s.encode()).hexdigest()
    return p


def post_ipn(client, p, ip=PPG_IP):
    return client.post('/billing/ipn/', data=p, REMOTE_ADDR=ip)


def make_sub(org, status=STATUS_ACTIVE, days=30, **kw):
    end = timezone.now() + timedelta(days=days) if days is not None else None
    defaults = dict(organization=org, product_key='pro_monthly', ppg_product_id='1001', ppg_subscription_id='954874',
                    status=status, current_period_end=end, renewal_type='auto', customer_email='bill_owner@example.test')
    defaults.update(kw)
    return Subscription.objects.create(**defaults)
