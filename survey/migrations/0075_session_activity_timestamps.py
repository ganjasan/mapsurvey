# Session timing on the session row (owner decision 2026-09-06): `last_activity_at`
# is written by every section submit and page-leave beacon, `end_datetime` when
# the thanks page is reached. Backfill from the event log where one exists —
# the only trace older sessions left.
from django.db import migrations, models
from django.db.models import Max


def backfill_from_events(apps, schema_editor):
    SurveySession = apps.get_model('survey', 'SurveySession')
    SurveyEvent = apps.get_model('survey', 'SurveyEvent')
    last_seen = dict(
        SurveyEvent.objects.values_list('session_id')
        .annotate(m=Max('created_at')).values_list('session_id', 'm'))
    completed = dict(
        SurveyEvent.objects.filter(event_type='survey_complete')
        .values_list('session_id').annotate(m=Max('created_at')).values_list('session_id', 'm'))
    for session in SurveySession.objects.filter(last_activity_at__isnull=True).only('id', 'end_datetime').iterator():
        seen = last_seen.get(session.id)
        done = completed.get(session.id)
        if seen is None and done is None:
            continue
        fields = {'last_activity_at': seen or done}
        if session.end_datetime is None and done is not None:
            fields['end_datetime'] = done
        SurveySession.objects.filter(pk=session.id).update(**fields)


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0074_layers_by_question'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveysession',
            name='last_activity_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_from_events, migrations.RunPython.noop),
    ]
