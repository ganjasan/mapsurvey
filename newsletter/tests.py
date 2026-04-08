from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Campaign, CampaignRecipient, NewsletterPreference
from .tasks import send_campaign_chunk

User = get_user_model()


def _create_user(username, email, is_active=True):
    return User.objects.create_user(
        username=username,
        email=email,
        password='testpass123',
        is_active=is_active,
    )


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    NEWSLETTER_SITE_URL='https://test.mapsurvey.org',
    NEWSLETTER_PHYSICAL_ADDRESS='Test Address, 123',
)
class CampaignModelTest(TestCase):
    """Tests for Campaign model methods."""

    def test_can_send_returns_true_for_draft(self):
        """GIVEN a campaign with draft status
        WHEN can_send() is called
        THEN it returns True
        """
        campaign = Campaign.objects.create(subject='Test', status='draft')
        self.assertTrue(campaign.can_send())

    def test_can_send_returns_false_for_sent(self):
        """GIVEN a campaign with sent status
        WHEN can_send() is called
        THEN it returns False
        """
        campaign = Campaign.objects.create(subject='Test', status='sent')
        self.assertFalse(campaign.can_send())

    def test_get_recipient_queryset_excludes_unsubscribed(self):
        """GIVEN two users, one unsubscribed
        WHEN get_recipient_queryset() is called
        THEN it excludes the unsubscribed user
        """
        user1 = _create_user('alice', 'alice@example.com')
        user2 = _create_user('bob', 'bob@example.com')
        NewsletterPreference.objects.create(user=user2, is_unsubscribed=True)

        campaign = Campaign.objects.create(subject='Test')
        recipients = campaign.get_recipient_queryset()

        self.assertIn(user1, recipients)
        self.assertNotIn(user2, recipients)

    def test_get_recipient_queryset_excludes_inactive_users(self):
        """GIVEN an active and an inactive user
        WHEN get_recipient_queryset() is called
        THEN it excludes the inactive user
        """
        user1 = _create_user('alice', 'alice@example.com')
        _create_user('inactive', 'inactive@example.com', is_active=False)

        campaign = Campaign.objects.create(subject='Test')
        recipients = list(campaign.get_recipient_queryset())

        self.assertEqual(recipients, [user1])


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    NEWSLETTER_SITE_URL='https://test.mapsurvey.org',
    NEWSLETTER_PHYSICAL_ADDRESS='Test Address, 123',
)
class SendCampaignChunkTest(TestCase):
    """Tests for the send_campaign_chunk Celery task."""

    def setUp(self):
        self.user1 = _create_user('alice', 'alice@example.com')
        self.user2 = _create_user('bob', 'bob@example.com')
        self.user3 = _create_user('charlie', 'charlie@example.com')
        self.campaign = Campaign.objects.create(
            subject='Test Campaign',
            body_html='<p>Hello!</p>',
            status='sending',
        )

    def test_sends_to_active_users(self):
        """GIVEN a campaign in sending status with active users
        WHEN send_campaign_chunk is called
        THEN emails are sent to all active users
        """
        send_campaign_chunk(self.campaign.pk)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'sent')
        self.assertEqual(self.campaign.total_sent, 3)
        self.assertIsNotNone(self.campaign.sent_at)
        self.assertEqual(len(mail.outbox), 3)

    def test_skips_unsubscribed_users(self):
        """GIVEN a campaign and one unsubscribed user
        WHEN send_campaign_chunk is called
        THEN the unsubscribed user does not receive an email
        """
        NewsletterPreference.objects.create(user=self.user2, is_unsubscribed=True)

        send_campaign_chunk(self.campaign.pk)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.total_sent, 2)
        self.assertEqual(len(mail.outbox), 2)
        recipient_emails = [m.to[0] for m in mail.outbox]
        self.assertNotIn('bob@example.com', recipient_emails)

    def test_logs_smtp_failures(self):
        """GIVEN a campaign where sending to one user fails at SMTP level
        WHEN send_campaign_chunk is called
        THEN the failure is logged in CampaignRecipient with error message
        """
        from .email_renderer import render_campaign_email as real_render

        def render_with_failure(campaign, user, preference, site_url=None):
            msg = real_render(campaign, user, preference, site_url)
            if user.pk == self.user2.pk:
                msg.send = MagicMock(side_effect=Exception('SMTP error'))
            return msg

        with patch('newsletter.email_renderer.render_campaign_email', side_effect=render_with_failure):
            send_campaign_chunk(self.campaign.pk)

        failed = CampaignRecipient.objects.filter(campaign=self.campaign, status='failed')
        self.assertEqual(failed.count(), 1)
        self.assertEqual(failed.first().user, self.user2)
        self.assertIn('SMTP error', failed.first().error_message)

    def test_updates_cursor_for_crash_recovery(self):
        """GIVEN a campaign with chunk_size=1
        WHEN send_campaign_chunk is called
        THEN cursor_user_id is updated after each chunk
        """
        # Use chunk_size=1 so it processes one at a time, then re-queues
        with patch.object(send_campaign_chunk, 'apply_async') as mock_requeue:
            send_campaign_chunk(self.campaign.pk, chunk_size=1)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.cursor_user_id, self.user1.pk)
        mock_requeue.assert_called_once()

    def test_no_duplicate_recipients_on_retry(self):
        """GIVEN a campaign with an existing CampaignRecipient for user1
        WHEN send_campaign_chunk is called
        THEN user1 is skipped (no duplicate)
        """
        CampaignRecipient.objects.create(
            campaign=self.campaign,
            user=self.user1,
            status='sent',
            sent_at=timezone.now(),
        )

        send_campaign_chunk(self.campaign.pk)

        self.assertEqual(
            CampaignRecipient.objects.filter(campaign=self.campaign, user=self.user1).count(),
            1,
        )
        self.campaign.refresh_from_db()
        # user1 was skipped, user2 and user3 were sent
        self.assertEqual(self.campaign.total_sent, 2)

    def test_skips_non_sending_campaign(self):
        """GIVEN a campaign with draft status
        WHEN send_campaign_chunk is called
        THEN no emails are sent
        """
        self.campaign.status = 'draft'
        self.campaign.save()

        send_campaign_chunk(self.campaign.pk)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(CampaignRecipient.objects.count(), 0)


