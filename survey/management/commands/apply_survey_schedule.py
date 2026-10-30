"""Close published surveys whose closing time has passed (change survey-schedule, #497).

The Celery beat task `survey.tasks.apply_survey_schedule` runs the same function every five
minutes; this command is for operators and for a preview whose worker is asleep.
"""
from django.core.management.base import BaseCommand

from survey.schedule import close_due


class Command(BaseCommand):
    help = 'Close published surveys whose closing time has passed.'

    def handle(self, *args, **options):
        closed = close_due()
        self.stdout.write(f'Closed {closed} survey(s).')
