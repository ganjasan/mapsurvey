import logging

from celery import shared_task
from django.core.mail import get_connection
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_campaign_chunk(self, campaign_id, chunk_size=CHUNK_SIZE):
    from .models import Campaign, CampaignRecipient, NewsletterPreference
    from .email_renderer import render_campaign_email

    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        logger.error('Campaign %s does not exist', campaign_id)
        return

    if campaign.status != 'sending':
        logger.info('Campaign %s status is %s, skipping', campaign_id, campaign.status)
        return

    users = list(
        campaign.get_recipient_queryset()
        .exclude(campaign_receipts__campaign=campaign, campaign_receipts__status='sent')
        .filter(pk__gt=campaign.cursor_user_id)[:chunk_size]
    )

    if not users:
        Campaign.objects.filter(pk=campaign_id).update(
            status='sent',
            sent_at=timezone.now(),
        )
        logger.info('Campaign %s finished sending', campaign_id)
        return

    sent_count = 0
    last_user_pk = campaign.cursor_user_id

    try:
        connection = get_connection(fail_silently=False)
        connection.open()
    except Exception as exc:
        logger.error('Failed to open SMTP connection for campaign %s: %s', campaign_id, exc)
        raise self.retry(exc=exc)

    try:
        for user in users:
            last_user_pk = user.pk

            preference, _ = NewsletterPreference.objects.get_or_create(user=user)

            try:
                msg = render_campaign_email(campaign, user, preference)
                msg.connection = connection
                msg.send()

                CampaignRecipient.objects.update_or_create(
                    campaign=campaign,
                    user=user,
                    defaults={
                        'status': 'sent',
                        'sent_at': timezone.now(),
                        'error_message': '',
                    },
                )
                sent_count += 1
            except Exception as e:
                logger.warning(
                    'Failed to send campaign %s to %s: %s',
                    campaign_id, user.email, e,
                )
                CampaignRecipient.objects.update_or_create(
                    campaign=campaign,
                    user=user,
                    defaults={
                        'status': 'failed',
                        'error_message': f'{type(e).__name__}: {e}',
                    },
                )
    finally:
        try:
            connection.close()
        except Exception:
            pass

        Campaign.objects.filter(pk=campaign_id).update(
            cursor_user_id=last_user_pk,
            total_sent=F('total_sent') + sent_count,
        )

    if len(users) == chunk_size:
        send_campaign_chunk.apply_async((campaign_id,), countdown=2)
    else:
        Campaign.objects.filter(pk=campaign_id).update(
            status='sent',
            sent_at=timezone.now(),
        )
        logger.info('Campaign %s finished sending', campaign_id)
