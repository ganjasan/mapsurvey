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