@override_settings(
    NEWSLETTER_SITE_URL='https://test.mapsurvey.org',
    NEWSLETTER_PHYSICAL_ADDRESS='Test Address, 123',
)
class UnsubscribeViewTest(TestCase):
    """Tests for the unsubscribe views."""

    def setUp(self):
        self.user = _create_user('alice', 'alice@example.com')
        self.preference = NewsletterPreference.objects.create(user=self.user)

    def test_get_shows_confirmation_page(self):
        """GIVEN a valid unsubscribe token
        WHEN GET request to unsubscribe URL
        THEN confirmation page is shown
        """
        url = reverse('newsletter:unsubscribe', args=[self.preference.unsubscribe_token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alice@example.com')
        self.assertContains(response, 'Unsubscribe')

    def test_post_unsubscribes_user(self):
        """GIVEN a valid unsubscribe token
        WHEN POST request to unsubscribe URL
        THEN user is unsubscribed
        """
        url = reverse('newsletter:unsubscribe', args=[self.preference.unsubscribe_token])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.preference.refresh_from_db()
        self.assertTrue(self.preference.is_unsubscribed)
        self.assertIsNotNone(self.preference.unsubscribed_at)

    def test_invalid_token_returns_404(self):
        """GIVEN an invalid unsubscribe token
        WHEN GET request to unsubscribe URL
        THEN 404 is returned
        """
        import uuid
        url = reverse('newsletter:unsubscribe', args=[uuid.uuid4()])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


@override_settings(
    NEWSLETTER_SITE_URL='https://test.mapsurvey.org',
    NEWSLETTER_PHYSICAL_ADDRESS='Test Address, 123',
)
class OneClickUnsubscribeTest(TestCase):
    """Tests for RFC 8058 one-click unsubscribe."""

    def setUp(self):
        self.user = _create_user('alice', 'alice@example.com')
        self.preference = NewsletterPreference.objects.create(user=self.user)

    def test_post_unsubscribes(self):
        """GIVEN a valid token
        WHEN POST to one-click endpoint with List-Unsubscribe=One-Click
        THEN user is unsubscribed and 200 returned
        """
        url = reverse('newsletter:unsubscribe_one_click', args=[self.preference.unsubscribe_token])
        response = self.client.post(url, data='List-Unsubscribe=One-Click', content_type='application/x-www-form-urlencoded')

        self.assertEqual(response.status_code, 200)
        self.preference.refresh_from_db()
        self.assertTrue(self.preference.is_unsubscribed)

    def test_get_returns_405(self):
        """GIVEN a valid token
        WHEN GET to one-click endpoint
        THEN 405 Method Not Allowed is returned
        """
        url = reverse('newsletter:unsubscribe_one_click', args=[self.preference.unsubscribe_token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    NEWSLETTER_SITE_URL='https://test.mapsurvey.org',
    NEWSLETTER_PHYSICAL_ADDRESS='Test Address, 123',
)
class TrackOpenViewTest(TestCase):
    """Tests for the open tracking pixel view."""

    def setUp(self):
        self.user = _create_user('alice', 'alice@example.com')
        self.campaign = Campaign.objects.create(
            subject='Test',
            body_html='<p>Hello</p>',
            status='sent',
        )
        self.recipient = CampaignRecipient.objects.create(
            campaign=self.campaign,
            user=self.user,
            status='sent',
            sent_at=timezone.now(),
        )

    def test_track_open_sets_opened_at(self):
        """GIVEN a sent campaign recipient
        WHEN pixel URL is requested
        THEN opened_at is set and image/gif is returned
        """
        url = reverse('newsletter:track_open', args=[self.campaign.pk, self.user.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/gif')
        self.recipient.refresh_from_db()
        self.assertIsNotNone(self.recipient.opened_at)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.total_opened, 1)

    def test_track_open_is_idempotent(self):
        """GIVEN a recipient that already has opened_at set
        WHEN pixel URL is requested again
        THEN opened_at is not changed and total_opened stays same
        """
        url = reverse('newsletter:track_open', args=[self.campaign.pk, self.user.pk])
        self.client.get(url)

        self.recipient.refresh_from_db()
        first_opened = self.recipient.opened_at

        self.client.get(url)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.opened_at, first_opened)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.total_opened, 1)

    def test_track_open_returns_gif_for_unknown(self):
        """GIVEN a non-existent campaign/user combo
        WHEN pixel URL is requested
        THEN image/gif is still returned (no 404)
        """
        url = reverse('newsletter:track_open', args=[99999, 99999])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/gif')


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    NEWSLETTER_SITE_URL='https://test.mapsurvey.org',
    NEWSLETTER_PHYSICAL_ADDRESS='Test Address, 123',
)
class EmailRenderingTest(TestCase):
    """Tests for email rendering output."""

    def test_email_has_list_unsubscribe_header(self):
        """GIVEN a campaign and user
        WHEN render_campaign_email is called
        THEN the email has List-Unsubscribe header
        """
        from .email_renderer import render_campaign_email

        user = _create_user('alice', 'alice@example.com')
        preference = NewsletterPreference.objects.create(user=user)
        campaign = Campaign.objects.create(subject='Test', body_html='<p>Hi</p>')

        msg = render_campaign_email(campaign, user, preference)

        self.assertIn('List-Unsubscribe', msg.extra_headers)
        self.assertIn('List-Unsubscribe-Post', msg.extra_headers)
        self.assertIn(str(preference.unsubscribe_token), msg.extra_headers['List-Unsubscribe'])

    def test_email_contains_physical_address(self):
        """GIVEN a campaign
        WHEN render_campaign_email is called
        THEN the HTML body contains the physical address
        """
        from .email_renderer import render_campaign_email

        user = _create_user('alice', 'alice@example.com')
        preference = NewsletterPreference.objects.create(user=user)
        campaign = Campaign.objects.create(subject='Test', body_html='<p>Hi</p>')

        msg = render_campaign_email(campaign, user, preference)
        html_body = msg.alternatives[0][0]

        self.assertIn('Test Address, 123', html_body)

    def test_email_contains_tracking_pixel(self):
        """GIVEN a campaign
        WHEN render_campaign_email is called
        THEN the HTML body contains the tracking pixel img
        """
        from .email_renderer import render_campaign_email

        user = _create_user('alice', 'alice@example.com')
        preference = NewsletterPreference.objects.create(user=user)
        campaign = Campaign.objects.create(subject='Test', body_html='<p>Hi</p>')

        msg = render_campaign_email(campaign, user, preference)
        html_body = msg.alternatives[0][0]

        self.assertIn(f'/nl/track/{campaign.pk}/{user.pk}/open.gif', html_body)

    def test_email_has_text_alternative(self):
        """GIVEN a campaign with HTML body
        WHEN render_campaign_email is called
        THEN the email has a plain text body
        """
        from .email_renderer import render_campaign_email

        user = _create_user('alice', 'alice@example.com')
        preference = NewsletterPreference.objects.create(user=user)
        campaign = Campaign.objects.create(subject='Test', body_html='<p>Hello World</p>')

        msg = render_campaign_email(campaign, user, preference)

        self.assertIn('Hello World', msg.body)
