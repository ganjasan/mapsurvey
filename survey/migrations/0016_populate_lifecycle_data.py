"""
Data migration:
- Set status='published' for all existing surveys (preserves current unrestricted access)
- Set status='archived' for surveys where is_archived=True
- Populate test_token with unique UUIDs for all existing surveys
"""
import uuid as uuid_module
from django.db import migrations


def populate_lifecycle_data(apps, schema_editor):
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    for survey in SurveyHeader.objects.all():
        if survey.is_archived:
            survey.status = 'archived'
        else:
            survey.status = 'published'
        survey.test_token = uuid_module.uuid4()
        survey.save(update_fields=['status', 'test_token'])


def reverse_lifecycle_data(apps, schema_editor):
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    SurveyHeader.objects.all().update(status='draft', test_token=None)


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0015_add_lifecycle_fields'),
    ]

    operations = [
        migrations.RunPython(populate_lifecycle_data, reverse_lifecycle_data),
    ]
