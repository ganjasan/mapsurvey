"""Daily: tell owners whose Pro ended, once (billing.tasks.notify_lapsed run inline).

Scheduled from reclaim.sh (the daily Render cron) so it needs no beat process.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Emit plan_lapsed and email owners for subscriptions whose entitlement turned Free.'

    def handle(self, *args, **options):
        from billing.tasks import notify_lapsed
        n = notify_lapsed()
        self.stdout.write(f'notified {n} lapsed subscription(s)')
