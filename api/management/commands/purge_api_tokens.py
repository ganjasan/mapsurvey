"""Delete personal tokens that expired or were revoked more than 30 days ago.

Run nightly from reclaim.sh. Expired and revoked tokens are refused by
`authenticate()` the moment they end; the 30 days keep them visible in the
admin and the audit trail readable, then the rows go.
"""
from django.core.management.base import BaseCommand

from api import tokens


class Command(BaseCommand):
    help = 'Delete API tokens expired or revoked more than 30 days ago.'

    def handle(self, *args, **options):
        count = tokens.purge_ended()
        self.stdout.write(f'purge_api_tokens: deleted {count}')
