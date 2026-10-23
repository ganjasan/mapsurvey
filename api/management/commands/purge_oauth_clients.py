"""Delete dynamically registered OAuth clients nobody ever authorised
(change oauth-server, D8). Runs nightly from reclaim.sh after purge_api_tokens.

Registration is open, so the table collects rows from scanners and from
connectors whose creator never finished the sign-in. A row older than 30 days
with no authorization code, no refresh token and no access token other than
its own RFC 7592 registration token has nothing to lose. Manually registered
(first-party) clients are never touched, whatever their age.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from oauth2_provider.models import Application
from oauth2_provider.settings import oauth2_settings

UNUSED_AFTER = timedelta(days=30)


def stale_clients(now=None):
    now = now or timezone.now()
    registration_scope = oauth2_settings.DCR_REGISTRATION_SCOPE
    return (
        Application.objects
        .filter(registration_source__in=[Application.RegistrationSource.DCR, Application.RegistrationSource.CIMD],
                created__lt=now - UNUSED_AFTER)
        .annotate(
            n_grants=Count('grant', distinct=True),
            n_refresh=Count('refreshtoken', distinct=True),
            n_access=Count('accesstoken', filter=~Q(accesstoken__scope=registration_scope), distinct=True),
        )
        .filter(n_grants=0, n_refresh=0, n_access=0)
    )


class Command(BaseCommand):
    help = 'Delete DCR/CIMD client registrations older than 30 days that were never authorised.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report without deleting.')

    def handle(self, *args, **options):
        qs = stale_clients()
        count = qs.count()
        if options['dry_run']:
            self.stdout.write(f'{count} stale client registration(s) would be deleted')
            return
        # Delete by pk list: the annotated queryset cannot be deleted directly.
        Application.objects.filter(pk__in=list(qs.values_list('pk', flat=True))).delete()
        self.stdout.write(f'{count} stale client registration(s) deleted')
