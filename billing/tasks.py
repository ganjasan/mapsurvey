"""Celery tasks of the billing app: the two Pro help mails and the lapse notice.

Same rules as survey/tasks.py: `fail_silently=False` so a transport failure
raises and Celery retries; past the last retry the task_failure receiver in
mapsurvey/celery.py reports it. The stored row is never at risk -- the view
commits before enqueueing.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_pro_help_request(self, request_id):
    from django.urls import reverse

    from survey.mail import absolute_url, send_templated_mail

    from .models import ProHelpRequest

    try:
        req = ProHelpRequest.objects.select_related('organization', 'user', 'survey').get(pk=request_id)
    except ProHelpRequest.DoesNotExist:
        logger.warning('pro help request %s: row gone before send', request_id)
        return
    context = {
        'req': req,
        'org': req.organization,
        'admin_url': absolute_url(reverse('admin:billing_prohelprequest_change', args=[req.pk])),
        'survey_url': absolute_url(reverse('editor_survey_detail', args=[req.survey.uuid])) if req.survey else '',
    }
    try:
        send_templated_mail('billing/email/help_request_team', settings.CONTACT_EMAIL,
                            f'[Pro] {req.get_kind_display()} — {req.organization.name}', context, fail_silently=False)
        send_templated_mail('billing/email/help_request_confirm', req.contact_email,
                            'We received your request — Mapsurvey Pro', context, fail_silently=False)
    except Exception as exc:  # noqa: BLE001 -- retried, then reported by task_failure
        raise self.retry(exc=exc)


@shared_task
def notify_lapsed():
    """Once per subscription whose entitlement turned Free: `plan_lapsed` and an
    email to the owners. PayPro already mailed about the payment; ours is about
    the service. Idempotent through `lapse_notified_at`."""
    from survey.mail import send_templated_mail
    from survey.models import Membership

    from . import events as ev
    from .entitlements import for_subscription
    from .models import Subscription

    now = timezone.now()
    count = 0
    for sub in Subscription.objects.filter(lapse_notified_at__isnull=True).exclude(current_period_end__isnull=True):
        if for_subscription(sub, now).is_pro:
            continue
        sub.lapse_notified_at = now
        sub.save(update_fields=['lapse_notified_at', 'updated_at'])
        owners = Membership.objects.filter(organization=sub.organization, role='owner').select_related('user')
        for m in owners:
            ev.emit(ev.PLAN_LAPSED, m.user_id, {'org_id': sub.organization_id, 'status': sub.status,
                                                 'ppg_subscription_id': sub.ppg_subscription_id})
            if m.user.email:
                send_templated_mail('billing/email/plan_lapsed', m.user.email,
                                    f'Your Mapsurvey Pro plan has ended — {sub.organization.name}',
                                    {'org': sub.organization, 'sub': sub}, fail_silently=True)
        count += 1
    return count


# The Pro trial's two mails (change pro-trial-auto, #508). The owner the trial
# belongs to hears when it starts -- possibly through an editor's first Pro use
# or an API call they never saw -- and once more seven days before it ends.

TRIAL_FEATURE_PHRASES = {
    'unbranded': 'by removing the "Made with Mapsurvey" badge from a survey',
    'pro_help': 'by sending a request to the Mapsurvey team',
    'api': 'with a call to the API or the MCP server',
    'operator_entry': 'by entering a paper response',
}
TRIAL_ENDING_DAYS = 7


def _trial_context(grant):
    from django.urls import reverse

    from survey.mail import absolute_url

    from .trial import unit_label

    rows = list(grant.allowances.all())
    return {
        'grant': grant, 'org': grant.organization, 'owner': grant.claimed_by,
        'started_by': grant.started_by,
        'started_by_other': grant.started_by_id is not None and grant.started_by_id != grant.claimed_by_id,
        'how': TRIAL_FEATURE_PHRASES.get(grant.trigger, ''),
        'allowances': [{'label': unit_label(a.feature), 'limit': a.limit, 'used': a.used} for a in rows],
        'features': {a.feature for a in rows},
        'billing_url': absolute_url(reverse('org_billing', args=[grant.organization.slug])) + '#pro-trial',
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_trial_started(self, grant_id):
    from survey.mail import send_templated_mail

    from .models import EntitlementGrant

    grant = (EntitlementGrant.objects.select_related('organization', 'claimed_by', 'started_by')
             .filter(pk=grant_id).first())
    if grant is None or grant.claimed_by is None or not grant.claimed_by.email:
        return
    try:
        send_templated_mail('billing/email/trial_started', grant.claimed_by.email,
                            f'Your free Pro trial has started — {grant.organization.name}',
                            _trial_context(grant), fail_silently=False)
    except Exception as exc:  # noqa: BLE001 -- retried, then reported by task_failure
        raise self.retry(exc=exc)


@shared_task
def notify_trials_ending():
    """Once per live trial that ends within TRIAL_ENDING_DAYS: one mail to the
    owner it belongs to and `trial_ending_notified`. Skips revoked grants and
    workspaces that are Pro now. Idempotent through `ending_notified_at`; a
    missed day is caught up by the next run (a window, not an exact date)."""
    from datetime import timedelta

    from survey.mail import send_templated_mail

    from . import events as ev
    from .entitlements import for_organization
    from .models import GRANT_KIND_TRIAL, EntitlementGrant

    now = timezone.now()
    grants = (EntitlementGrant.objects.select_related('organization', 'claimed_by', 'started_by')
              .filter(kind=GRANT_KIND_TRIAL, revoked_at__isnull=True, ending_notified_at__isnull=True,
                      starts_at__lte=now, expires_at__gt=now,
                      expires_at__lte=now + timedelta(days=TRIAL_ENDING_DAYS)))
    count = 0
    for grant in grants:
        if for_organization(grant.organization).is_pro:
            continue
        grant.ending_notified_at = now
        grant.save(update_fields=['ending_notified_at'])
        owner = grant.claimed_by
        if owner is not None:
            ev.emit(ev.TRIAL_ENDING_NOTIFIED, owner.pk, {'org_id': grant.organization_id})
            if owner.email:
                send_templated_mail('billing/email/trial_ending', owner.email,
                                    f'Your free Pro trial ends on {grant.expires_at:%-d %B} — '
                                    f'{grant.organization.name}',
                                    _trial_context(grant), fail_silently=True)
        count += 1
    return count
