import sys

from django.core.management.base import BaseCommand, CommandError

from newsletter.models import Campaign, CampaignRecipient, NewsletterPreference
from newsletter.email_renderer import render_campaign_email
from newsletter.tasks import send_campaign_chunk


class Command(BaseCommand):
    help = 'Manage newsletter campaigns'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', help='Action to perform')

        # create
        create_parser = sub.add_parser('create', help='Create a new campaign')
        create_parser.add_argument('--subject', required=True)
        create_parser.add_argument('--body', help='HTML body string')
        create_parser.add_argument('--body-file', help='Read HTML body from file (- for stdin)')
        create_parser.add_argument('--preheader', default='')

        # list
        sub.add_parser('list', help='List all campaigns')

        # show
        show_parser = sub.add_parser('show', help='Show campaign details')
        show_parser.add_argument('campaign_id', type=int)

        # test-send
        test_parser = sub.add_parser('test-send', help='Send test email')
        test_parser.add_argument('campaign_id', type=int)
        test_parser.add_argument('--email', required=True)

        # send
        send_parser = sub.add_parser('send', help='Send campaign to all recipients')
        send_parser.add_argument('campaign_id', type=int)
        send_parser.add_argument('--sync', action='store_true', help='Send synchronously (no Celery)')

        # status
        status_parser = sub.add_parser('status', help='Show send status')
        status_parser.add_argument('campaign_id', type=int)

    def handle(self, *args, **options):
        action = options.get('action')
        if not action:
            self.print_help('manage.py', 'campaign')
            return

        handler = getattr(self, f'handle_{action.replace("-", "_")}', None)
        if handler:
            handler(options)
        else:
            raise CommandError(f'Unknown action: {action}')

    def handle_create(self, options):
        body = options.get('body') or ''
        body_file = options.get('body_file')

        if body_file:
            if body_file == '-':
                body = sys.stdin.read()
            else:
                with open(body_file, 'r') as f:
                    body = f.read()

        campaign = Campaign.objects.create(
            subject=options['subject'],
            body_html=body,
            preheader=options.get('preheader') or '',
        )
        self.stdout.write(self.style.SUCCESS(
            f'Campaign #{campaign.pk} created: "{campaign.subject}"'
        ))

    def handle_list(self, options):
        campaigns = Campaign.objects.all()[:20]
        if not campaigns:
            self.stdout.write('No campaigns.')
            return

        self.stdout.write(f'{"ID":<5} {"Status":<10} {"Sent":<6} {"Opened":<8} {"Subject"}')
        self.stdout.write('-' * 60)
        for c in campaigns:
            self.stdout.write(
                f'{c.pk:<5} {c.status:<10} {c.total_sent:<6} {c.total_opened:<8} {c.subject}'
            )

    def handle_show(self, options):
        campaign = self._get_campaign(options['campaign_id'])
        self.stdout.write(f'Campaign #{campaign.pk}')
        self.stdout.write(f'  Subject:    {campaign.subject}')
        self.stdout.write(f'  Preheader:  {campaign.preheader or "(empty)"}')
        self.stdout.write(f'  Status:     {campaign.status}')
        self.stdout.write(f'  Created:    {campaign.created_at}')
        self.stdout.write(f'  Sent at:    {campaign.sent_at or "-"}')
        self.stdout.write(f'  Recipients: {campaign.get_recipient_count()}')
        self.stdout.write(f'  Sent:       {campaign.total_sent}')
        self.stdout.write(f'  Opened:     {campaign.total_opened}')
        self.stdout.write(f'')
        self.stdout.write(f'Body HTML:')
        self.stdout.write(campaign.body_html or '(empty)')

    def handle_test_send(self, options):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        campaign = self._get_campaign(options['campaign_id'])
        email = options['email']

        # Use first superuser for personalization context
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.first()
        if not user:
            raise CommandError('No users in database')

        preference, _ = NewsletterPreference.objects.get_or_create(user=user)
        msg = render_campaign_email(campaign, user, preference)
        msg.to = [email]

        try:
            msg.send()
            self.stdout.write(self.style.SUCCESS(f'Test email sent to {email}'))
        except Exception as e:
            raise CommandError(f'Failed to send: {e}')

    def handle_send(self, options):
        campaign = self._get_campaign(options['campaign_id'])

        if not campaign.can_send():
            raise CommandError(f'Campaign status is "{campaign.status}", must be "draft"')

        recipient_count = campaign.get_recipient_count()
        self.stdout.write(f'Sending "{campaign.subject}" to {recipient_count} recipients...')

        Campaign.objects.filter(pk=campaign.pk, status='draft').update(
            status='sending',
            cursor_user_id=0,
            total_sent=0,
            total_opened=0,
        )

        if options.get('sync'):
            # Run synchronously without Celery
            while True:
                campaign.refresh_from_db()
                if campaign.status != 'sending':
                    break
                send_campaign_chunk(campaign.pk)

            campaign.refresh_from_db()
            self.stdout.write(self.style.SUCCESS(
                f'Done. Sent: {campaign.total_sent}, Status: {campaign.status}'
            ))
        else:
            send_campaign_chunk.delay(campaign.pk)
            self.stdout.write(self.style.SUCCESS(
                f'Campaign queued for sending via Celery.'
            ))

    def handle_status(self, options):
        campaign = self._get_campaign(options['campaign_id'])
        self.stdout.write(f'Campaign #{campaign.pk}: "{campaign.subject}"')
        self.stdout.write(f'  Status:  {campaign.status}')
        self.stdout.write(f'  Sent:    {campaign.total_sent}')
        self.stdout.write(f'  Opened:  {campaign.total_opened}')

        failed = CampaignRecipient.objects.filter(campaign=campaign, status='failed')
        if failed.exists():
            self.stdout.write(self.style.WARNING(f'  Failed:  {failed.count()}'))
            for r in failed[:10]:
                self.stdout.write(f'    - {r.user.email}: {r.error_message}')

    def _get_campaign(self, campaign_id):
        try:
            return Campaign.objects.get(pk=campaign_id)
        except Campaign.DoesNotExist:
            raise CommandError(f'Campaign #{campaign_id} not found')
