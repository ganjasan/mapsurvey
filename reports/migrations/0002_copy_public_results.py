"""Every public results page becomes a report (change reports-object, #703).

Rows are copied WITH their primary keys: comment threads anchored to a block, frozen snapshots
(`blocks[].id`) and `?block=<id>` links keep pointing at the same thing. A block's question FK
becomes a dataset of the Data module plus the question's code — a map block reads the `answers`
dataset of (canonical survey, code), every other question block the survey's `responses` dataset.
Registry rows that `data.datasets.sync` has not written yet are created with the values it would
write. `survey/0133` drops the old tables afterwards.
"""
from django.db import migrations

GEO_TYPES = ('point', 'line', 'polygon', 'spraycan')
QUESTION_BLOCK_TYPES = ('chart', 'map', 'objects', 'budget')


def copy_pages(apps, schema_editor):
    Page = apps.get_model('survey', 'PublicResultsPage')
    Block = apps.get_model('survey', 'PublicResultsBlock')
    Question = apps.get_model('survey', 'Question')
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    Dataset = apps.get_model('data', 'Dataset')
    Report = apps.get_model('reports', 'Report')
    ReportBlock = apps.get_model('reports', 'ReportBlock')

    if not Page.objects.exists():
        return

    headers = {h['id']: h for h in SurveyHeader.objects.values(
        'id', 'organization_id', 'canonical_survey_id', 'published_version_id', 'name')}

    def canonical_id(header_id):
        h = headers[header_id]
        return h['canonical_survey_id'] or h['published_version_id'] or header_id

    reports = []
    for p in Page.objects.all().iterator():
        reports.append(Report(
            id=p.id, organization_id=headers[p.survey_id]['organization_id'], survey_id=p.survey_id,
            slug=p.slug, visibility=p.visibility, is_published=p.is_published, intro=p.intro, mode=p.mode,
            snapshot=p.snapshot, snapshot_version=p.snapshot_version, frozen_at=p.frozen_at,
            show_response_count=p.show_response_count, show_participate_cta=p.show_participate_cta,
            show_on_thanks=p.show_on_thanks, feature_in_listing=p.feature_in_listing,
            k_anonymity_threshold=p.k_anonymity_threshold, scaffolded_at=p.scaffolded_at,
            created_at=p.created_at, updated_at=p.updated_at))
    Report.objects.bulk_create(reports, batch_size=200)
    # auto_now_add / auto_now overwrote the dates on insert: `updated_at` is the live-cache stamp
    # and both are what the list shows.
    for p in Page.objects.values('id', 'created_at', 'updated_at').iterator():
        Report.objects.filter(pk=p['id']).update(created_at=p['created_at'], updated_at=p['updated_at'])

    questions = {q['id']: q for q in Question.objects
                 .filter(id__in=Block.objects.exclude(question_id=None).values('question_id'))
                 .values('id', 'code', 'name', 'input_type', 'parent_question_id_id',
                         'survey_section__survey_header_id')}
    datasets = {}

    def dataset_id(question):
        survey_id = canonical_id(question['survey_section__survey_header_id'])
        is_geo = (question['input_type'] in GEO_TYPES and question['parent_question_id_id'] is None
                  and question['code'])
        key = ('answers', survey_id, question['code']) if is_geo else ('responses', survey_id, '')
        if key not in datasets:
            name = (question['name'] or question['code']) if is_geo else headers[survey_id]['name']
            ds, _created = Dataset.objects.get_or_create(
                kind=key[0], survey_id=survey_id, question_code=key[2],
                defaults=dict(organization_id=headers[survey_id]['organization_id'],
                              name=(name or '')[:200], privacy_class='aggregated'))
            datasets[key] = ds.id
        return datasets[key]

    blocks = []
    for b in Block.objects.all().iterator():
        question = questions.get(b.question_id) if b.question_id else None
        reads = question is not None and b.block_type in QUESTION_BLOCK_TYPES
        blocks.append(ReportBlock(
            id=b.id, report_id=b.page_id, block_type=b.block_type,
            dataset_id=dataset_id(question) if reads else None,
            question_code=(question['code'] or '') if reads else '',
            viz=b.viz, custom_title=b.custom_title, content=b.content, image=b.image.name if b.image else '',
            geo_label_fields=b.geo_label_fields, basemap=b.basemap, is_hidden=b.is_hidden, order=b.order))
    ReportBlock.objects.bulk_create(blocks, batch_size=500)

    # Explicit primary keys leave the identity sequences behind.
    with schema_editor.connection.cursor() as cursor:
        for table in ('reports_report', 'reports_reportblock'):
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) "
                "FROM {}".format(table), [table])


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
        ('data', '0007_tags'),
        ('survey', '0130_map_layer_workspace'),
    ]

    operations = [
        # The reverse leaves the copies in place: 0133's reverse recreates the old tables empty,
        # and a real rollback is a database restore (design.md, Migration Plan).
        migrations.RunPython(copy_pages, migrations.RunPython.noop),
    ]
