# Change layers-by-question (owner decision 2026-09-06): a layer is on a
# section's map because an Objects-on-the-map question of that section shows
# it — the per-section `hidden_layers` checklist goes away. This migration adds
# `Question.panel_mode` and converts every (map section × layer the checklist
# left visible) into a display-only Objects question in `legend` mode, so no
# published map changes on deploy. `SurveySection.hidden_layers` is dropped by
# a later migration, one release after this one (pre-deploy rule).
import random

from django.db import migrations, models
from django.db.models import Max


def _code_generator(Question):
    def generate():
        while True:
            code = "Q_" + str(random.random())[2:12]
            if not Question.objects.filter(code=code).exists():
                return code
    return generate


def hidden_layers_to_questions(apps, schema_editor):
    SurveySection = apps.get_model('survey', 'SurveySection')
    Question = apps.get_model('survey', 'Question')
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')
    new_code = _code_generator(Question)

    sections = (SurveySection.objects
                .filter(layout='map')
                .select_related('survey_header')
                .order_by('id'))
    for section in sections:
        header = section.survey_header
        # layers.layer_owner(), over historical models: layers belong to the
        # canonical survey; versions and draft copies borrow them.
        owner_id = header.canonical_survey_id or header.published_version_id or header.id
        hidden = {i for i in (section.hidden_layers or []) if isinstance(i, int)}
        bound = set(Question.objects.filter(
            survey_section=section, parent_question_id__isnull=True,
            input_type='layer_objects', layer__isnull=False,
        ).values_list('layer_id', flat=True))
        max_order = Question.objects.filter(
            survey_section=section, parent_question_id__isnull=True,
        ).aggregate(m=Max('order_number'))['m'] or 0
        for layer in SurveyMapLayer.objects.filter(survey_id=owner_id).order_by('position', 'id'):
            if layer.id in hidden or layer.id in bound:
                continue
            max_order += 1
            Question.objects.create(
                survey_section=section, code=new_code(), name=(layer.name or '')[:250],
                input_type='layer_objects', layer=layer, required=False,
                min_objects=0, objects_search='auto', panel_mode='legend',
                order_number=max_order, choices=None,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0073_layer_style'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='panel_mode',
            field=models.CharField(
                choices=[('list', 'List the objects'), ('legend', 'Legend line only')],
                default='list',
                help_text='`layer_objects` only: list the objects in the panel, or show one legend line.',
                max_length=6,
            ),
        ),
        migrations.RunPython(hidden_layers_to_questions, migrations.RunPython.noop),
    ]
