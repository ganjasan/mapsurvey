# Change map-layers-study-area (spec data-links "A dataset is linked into surveys and sites, not
# copied", owner 2026-11-24: "слои живут в Data"): every uploaded or drawn reference layer becomes a
# workspace dataset that its survey LINKS. Per `upload` layer of a survey, in one transaction:
#   - the layer leaves the survey (`survey=NULL`) and keeps its workspace (`organization`);
#   - its Data registry row exists and is `public` (the survey already showed it to every
#     respondent; a `private` row would drop it from `layers_for`);
#   - one DatasetLink ties it to the canonical survey that owned it.
# Respondents see the same layers: `layers_for` = links + the survey's own `question` layers, and
# the placements of migration 0135 keep pointing at the same layer ids. Layers built from answers
# (`source='question'`) stay owned by their survey. A survey with no workspace keeps its layers.
# Reverse is a no-op on purpose: the pre-change code reads linked public datasets through
# `layers_for` too, so a rolled-back release still shows every layer; moving rows back could not
# tell a migrated layer from a dataset someone linked from Data.
from django.db import migrations, transaction


def layers_to_data(apps, schema_editor):
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    Dataset = apps.get_model('data', 'Dataset')
    DatasetLink = apps.get_model('data', 'DatasetLink')
    rows = list(SurveyMapLayer.objects.filter(survey__isnull=False, source='upload')
                .values('id', 'name', 'survey_id', 'organization_id'))
    headers = {h['id']: h for h in SurveyHeader.objects.filter(pk__in={r['survey_id'] for r in rows})
               .values('id', 'organization_id', 'canonical_survey_id', 'published_version_id')}
    with transaction.atomic():
        for row in rows:
            header = headers.get(row['survey_id']) or {}
            org_id = row['organization_id'] or header.get('organization_id')
            if org_id is None:
                continue
            # layers.layer_owner over historical rows: a link always sits on the canonical survey.
            owner_id = header.get('canonical_survey_id') or header.get('published_version_id') or row['survey_id']
            ds = Dataset.objects.filter(layer_id=row['id'], kind='layer').first()
            if ds is None:
                ds = Dataset.objects.create(organization_id=org_id, kind='layer', layer_id=row['id'],
                                            name=(row['name'] or 'Layer')[:200], privacy_class='public')
            elif ds.privacy_class != 'public':
                Dataset.objects.filter(pk=ds.pk).update(privacy_class='public')
            if not DatasetLink.objects.filter(dataset=ds, survey_id=owner_id).exists():
                DatasetLink.objects.create(dataset=ds, survey_id=owner_id)
            SurveyMapLayer.objects.filter(pk=row['id']).update(survey=None, organization_id=org_id)


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0135_legend_questions_to_placements'),
        ('data', '0009_report_usage_tags'),
    ]

    operations = [
        migrations.RunPython(layers_to_data, migrations.RunPython.noop),
    ]
