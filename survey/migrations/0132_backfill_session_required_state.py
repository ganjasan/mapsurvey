"""Fill `required_missing` / `required_complete` for every existing non-empty session
(change responses-required-unanswered). Uses the app's own `required_state` with the
current models: a one-off backfill, and the function reads no field added after 0131."""
from django.db import migrations


def backfill(apps, schema_editor):
    from survey.models import SurveySession
    from survey.required_state import refresh_many
    refresh_many(SurveySession.objects.all())


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0131_session_required_state'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
