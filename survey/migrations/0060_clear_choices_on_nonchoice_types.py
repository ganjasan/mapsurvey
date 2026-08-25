"""Clear stale `choices` on questions whose type does not use them.

Answer storage used to branch on whether `choices` was non-empty, so a leftover
list on e.g. a point question (the editor kept posted choices_json across a
type switch) routed GeoJSON into the choice parser — a 500 on every submit.
The dispatch now keys on input_type, the editor and ZIP import null choices for
non-choice types; this migration repairs the rows that already exist.
"""
from django.db import migrations

# Frozen copy of question_types.CHOICE_TYPES: a migration must not change
# meaning if the constant later does.
CHOICE_TYPES = ("choice", "multichoice", "range", "rating", "ranking")


def clear_stale_choices(apps, schema_editor):
    Question = apps.get_model("survey", "Question")
    Question.objects.exclude(input_type__in=CHOICE_TYPES).exclude(
        choices__isnull=True
    ).update(choices=None)


class Migration(migrations.Migration):

    dependencies = [
        ("survey", "0059_section_next_label"),
    ]

    operations = [
        migrations.RunPython(clear_stale_choices, migrations.RunPython.noop),
    ]
