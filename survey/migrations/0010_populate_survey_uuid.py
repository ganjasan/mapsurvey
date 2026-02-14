import uuid

from django.db import migrations


def populate_uuids(apps, schema_editor):
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    for survey in SurveyHeader.objects.all():
        survey.uuid = uuid.uuid4()
        survey.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0009_add_survey_uuid'),
    ]

    operations = [
        migrations.RunPython(populate_uuids, migrations.RunPython.noop),
    ]
