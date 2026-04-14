# Data migration: set all existing surveys to have all basemaps enabled

from django.db import migrations

DEFAULT_BASEMAPS = ['streets', 'satellite', 'topo']


def populate_basemaps(apps, schema_editor):
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    SurveyHeader.objects.filter(basemaps=[]).update(basemaps=DEFAULT_BASEMAPS)


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0027_surveyheader_basemaps'),
    ]

    operations = [
        migrations.RunPython(populate_basemaps, migrations.RunPython.noop),
    ]
