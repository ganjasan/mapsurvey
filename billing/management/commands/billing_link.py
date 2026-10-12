"""Print a payment link for an organisation: python manage.py billing_link <slug> --yearly [--quote]"""
from django.core.management.base import BaseCommand, CommandError

from billing import checkout as co
from billing.links import make_payment_link
from survey.models import Organization


class Command(BaseCommand):
    help = 'Payment (or quote) link tied to an organisation, for a buyer without a Mapsurvey account.'

    def add_arguments(self, parser):
        parser.add_argument('slug')
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument('--monthly', action='store_true')
        g.add_argument('--yearly', action='store_true')
        parser.add_argument('--quote', action='store_true', help='yearly only: PDF quote for procurement')

    def handle(self, *args, **o):
        try:
            org = Organization.objects.get(slug=o['slug'])
        except Organization.DoesNotExist:
            raise CommandError(f'no organisation with slug {o["slug"]!r}')
        if not co.products_configured():
            raise CommandError('PPG_PRODUCTS is not configured')
        key = co.PRODUCT_YEARLY if o['yearly'] else co.PRODUCT_MONTHLY
        intent, url = make_payment_link(org, key, quote=o['quote'])
        self.stdout.write(url)
        self.stderr.write(f'intent {intent.nonce} for {org.name} ({key}{", quote" if intent.quote else ""})')
