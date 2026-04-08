import uuid as uuid_module

from django.conf import settings
from django.db import models
from django.utils import timezone


CAMPAIGN_STATUS_CHOICES = (
    ('draft', 'Draft'),
    ('sending', 'Sending'),
    ('sent', 'Sent'),
    ('failed', 'Failed'),
)

RECIPIENT_STATUS_CHOICES = (
    ('sent', 'Sent'),
    ('failed', 'Failed'),
    ('skipped', 'Skipped'),
)

BOUNCE_TYPE_CHOICES = (
    ('hard', 'Hard'),
    ('soft', 'Soft'),
)


class Campaign(models.Model):
    subject = models.CharField(max_length=998)
    preheader = models.CharField(max_length=150, blank=True)
    body_html = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=CAMPAIGN_STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_campaigns',
    )
    cursor_user_id = models.IntegerField(default=0)
    total_sent = models.IntegerField(default=0)
    total_opened = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.subject

    def can_send(self):
        return self.status == 'draft'

    def get_recipient_queryset(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return (
            User.objects.filter(is_active=True)
            .exclude(newsletter_preference__is_unsubscribed=True)
            .order_by('pk')
        )

    def get_recipient_count(self):
        return self.get_recipient_queryset().count()


class NewsletterPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='newsletter_preference',
    )
    unsubscribe_token = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    is_unsubscribed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        status = 'unsubscribed' if self.is_unsubscribed else 'subscribed'
        return f'{self.user} ({status})'

    def unsubscribe(self):
        self.is_unsubscribed = True
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=['is_unsubscribed', 'unsubscribed_at'])


class CampaignRecipient(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='recipients')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='campaign_receipts',
    )
    status = models.CharField(max_length=10, choices=RECIPIENT_STATUS_CHOICES, default='sent')
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        unique_together = ('campaign', 'user')

    def __str__(self):
        return f'{self.campaign} → {self.user} ({self.status})'


class BounceRecord(models.Model):
    email = models.EmailField(db_index=True)
    bounce_type = models.CharField(max_length=4, choices=BOUNCE_TYPE_CHOICES)
    received_at = models.DateTimeField(auto_now_add=True)
    raw_payload = models.TextField(blank=True)

    def __str__(self):
        return f'{self.email} ({self.bounce_type})'
