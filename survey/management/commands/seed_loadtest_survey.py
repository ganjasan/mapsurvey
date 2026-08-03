"""
Seed a published one-question point survey for load testing.

Reproduces the shape of the survey that collapsed under a lecture-hall burst on
2026-07-13: a single section with one `point` question. Used to give a Render PR
preview (which always starts with an empty database) something to load-test, so
baseline and fixed builds are measured against identical content.

Idempotent — re-running returns the existing survey instead of creating a second.

Usage:
    python manage.py seed_loadtest_survey
    python manage.py seed_loadtest_survey --name my-load-test
"""
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from survey.models import Organization, Question, SurveyHeader, SurveySection


class Command(BaseCommand):
    help = 'Seed a published single-point survey for load testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            default='loadtest-lecture',
            help='Survey name (default: loadtest-lecture)',
        )

    def handle(self, *args, **options):
        name = options['name']

        existing = SurveyHeader.objects.filter(name=name, is_canonical=True).first()
        if existing:
            self.stdout.write(f'Survey "{name}" already exists.')
            self._report(existing)
            return

        org, _ = Organization.objects.get_or_create(
            slug='loadtest',
            defaults={'name': 'Load Test'},
        )
        survey = SurveyHeader.objects.create(
            name=name,
            organization=org,
            status='published',
        )
        section = SurveySection.objects.create(
            survey_header=survey,
            name='section_1',
            title='Where are you from?',
            subheading='Drop a pin on your place of origin',
            code='S1',
            is_head=True,
            start_map_postion=Point(13.405, 52.52),
            start_map_zoom=4,
        )
        Question.objects.create(
            survey_section=section,
            code='Q001',
            order_number=1,
            name='Your place of origin',
            input_type='point',
            required=True,
        )

        self.stdout.write(self.style.SUCCESS(f'Created survey "{name}".'))
        self._report(survey)

    def _report(self, survey):
        self.stdout.write(f'uuid:   {survey.uuid}')
        self.stdout.write(f'status: {survey.status}')
        self.stdout.write(f'path:   /surveys/{survey.uuid}/section_1/')
