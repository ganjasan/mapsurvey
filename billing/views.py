"""Billing views: the webhook, the return page, the organisation's billing page
and its actions, and the Pro help channel.

One grant path. `ipn` is the only view that writes `Subscription`; the return
page polls, the actions ask PayPro and wait for the webhook, the help page
reads the entitlement. See openspec/changes/paywall-payproglobal/design.md.
"""
import logging
import re
from urllib.parse import parse_qs, urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from survey.models import Organization
from survey.permissions import get_org_membership

from . import checkout as co
from . import entitlements as ents
from . import events as ev
from . import ipn as ipn_mod
from . import ppg
from .forms import CancelForm, ProHelpRequestForm
from .models import STATUS_ACTIVE, STATUS_SUSPENDED, BillingEvent, CheckoutIntent, Subscription
from .trial import TrialRefused, claim, flash_started, offered, state_for, use
from .trial import may as trial_may

logger = logging.getLogger(__name__)

PENDING_CHANGE_MINUTES = 10


def _report(exc, **tags):
    """PostHog error tracking, never raising. The same gate as everywhere else:
    `posthog.disabled` is True when the key is unset."""
    try:
        import posthog
        from posthog import new_context, tag
        if posthog.disabled:
            return
        with new_context(capture_exceptions=False):
            for k, v in tags.items():
                tag(k, str(v))
            posthog.capture_exception(exc)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def ipn(request):
    """verify → test-mode gate → persist once → apply → 200 after commit.

    400 when verification fails (PayPro retries three times and emails us,
    which is what a key rotation deserves). 500 when our own code fails: the
    transaction rolls back so the event is not marked seen, and PayPro
    redelivers. 200 for duplicates, ignored test events and events we cannot
    attribute -- all stored, none worth a retry.
    """
    payload = request.POST.dict()
    client_ip = getattr(request, 'cf_ip', None) or request.META.get('REMOTE_ADDR', '')
    try:
        verified = ipn_mod.verify(payload, client_ip)
        event = ipn_mod.parse(payload)
    except ipn_mod.IpnVerificationError as e:
        logger.warning('billing ipn rejected (%s) order=%s ip=%s', e, payload.get('ORDER_ID', ''), client_ip)
        _report(e, billing_order_id=payload.get('ORDER_ID', ''), billing_ip=client_ip)
        return HttpResponse('rejected', status=400)

    analytics = []
    with transaction.atomic():
        row, created = BillingEvent.objects.get_or_create(
            order_id=event.order_id, ipn_type_id=event.type_id, body_sha256=ipn_mod.body_sha256(payload),
            defaults={
                'ipn_type_name': event.type_name, 'ppg_subscription_id': event.subscription_id,
                'product_id': event.product_id, 'test_mode': event.test_mode, 'is_resent': event.is_resent,
                'payload': payload, 'verified_by': verified,
            },
        )
        if not created:
            return HttpResponse('duplicate', status=200)

        if event.test_mode and not settings.PPG_ACCEPT_TEST_IPN:
            row.ignored_test = True
            row.save(update_fields=['ignored_test'])
            return HttpResponse('ignored test', status=200)

        org, intent = ipn_mod.resolve_organization(event)
        if org is None:
            row.error = 'unresolved'
            row.save(update_fields=['error'])
            logger.error('billing ipn unresolved: %s order=%s sub=%s', event.type_name, event.order_id, event.subscription_id)
            _report(RuntimeError('billing ipn unresolved'), billing_order_id=event.order_id, billing_type=event.type_name)
            return HttpResponse('unresolved', status=200)

        applied = ipn_mod.apply(event, org, intent)
        row.organization = org
        row.subscription = applied.subscription
        row.error = applied.error
        row.processed_at = timezone.now()
        row.save(update_fields=['organization', 'subscription', 'error', 'processed_at'])
        if applied.error:
            logger.error('billing ipn %s not applied (%s): order=%s sub=%s org=%s',
                         event.type_name, applied.error, event.order_id, event.subscription_id, org.pk)
            _report(RuntimeError(f'billing ipn {applied.error}'), billing_order_id=event.order_id, billing_type=event.type_name)
        analytics = applied.analytics

    for name, user_id, props in analytics:
        ev.emit(name, user_id, props)
    return HttpResponse('OK', status=200)


