# Change map-layers-study-area (spec map-layer-placement "Legend-only questions become
# placements"): a layer is on a section's map because a placement covers it, no longer because an
# Objects-on-the-map question binds it. This migration writes, for every canonical survey, one
# placement per layer its map sections' top-level Objects/budget questions bind — scope `all` when
# the layer then covers every map section, else the picked section references — in the layers'
# own `position` order, which is the stacking order the maps drew them in until now. The questions stay: those with sub-questions still ask, legend-only
# ones are hidden by the code and deleted one release later (PR 2, pre-deploy rule).
# Idempotent: an existing placement of a (survey, layer) is left alone.
from django.db import migrations

MAPLESS_LAYOUTS = ('form', 'image')
BINDING_TYPES = ('layer_objects', 'budget')


def _ordered_sections(SurveySection, header_id):
    """The header's sections in survey order (the head, then next_section links), then any left."""
    rows = list(SurveySection.objects.filter(survey_header_id=header_id)
                .order_by('id').values('id', 'code', 'layout', 'is_head', 'next_section_id'))
    by_id = {r['id']: r for r in rows}
    ordered, seen = [], set()
    current = next((r for r in rows if r['is_head']), None)
    while current is not None and current['id'] not in seen:
        ordered.append(current)
        seen.add(current['id'])
        current = by_id.get(current['next_section_id'])
    ordered += [r for r in rows if r['id'] not in seen]
    return rows, ordered


def _refs(rows):
    """{section_id: ref} as survey.section_refs.refs_for computes it (code, `code#n` on repeats)."""
    by_code = {}
    for r in rows:
        by_code.setdefault(r['code'], []).append(r['id'])
    out = {}
    for code, ids in by_code.items():
        for index, pk in enumerate(ids):
            out[pk] = f'{code}#{index}' if len(ids) > 1 else code
    return out


def questions_to_placements(apps, schema_editor):
    SurveyHeader = apps.get_model('survey', 'SurveyHeader')
    SurveySection = apps.get_model('survey', 'SurveySection')
    Question = apps.get_model('survey', 'Question')
    LayerPlacement = apps.get_model('survey', 'LayerPlacement')
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')

    header_ids = set(Question.objects.filter(
        parent_question_id__isnull=True, input_type__in=BINDING_TYPES, layer__isnull=False,
    ).values_list('survey_section__survey_header_id', flat=True))
    owners = {}
    for h in SurveyHeader.objects.filter(pk__in=header_ids).values('id', 'canonical_survey_id', 'published_version_id'):
        owner = h['canonical_survey_id'] or h['published_version_id'] or h['id']
        owners.setdefault(owner, set()).add(h['id'])

    for owner_id in sorted(owners):
        # The canonical survey first, then its draft copy (unpublished legend questions there must
        # not vanish on publish); archived versions only borrow and add nothing.
        headers = [owner_id] + sorted(SurveyHeader.objects.filter(published_version_id=owner_id)
                                      .values_list('id', flat=True))
        canon_rows, _ordered = _ordered_sections(SurveySection, owner_id)
        canon_refs = _refs(canon_rows)
        all_map_refs = {canon_refs[r['id']] for r in canon_rows if r['layout'] not in MAPLESS_LAYOUTS}
        layer_refs, order = {}, []
        for header_id in headers:
            rows, ordered = _ordered_sections(SurveySection, header_id)
            refs = _refs(rows)
            for section in ordered:
                if section['layout'] in MAPLESS_LAYOUTS:
                    continue
                for layer_id in (Question.objects.filter(
                        survey_section_id=section['id'], parent_question_id__isnull=True,
                        input_type__in=BINDING_TYPES, layer__isnull=False)
                        .order_by('order_number', 'id').values_list('layer_id', flat=True)):
                    if layer_id not in layer_refs:
                        layer_refs[layer_id] = set()
                        order.append(layer_id)
                    layer_refs[layer_id].add(refs[section['id']])
        existing = set(LayerPlacement.objects.filter(survey_id=owner_id).values_list('layer_id', flat=True))
        position = len(existing)
        stacking = {pk: (pos, pk) for pk, pos in
                    SurveyMapLayer.objects.filter(pk__in=order).values_list('id', 'position')}
        order = sorted((pk for pk in order if pk in stacking), key=stacking.get)
        for layer_id in order:
            if layer_id in existing:
                continue
            refs = layer_refs[layer_id]
            position += 1
            if all_map_refs and all_map_refs <= refs:
                LayerPlacement.objects.create(survey_id=owner_id, layer_id=layer_id, scope='all',
                                              sections=[], position=position)
            else:
                LayerPlacement.objects.create(survey_id=owner_id, layer_id=layer_id, scope='sections',
                                              sections=sorted(refs), position=position)


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0134_placement_and_study_area'),
    ]

    operations = [
        migrations.RunPython(questions_to_placements, migrations.RunPython.noop),
    ]
