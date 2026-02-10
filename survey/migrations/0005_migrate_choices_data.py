"""Data migration: copy OptionGroup/OptionChoice into Question.choices."""
from django.db import migrations


def migrate_question_choices(apps, schema_editor):
    """Copy OptionGroup/OptionChoice data into Question.choices JSONField."""
    Question = apps.get_model('survey', 'Question')
    OptionChoiceTranslation = apps.get_model('survey', 'OptionChoiceTranslation')

    for q in Question.objects.filter(option_group__isnull=False):
        choices = []
        for c in q.option_group.optionchoice_set.all().order_by('code'):
            names = {"default": c.name}
            for t in OptionChoiceTranslation.objects.filter(option_choice=c):
                names[t.language] = t.name
            choices.append({"code": c.code, "name": names})
        q.choices = choices
        q.save(update_fields=['choices'])


def migrate_answer_choices(apps, schema_editor):
    """Copy Answer.choice M2M data into Answer.selected_choices JSONField."""
    Answer = apps.get_model('survey', 'Answer')

    for answer in Answer.objects.all():
        choice_codes = list(answer.choice.values_list('code', flat=True))
        if choice_codes:
            answer.selected_choices = choice_codes
            answer.save(update_fields=['selected_choices'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0004_add_inline_choices_fields'),
    ]

    operations = [
        migrations.RunPython(migrate_question_choices, noop),
        migrations.RunPython(migrate_answer_choices, noop),
    ]
