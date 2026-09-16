# Change layer-memory-diet, stage 3: the derived FeatureCollection moves from a
# TextField to gzip bytes (8.6 MB → 2.4 MB per layer 91-sized row). Rows are
# compressed one at a time by pk so the migration never holds more than one
# layer's text; a row whose text is empty (never rebuilt) becomes NULL.
import gzip

from django.db import migrations, models


def forwards(apps, schema_editor):
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')
    for pk in list(SurveyMapLayer.objects.values_list('pk', flat=True)):
        text = SurveyMapLayer.objects.filter(pk=pk).values_list('geojson', flat=True).first() or ''
        SurveyMapLayer.objects.filter(pk=pk).update(
            geojson_gz=gzip.compress(text.encode('utf-8'), compresslevel=6) if text else None)


def backwards(apps, schema_editor):
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')
    for pk in list(SurveyMapLayer.objects.values_list('pk', flat=True)):
        data = SurveyMapLayer.objects.filter(pk=pk).values_list('geojson_gz', flat=True).first()
        SurveyMapLayer.objects.filter(pk=pk).update(
            geojson=gzip.decompress(bytes(data)).decode('utf-8') if data else '')


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0085_surveyimportjob'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveymaplayer',
            name='geojson_gz',
            field=models.BinaryField(blank=True, editable=False, help_text='Derived FeatureCollection, gzip-compressed, rebuilt from the layer objects on every write. Read and write it through `geojson`.', null=True),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name='surveymaplayer',
            name='geojson',
        ),
    ]
