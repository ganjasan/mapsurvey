"""
Django management command to export a survey to ZIP archive.

Usage:
    python manage.py export_survey <survey_name_or_uuid> [--mode=structure|data|full] [--output=file.zip]
"""
import sys
import uuid as uuid_mod

from django.core.management.base import BaseCommand, CommandError

from survey.models import SurveyHeader
from survey.serialization import export_survey_to_zip, EXPORT_MODES, ExportError


class Command(BaseCommand):
    help = 'Export a survey to ZIP archive'

    def add_arguments(self, parser):
        parser.add_argument(
            'survey_identifier',
            type=str,
            help='Name or UUID of the survey to export'
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
        identifier = options['survey_identifier']
        mode = options['mode']
        output_path = options['output']

        # Try UUID first, then name
        try:
            parsed_uuid = uuid_mod.UUID(identifier)
            survey = SurveyHeader.objects.get(uuid=parsed_uuid)
        except (ValueError, SurveyHeader.DoesNotExist):
            matches = SurveyHeader.objects.filter(name=identifier)
            count = matches.count()
            if count == 0:
                raise CommandError(f"Survey '{identifier}' not found")
            if count > 1:
                lines = [f"Multiple surveys found with name '{identifier}':"]
                for s in matches:
                    lines.append(f"  - {s.uuid} ({s.name})")
                raise CommandError("\n".join(lines))
            survey = matches.first()

        # Export
        try:
            if output_path:
                with open(output_path, 'wb') as f:
                    warnings = export_survey_to_zip(survey, f, mode)

                self.stdout.write(
                    self.style.SUCCESS(f"Survey '{survey.name}' exported to {output_path}")
                )
            else:
                # Output to stdout (binary mode)
                warnings = export_survey_to_zip(survey, sys.stdout.buffer, mode)

            # Show warnings
            for warning in warnings:
                self.stderr.write(self.style.WARNING(f"Warning: {warning}"))

        except ExportError as e:
            raise CommandError(str(e))
