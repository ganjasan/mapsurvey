"""
Django management command to export a survey to ZIP archive.

Usage:
    python manage.py export_survey <survey_name> [--mode=structure|data|full] [--output=file.zip]
"""
import sys

from django.core.management.base import BaseCommand, CommandError

from survey.models import SurveyHeader
from survey.serialization import export_survey_to_zip, EXPORT_MODES, ExportError


class Command(BaseCommand):
    help = 'Export a survey to ZIP archive'

    def add_arguments(self, parser):
        parser.add_argument(
            'survey_name',
            type=str,
            help='Name of the survey to export'
        )
        parser.add_argument(
            '--mode',
            type=str,
            choices=EXPORT_MODES,
            default='structure',
            help='Export mode: structure (default), data, or full'
        )
        parser.add_argument(
            '--output',
            '-o',
            type=str,
            default=None,
            help='Output file path. If not specified, outputs to stdout.'
        )

    def handle(self, *args, **options):
        survey_name = options['survey_name']
        mode = options['mode']
        output_path = options['output']

        # Find survey
        try:
            survey = SurveyHeader.objects.get(name=survey_name)
        except SurveyHeader.DoesNotExist:
            raise CommandError(f"Survey '{survey_name}' not found")

        # Export
        try:
            if output_path:
                with open(output_path, 'wb') as f:
                    warnings = export_survey_to_zip(survey, f, mode)

                self.stdout.write(
                    self.style.SUCCESS(f"Survey '{survey_name}' exported to {output_path}")
                )
            else:
                # Output to stdout (binary mode)
                warnings = export_survey_to_zip(survey, sys.stdout.buffer, mode)

            # Show warnings
            for warning in warnings:
                self.stderr.write(self.style.WARNING(f"Warning: {warning}"))

        except ExportError as e:
            raise CommandError(str(e))
