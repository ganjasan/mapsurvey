# Change layer-memory-diet: the editor listed a layer's property names by parsing
# its whole derived GeoJSON (55 MB of Python objects for an 8.6 MB layer, on every
# editor page render). The names are already on the objects; store them on the
# layer at rebuild time and backfill existing rows from the objects here.
from django.db import migrations, models

RESERVED_PROPS = ('_key', '_title', '_category', '_has_content', '_cover')


def forwards(apps, schema_editor):
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')
    LayerObject = apps.get_model('survey', 'LayerObject')
    for layer_id in SurveyMapLayer.objects.values_list('pk', flat=True):
        names = set()
        for props in LayerObject.objects.filter(layer_id=layer_id).values_list('properties', flat=True):
            if isinstance(props, dict):
                names.update(k for k in props if isinstance(k, str) and k not in RESERVED_PROPS)
        SurveyMapLayer.objects.filter(pk=layer_id).update(property_names=sorted(names))


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0083_comment_survey_anchor'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveymaplayer',
            name='property_names',
            field=models.JSONField(blank=True, default=list, help_text="Sorted union of the objects' property names (reserved `_*` names excluded), stored on every rebuild so the editor never parses the GeoJSON to list them."),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
