# Change funnel-history-metrics (D4): fill `SurveyHeader.published_at` from the
# audit trail. `AuditLog` has recorded every lifecycle transition since 0035, so
# for a survey published after that the earliest `status_transition` row with
# `new_status == 'published'` IS the publish moment. A survey with no such row
# stays NULL on purpose: readers fall back to `created_at` as a proxy at read
# time, and the column never holds a guess.

from django.db import migrations
from django.db.models import Min


def backfill(apps, schema_editor):
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    AuditLog = apps.get_model('survey', 'AuditLog')

    first_publish = {
        r['survey_uuid']: r['m']
        for r in (AuditLog.objects
                  .filter(action='status_transition', metadata__new_status='published',
                          survey_uuid__isnull=False)
                  .values('survey_uuid')
                  .annotate(m=Min('created_at')))
    }
    if not first_publish:
        return
    rows = SurveyHeader.objects.filter(uuid__in=first_publish, published_at__isnull=True)
    for pk, survey_uuid in rows.values_list('id', 'uuid'):
        # update(), not save(): no signals, and `updated_at` must not move.
        SurveyHeader.objects.filter(pk=pk).update(published_at=first_publish[survey_uuid])


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0094_published_at_metric_snapshot'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