# ---------------------------------------------------------------------------
# Return page
# ---------------------------------------------------------------------------

def _nonce_from(request):
    """PayPro redirects with our original query string via GET and the order
    parameters via POST; the nonce can arrive either way."""
    nonce = request.GET.get('x-nonce') or request.GET.get('nonce') or ''
    if not nonce and request.method == 'POST':
        nonce = ipn_mod.parse_custom_fields(request.POST.get('ORDER_CUSTOM_FIELDS', '')).get('x-nonce', '')
    return nonce.strip()


def _origin_host(request):
    """The environment the checkout started on: `ipn-domain` from the original
    checkout query string (PayPro sends it back via GET, and in the POSTed
    CHECKOUT_QUERY_STRING)."""
    host = request.GET.get('ipn-domain', '')
    if not host and request.method == 'POST':
        host = (parse_qs(request.POST.get('CHECKOUT_QUERY_STRING', '')).get('ipn-domain') or [''])[0]
    return host.strip().lower()


@csrf_exempt
def checkout_return(request):
    """Thank-you redirect target. Shows and polls; never grants.

    PayPro allows one redirect URL per page template, and it points at
    production. An order placed on a PR preview carries the preview's host in
    `ipn-domain`; production forwards the buyer there (303, so the POST becomes
    a GET). Only hosts matching PPG_RETURN_FORWARD_HOSTS qualify -- anything else
    renders here, so this is never an open redirect."""
    pending = request.GET.get('pending') == '1'
    nonce = _nonce_from(request)
    origin = _origin_host(request)
    here = request.get_host().split(':')[0].lower()
    if origin and origin != here and re.fullmatch(settings.PPG_RETURN_FORWARD_HOSTS, origin):
        params = {'x-nonce': nonce} if nonce else {}
        if pending:
            params['pending'] = '1'
        url = f'https://{origin}/billing/return/' + (f'?{urlencode(params)}' if params else '')
        response = redirect(url)
        response.status_code = 303
        return response
    intent = None
    if nonce:
        try:
            intent = CheckoutIntent.objects.select_related('organization').get(nonce=nonce)
        except (CheckoutIntent.DoesNotExist, ValueError, ValidationError):
            intent = None
    org = intent.organization if intent is not None else None
    member = org is not None and get_org_membership(request.user, org) is not None
    return render(request, 'billing/checkout_return.html', {
        'nonce': nonce if intent is not None else '',
        'org': org if member else None,
        'pending_transfer': pending,
        'poll_seconds': 2,
        'poll_limit_seconds': 60,
    })


@require_GET
def checkout_status(request):
    nonce = (request.GET.get('nonce') or '').strip()
    if not nonce:
        return JsonResponse({'state': 'unknown'})
    try:
        intent = CheckoutIntent.objects.select_related('organization').get(nonce=nonce)
    except (CheckoutIntent.DoesNotExist, ValueError, ValidationError):
        return JsonResponse({'state': 'unknown'})
    e = ents.for_organization(intent.organization)
    return JsonResponse({'state': 'active' if e.is_pro else 'pending'})


# ---------------------------------------------------------------------------
# Organisation billing page
# ---------------------------------------------------------------------------

def _org_for(request, slug, min_roles):
    org = get_object_or_404(Organization, slug=slug)
    m = get_org_membership(request.user, org)
    if m is None or m.role not in min_roles:
        return org, None
    return org, m


def _waiting_order(org):
    """An `OrderOnWaiting` (bank transfer / purchase order) with no later
    OrderCharged for the same order: shown as "awaiting bank transfer"."""
    waiting = (BillingEvent.objects.filter(organization=org, ipn_type_id=ipn_mod.ORDER_ON_WAITING, ignored_test=False)
               .order_by('-received_at').first())
    if waiting is None:
        return None
    charged = BillingEvent.objects.filter(organization=org, order_id=waiting.order_id,
                                          ipn_type_id__in=(ipn_mod.ORDER_CHARGED, ipn_mod.ORDER_DECLINED, ipn_mod.ORDER_REFUNDED)).exists()
    return None if charged else waiting


