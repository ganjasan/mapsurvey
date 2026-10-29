"""Give accounts without an EmailVerification row one (change login-grace-period, #487).

Migration 0111 did this once. Run it again right after the deploy that shipped
the change: for about a minute the old instance still registered accounts the
old way (`is_active=False`, no row), which the new code would read as banned.
Idempotent — accounts that already have a row are not touched.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from survey.email_verification import sync_accounts
from survey.models import ContentReview, EmailVerification


class Command(BaseCommand):
    help = 'Create missing EmailVerification rows by the login-grace-period rule.'

    def handle(self, *args, **options):
        confirmed, unconfirmed = sync_accounts(get_user_model(), EmailVerification, ContentReview)
        self.stdout.write(f'created {confirmed} confirmed, {unconfirmed} unconfirmed')
