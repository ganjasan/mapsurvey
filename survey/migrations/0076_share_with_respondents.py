# What other respondents see of the answers about an object is a property of
# the sub-question that collects them, not of the layer's source (owner
# decision 2026-09-07, layers-by-question/mockups/journey.md). The layer flags
# `show_tallies` / `show_comments` seeded the new field and are dropped one
# release later together with `hidden_layers`.
from django.db import migrations, models


def seed_from_layer_flags(apps, schema_editor):
    Question = apps.get_model('survey', 'Question')
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')
    for layer in SurveyMapLayer.objects.filter(source='question'):
        subs = Question.objects.filter(parent_question_id__layer=layer,
                                       parent_question_id__input_type='layer_objects')
        if layer.show_tallies:
            subs.filter(input_type='thumbs').update(share_with_respondents=True)
        if layer.show_comments:
            subs.filter(input_type__in=('text', 'text_line')).update(share_with_respondents=True)


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0075_session_activity_timestamps'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='share_with_respondents',
            field=models.BooleanField(default=False, help_text='Sub-questions of an Objects-on-the-map question: other respondents see the answers on the object (👍/👎 counts, comments).'),
        ),
        migrations.RunPython(seed_from_layer_flags, migrations.RunPython.noop),
    ]