def _duplicates(org, current):
    """Superseded subscriptions PayPro may still be charging."""
    qs = Subscription.objects.filter(organization=org, superseded_at__isnull=False, status__in=(STATUS_ACTIVE, 'past_due'))
    if current is not None:
        qs = qs.exclude(pk=current.pk)
    return list(qs)


@login_required
def org_billing(request, slug):
    org, m = _org_for(request, slug, ('owner', 'admin'))
    if m is None:
        return HttpResponseForbidden()
    e = ents.for_organization(org)
    sub = ents.current_subscription(org)
    return render(request, 'billing/org_billing.html', {
        'org': org,
        'is_owner': m.role == 'owner',
        'entitlements': e,
        'sub': sub,
        'products_configured': co.products_configured(),
        'api_configured': ppg.is_configured(),
        'renewal_url': co.renewal_url(sub.ppg_subscription_id) if sub and sub.ppg_subscription_id else '',
        'customer_account_url': co.CUSTOMER_ACCOUNT_URL,
        'waiting_order': _waiting_order(org),
        'duplicates': _duplicates(org, sub),
        'cancel_form': CancelForm(),
        'other_period': (co.PRODUCT_YEARLY if sub and sub.product_key == co.PRODUCT_MONTHLY else co.PRODUCT_MONTHLY),
        'can_resubscribe': bool(sub and sub.status == STATUS_SUSPENDED),
        'trial': state_for(org, request.user),
    })


@login_required
def try_pro(request):
    """The dashboard hero's call to action (no URL arguments, as hero links need):
    the trial block of the active workspace's Plan & billing."""
    org = getattr(request, 'active_org', None)
    if org is None:
        return redirect('editor')
    return redirect(reverse('org_billing', args=[org.slug]) + '#pro-trial')


_TRIAL_REFUSALS = {
    'pro': gettext_lazy('This workspace is on Pro already.'),
    'org_used': gettext_lazy('This workspace has had its Pro trial.'),
}


@login_required
@require_POST
def org_trial_claim(request, slug):
    """The owner's "Try Pro" (change pro-trial-allowances). Owner only; the
    rules of the trial live in billing.trial.claim."""
    if not offered():
        raise Http404
    org, m = _org_for(request, slug, ('owner',))
    if m is None:
        return HttpResponseForbidden()
    try:
        claim(org, request.user)
    except TrialRefused as refused:
        if refused.other is not None:
            messages.info(request, _('You already used your Pro trial in %(name)s.') % {'name': refused.other.name})
        else:
            messages.info(request, _TRIAL_REFUSALS.get(refused.reason, _('The Pro trial is not available.')))
        return redirect('org_billing', slug=org.slug)
    messages.success(request, _('Your Pro trial has started.'))
    nxt = request.POST.get('next', '')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return redirect(nxt)
    return redirect('org_billing', slug=org.slug)


@login_required
@require_POST
def org_checkout(request, slug):
    org, m = _org_for(request, slug, ('owner',))
    if m is None:
        return HttpResponseForbidden()
    if not co.products_configured():
        raise Http404
    period = request.POST.get('period', '')
    product_key = {'monthly': co.PRODUCT_MONTHLY, 'yearly': co.PRODUCT_YEARLY}.get(period)
    if product_key is None:
        return HttpResponse('bad period', status=400)
    quote = request.POST.get('quote') == '1' and product_key == co.PRODUCT_YEARLY
    intent = CheckoutIntent.objects.create(organization=org, user=request.user, product_key=product_key, quote=quote)
    url = co.build_checkout_url(product_key=product_key, organization=org, user=request.user, nonce=intent.nonce,
                                language=translation.get_language(), request=request, quote=quote)
    ev.emit(ev.PLAN_CHECKOUT_STARTED, request.user.pk,
            {'org_id': org.pk, 'plan': product_key, 'nonce': str(intent.nonce), 'quote': quote,
             'test_mode': bool(settings.PPG_TEST_MODE)})
    return redirect(url)


