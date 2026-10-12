"""Prove the PayPro configuration: product ids exist (with the API), or at
least print the checkout URLs and the IPN URL to configure (without it)."""
from django.conf import settings
from django.core.management.base import BaseCommand

from billing import checkout as co
from billing import ppg


class Command(BaseCommand):
    help = 'Check PPG_PRODUCTS against PayPro (API) or print what to configure.'

    def handle(self, *args, **options):
        products = settings.PPG_PRODUCTS
        self.stdout.write(f'PPG_PRODUCTS = {products!r}')
        self.stdout.write(f'IPN URL to set on every product / Integration tab: {settings.SITE_URL.rstrip("/")}/billing/ipn/')
        self.stdout.write(f'Thank-you redirect (Fulfilled): {settings.SITE_URL.rstrip("/")}/billing/return/')
        self.stdout.write(f'Thank-you redirect (Waiting for payment): {settings.SITE_URL.rstrip("/")}/billing/return/?pending=1')
        self.stdout.write(f'Keys set: secret={bool(settings.PPG_SECRET_KEY)} validation={bool(settings.PPG_VALIDATION_KEY)} '
                          f'api={ppg.is_configured()} accept_test_ipn={settings.PPG_ACCEPT_TEST_IPN} test_mode={settings.PPG_TEST_MODE}')
        if not co.products_configured():
            self.stdout.write(self.style.WARNING('Products not configured: Upgrade controls are hidden.'))
            return
        for key in co.PRODUCT_KEYS:
            self.stdout.write(f'  {key}: {co.CHECKOUT_BASE}?products[1][id]={co.product_id(key)}'
                              + ('&use-test-mode=true&secret-key=***' if settings.PPG_TEST_MODE else ''))
        if not ppg.is_configured():
            self.stdout.write(self.style.WARNING('No API key: open the URLs above by hand to verify the products.'))
            return
        try:
            data = ppg.store_products([co.product_id(k) for k in co.PRODUCT_KEYS])
        except ppg.PPGApiError as e:
            self.stderr.write(self.style.ERROR(f'API error: {e}'))
            return
        found = {str(p['id']): p for p in (data.get('response') or {}).get('storeProducts', [])}
        for key in co.PRODUCT_KEYS:
            pid = str(co.product_id(key))
            p = found.get(pid)
            if p:
                self.stdout.write(self.style.SUCCESS(f'  {key} = {pid}: {p.get("name")} (sku {p.get("sku")})'))
            else:
                self.stdout.write(self.style.ERROR(f'  {key} = {pid}: NOT FOUND in the store'))
