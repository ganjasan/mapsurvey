"""Daily: tell owners whose Pro trial ends within a week, once
(billing.tasks.notify_trials_ending run inline; change pro-trial-auto).

Scheduled from reclaim.sh (the daily Render cron) so it needs no beat process.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Email owners whose Pro trial ends within seven days (once per trial).'

    def handle(self, *args, **options):
        from billing.tasks import notify_trials_ending
        n = notify_trials_ending()
        self.stdout.write(f'notified {n} ending trial(s)')