def _api_action(request, slug):
    """Common preamble of the API-backed actions: owner, API configured, a
    subscription with a PayPro id."""
    org, m = _org_for(request, slug, ('owner',))
    if m is None:
        return org, None, HttpResponseForbidden()
    if not ppg.is_configured():
        raise Http404
    sub = ents.current_subscription(org)
    if sub is None or not sub.ppg_subscription_id:
        messages.error(request, _('There is no PayPro subscription to act on.'))
        return org, None, redirect('org_billing', slug=org.slug)
    return org, sub, None


def _mark_pending(sub, what):
    sub.pending_change = what
    sub.pending_change_until = timezone.now() + timezone.timedelta(minutes=PENDING_CHANGE_MINUTES)
    sub.save(update_fields=['pending_change', 'pending_change_until', 'updated_at'])


@login_required
@require_POST
def org_cancel(request, slug):
    org, sub, resp = _api_action(request, slug)
    if resp is not None:
        return resp
    form = CancelForm(request.POST)
    if not form.is_valid():
        messages.error(request, _('Please choose a reason.'))
        return redirect('org_billing', slug=org.slug)
    try:
        ppg.suspend(sub.ppg_subscription_id, cancellation_reason_id=form.cleaned_data['reason'],
                    reason_text=form.cleaned_data.get('note') or None, send_customer_notification=True)
    except ppg.PPGApiError as e:
        for msg in e.messages():
            messages.error(request, msg)
        return redirect('org_billing', slug=org.slug)
    _mark_pending(sub, 'cancel')
    messages.success(request, _('Cancellation requested. Pro stays active until the end of the paid period.'))
    return redirect('org_billing', slug=org.slug)


@login_required
@require_POST
def org_resubscribe(request, slug):
    org, sub, resp = _api_action(request, slug)
    if resp is not None:
        return resp
    try:
        ppg.renew(sub.ppg_subscription_id, reason_text='Customer resubscribed from Mapsurvey')
    except ppg.PPGApiError as e:
        for msg in e.messages():
            messages.error(request, msg)
        return redirect('org_billing', slug=org.slug)
    _mark_pending(sub, 'resubscribe')
    messages.success(request, _('Resubscribe requested. The plan becomes active as soon as PayPro confirms it.'))
    return redirect('org_billing', slug=org.slug)


@login_required
@require_POST
def org_switch_period(request, slug):
    org, sub, resp = _api_action(request, slug)
    if resp is not None:
        return resp
    target = co.PRODUCT_YEARLY if sub.product_key == co.PRODUCT_MONTHLY else co.PRODUCT_MONTHLY
    if not co.products_configured():
        raise Http404
    try:
        ppg.change_product(sub.ppg_subscription_id, co.product_id(target), send_customer_notification=True)
    except ppg.PPGApiError as e:
        for msg in e.messages():
            messages.error(request, msg)
        return redirect('org_billing', slug=org.slug)
    _mark_pending(sub, f'switch:{target}')
    messages.success(request, _('Plan change requested. It takes effect at the next charge.'))
    return redirect('org_billing', slug=org.slug)


@login_required
@require_POST
def org_login_link(request, slug):
    org, sub, resp = _api_action(request, slug)
    if resp is not None:
        return resp
    try:
        ppg.send_onetime_login_email(customer_email=sub.customer_email or None,
                                     order_id=sub.ppg_initial_order_id or None)
    except ppg.PPGApiError as e:
        for msg in e.messages():
            messages.error(request, msg)
        return redirect('org_billing', slug=org.slug)
    messages.success(request, _('PayPro has emailed a one-time login link to the billing address. It is valid for 15 minutes.'))
    return redirect('org_billing', slug=org.slug)


# ---------------------------------------------------------------------------
# Pro help channel
# ---------------------------------------------------------------------------

