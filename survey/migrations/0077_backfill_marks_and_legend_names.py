# Two follow-ups to 0074 seen on production 2026-09-07:
#
# - A `question`-sourced layer created before #160 had never been materialised
#   (that only happened at a respondent's section POST) and read "0 features"
#   next to 28 answers. Backfill every such layer that holds no objects.
# - The Objects questions 0074 created carried the layer's raw name ("Marks:
#   CLICK HERE: …", "existing-dog-bins"). Give the ones the creator has not
#   renamed the default an editor pick produces (layers.default_question_name).
from django.db import migrations


def forwards(apps, schema_editor):
    from survey.layers import backfill_question_layer, default_question_name
    from survey.models import Question, SurveyMapLayer

    for layer in SurveyMapLayer.objects.filter(source='question'):
        if not layer.items.exists():
            backfill_question_layer(layer)

    for question in Question.objects.filter(input_type='layer_objects', layer__isnull=False).select_related('layer'):
        if question.name == question.layer.name:
            question.name = default_question_name(question.layer)[:250]
            question.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0076_share_with_respondents'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
