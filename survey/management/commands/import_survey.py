"""
Django management command to import a survey from ZIP archive.

Usage:
    python manage.py import_survey <file.zip>
    cat file.zip | python manage.py import_survey -
"""
import sys
import os

from django.core.management.base import BaseCommand, CommandError

from survey.serialization import import_survey_from_zip, ImportError as SerializationImportError


class Command(BaseCommand):
    help = 'Import a survey from ZIP archive'

    def add_arguments(self, parser):
        parser.add_argument(
            'file',
            type=str,
            help='Path to ZIP file, or "-" to read from stdin'
        )

    def handle(self, *args, **options):
        file_path = options['file']

        # Read from stdin or file
        try:
            if file_path == '-':
                # Read from stdin
                input_file = sys.stdin.buffer
            else:
                # Check file exists
                if not os.path.exists(file_path):
                    raise CommandError(f"File '{file_path}' not found")

                input_file = open(file_path, 'rb')
        except IOError as e:
            raise CommandError(f"Cannot read file: {e}")

        # Import
        try:
            survey, warnings = import_survey_from_zip(input_file)

            # Show warnings
            for warning in warnings:
                self.stderr.write(self.style.WARNING(f"Warning: {warning}"))

            if survey:
                self.stdout.write(
                    self.style.SUCCESS(f"Survey '{survey.name}' imported successfully")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("Data imported successfully")
                )

        except SerializationImportError as e:
            raise CommandError(str(e))

        finally:
            if file_path != '-' and 'input_file' in locals():
                input_file.close()