@login_required
def org_help(request, slug):
    org = get_object_or_404(Organization, slug=slug)
    m = get_org_membership(request.user, org)
    if m is None:
        return HttpResponseForbidden()
    e = ents.for_organization(org)

    def free_view(submitted=False):
        trial = state_for(org, request.user)
        return render(request, 'billing/org_help.html', {
            'org': org, 'entitlements': e, 'form': None, 'submitted': submitted, 'is_owner': m.role == 'owner',
            'products_configured': co.products_configured(), 'trial': trial,
            'feature_used_up': trial.feature_exhausted('pro_help'), 'next_path': request.path,
        })

    if not trial_may(org, 'pro_help'):
        if request.method == 'POST':
            return HttpResponseForbidden()
        return free_view()

    submitted = False
    # The first request of a workspace that has never had a trial starts it
    # (change pro-trial-auto); the page says so above the form.
    starts_trial = not e.may('pro_help')
    if request.method == 'POST':
        form = ProHelpRequestForm(request.POST, organization=org)
        if form.is_valid():
            # Without the plan, a request spends the Pro trial's allowance
            # (change pro-trial-allowances) or starts the trial with it; a stale
            # tab past it gets the offer.
            if not e.has('pro_help') and not use(org, 'pro_help', actor=request.user):
                return free_view()
            flash_started(request, org)
            starts_trial = False
            req = form.save(commit=False)
            req.organization = org
            req.user = request.user
            req.save()
            from .tasks import send_pro_help_request
            transaction.on_commit(lambda: send_pro_help_request.delay(req.pk))
            ev.emit(ev.PRO_HELP_REQUESTED, request.user.pk,
                    {'org_id': org.pk, 'kind': req.kind, 'has_survey': req.survey_id is not None})
            submitted = True
            e = ents.for_organization(org)
            if not e.may('pro_help'):
                return free_view(submitted=True)
            form = ProHelpRequestForm(organization=org, initial={'contact_email': request.user.email})
    else:
        form = ProHelpRequestForm(organization=org, initial={'contact_email': request.user.email})
    return render(request, 'billing/org_help.html', {
        'org': org, 'entitlements': e, 'form': form, 'submitted': submitted, 'is_owner': m.role == 'owner',
        'products_configured': co.products_configured(), 'starts_trial': starts_trial,
    })


# ---------------------------------------------------------------------------
# Staff: payment links for a workspace (Django admin)
# ---------------------------------------------------------------------------

@staff_member_required
def admin_payment_links(request, org_id):
    """One page per workspace: make a monthly / yearly / quote link for a buyer
    who has no Mapsurvey account, and see the links made so far."""
    from django.contrib import admin as dj_admin

    from .features import PLAN_LABELS
    from .links import make_payment_link

    org = get_object_or_404(Organization, pk=org_id)
    link = nonce = link_label = ''
    if request.method == 'POST' and co.products_configured():
        choice = request.POST.get('product', '')
        key = co.PRODUCT_YEARLY if choice.startswith('pro_yearly') else co.PRODUCT_MONTHLY
        quote = choice == 'pro_yearly_quote'
        intent, link = make_payment_link(org, key, quote=quote, staff_user=request.user, request=request)
        nonce = str(intent.nonce)
        link_label = {'pro_monthly': 'Monthly payment link', 'pro_yearly': 'Yearly payment link',
                      'pro_yearly_quote': 'Yearly quote link'}[choice if choice in ('pro_monthly', 'pro_yearly', 'pro_yearly_quote') else 'pro_monthly']
    e = ents.for_organization(org)
    return render(request, 'admin/billing/payment_links.html', {
        **dj_admin.site.each_context(request),
        'title': 'Payment links', 'org': org, 'plan_label': PLAN_LABELS.get(e.plan, e.plan), 'until': e.until,
        'products_configured': co.products_configured(), 'test_mode': bool(settings.PPG_TEST_MODE),
        'link': link, 'nonce': nonce, 'link_label': link_label,
        'intents': CheckoutIntent.objects.filter(organization=org).select_related('user').order_by('-created_at')[:20],
    })
