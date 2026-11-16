"""The dataset registry kept in step with its sources, and what a member may see of it
(change data-catalogue, #667).

`sync(org)` is idempotent and runs when the catalogue opens: a read-time sync cannot miss a write
path (editor, API, MCP, ZIP import, cloning), and a workspace holds tens of datasets.
"""
from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Count, Max

from data.models import Dataset
from data.scope import SessionScope

GEO_TYPES = None  # filled lazily from survey.question_types (import cycle at module load)


def _geo_types():
    global GEO_TYPES
    if GEO_TYPES is None:
        from survey.question_types import GEO_TYPES as types
        GEO_TYPES = tuple(types)
    return GEO_TYPES


def _canonical_surveys(org):
    from survey.models import SurveyHeader
    return list(SurveyHeader.objects.filter(organization=org, is_canonical=True, deleted_at__isnull=True)
                .only('id', 'name', 'uuid', 'organization_id', 'created_by_id'))


def _family_map(org):
    """{header id: canonical id} for every header of the workspace."""
    from survey.models import SurveyHeader
    out = {}
    for hid, is_canonical, canonical_id in (SurveyHeader.objects.filter(organization=org)
                                            .values_list('id', 'is_canonical', 'canonical_survey_id')):
        out[hid] = hid if is_canonical else (canonical_id or hid)
    return out


def _geo_questions(org):
    """{canonical id: {code: name}} of top-level geo questions across each survey's versions;
    the canonical version's name wins, else the newest."""
    from survey.models import Question
    family = _family_map(org)
    names = defaultdict(dict)
    canonical_named = set()
    rows = (Question.objects
            .filter(survey_section__survey_header__organization=org, parent_question_id__isnull=True,
                    input_type__in=_geo_types())
            .exclude(code='')
            .values_list('survey_section__survey_header_id', 'code', 'name')
            .order_by('id'))
    for header_id, code, name in rows:
        canonical = family.get(header_id)
        if canonical is None:
            continue
        if (canonical, code) in canonical_named:
            continue
        names[canonical][code] = name or code
        if header_id == canonical:
            canonical_named.add((canonical, code))
    return names


def sync(org):
    """Create the registry rows the workspace is missing, refresh names, drop rows whose source
    is gone. Returns the workspace's datasets queryset."""
    from survey.models import SurveyMapLayer
    surveys = _canonical_surveys(org)
    survey_ids = {s.id for s in surveys}
    existing = {}
    for ds in Dataset.objects.filter(organization=org):
        key = ('layer', ds.layer_id) if ds.kind in Dataset.LAYER_KINDS else (ds.kind, ds.survey_id, ds.question_code)
        existing[key] = ds

    wanted = {}
    from django.db.models import Q
    for layer in (SurveyMapLayer.objects.filter(Q(survey_id__in=survey_ids)
                                                | Q(survey__isnull=True, organization=org))
                  .only('id', 'name', 'source', 'survey_id')):
        kind = Dataset.KIND_SHARED_MAP if layer.source == 'question' else Dataset.KIND_LAYER
        privacy = Dataset.PRIVACY_AGGREGATED if kind == Dataset.KIND_SHARED_MAP else Dataset.PRIVACY_PUBLIC
        if layer.survey_id is None:
            # A workspace upload keeps the privacy its owner set (uploads start private).
            privacy = existing[('layer', layer.id)].privacy_class if ('layer', layer.id) in existing \
                else Dataset.PRIVACY_PRIVATE
        wanted[('layer', layer.id)] = dict(kind=kind, layer_id=layer.id, survey_id=None, question_code='',
                                           name=layer.name, privacy_class=privacy)
    questions = _geo_questions(org)
    for s in surveys:
        wanted[(Dataset.KIND_RESPONSES, s.id, '')] = dict(
            kind=Dataset.KIND_RESPONSES, layer_id=None, survey_id=s.id, question_code='',
            name=s.name, privacy_class=Dataset.PRIVACY_AGGREGATED)
        for code, qname in questions.get(s.id, {}).items():
            wanted[(Dataset.KIND_ANSWERS, s.id, code)] = dict(
                kind=Dataset.KIND_ANSWERS, layer_id=None, survey_id=s.id, question_code=code,
                name=qname, privacy_class=Dataset.PRIVACY_AGGREGATED)

    create = []
    for key, values in wanted.items():
        ds = existing.get(key)
        if ds is None:
            create.append(Dataset(organization=org, **values))
        elif ds.name != values['name'][:200]:
            Dataset.objects.filter(pk=ds.pk).update(name=values['name'][:200])
    if create:
        for ds in create:
            ds.name = ds.name[:200]
        Dataset.objects.bulk_create(create, ignore_conflicts=True)
    stale = [ds.pk for key, ds in existing.items()
             if key not in wanted and (ds.kind in Dataset.COLLECTED_KINDS or ds.survey_id is None)]
    if stale:
        Dataset.objects.filter(pk__in=stale).delete()
    return Dataset.objects.filter(organization=org)


def visible_survey_ids(org, user):
    """Canonical survey ids the member has a role on (owner/admin/viewer: all)."""
    from survey.models import SurveyCollaborator
    from survey.permissions import get_org_membership
    membership = get_org_membership(user, org)
    if membership is None:
        return set()
    ids = {s.id for s in _canonical_surveys(org)}
    if membership.role in ('owner', 'admin', 'viewer'):
        return ids
    family = _family_map(org)
    collab = {family.get(sid, sid) for sid in
              SurveyCollaborator.objects.filter(user=user, survey__organization=org).values_list('survey_id', flat=True)}
    return ids & collab


@dataclass
class Row:
    dataset: Dataset
    survey: object = None
    rows: int = 0
    used_by: int = 0
    changed: object = None
    link: str = ''
    extra: dict = field(default_factory=dict)


def catalogue_rows(org, user):
    """The datasets the member may see, with their facts (rows, used by, last change, link)."""
    from django.urls import reverse
    from survey.models import (Answer, PublicResultsBlock, Question, SiteBlock, SurveyHeader,
                               SurveyMapLayer)
    from survey.models import LayerObject
    visible = visible_survey_ids(org, user)
    family = _family_map(org)
    # The layer's geometry text never rides along (layer memory rules).
    datasets = list(sync(org).select_related('layer', 'survey').defer('layer__geojson_gz', 'layer__geojson_legacy'))
    surveys = {s.id: s for s in SurveyHeader.objects.filter(id__in=visible).only('id', 'uuid', 'name')}

    # rows and last change of collected kinds, grouped per canonical survey
    header_ids = [h for h, c in family.items() if c in visible]
    responses = defaultdict(int)
    last_seen = {}
    for sid, n, newest in (SessionScope(header_ids, include_moderated=True, nonempty=True).sessions()
                           .values('survey_id').annotate(n=Count('id'), newest=Max('start_datetime'))
                           .values_list('survey_id', 'n', 'newest')):
        c = family.get(sid)
        responses[c] += n
        if newest and (c not in last_seen or newest > last_seen[c]):
            last_seen[c] = newest
    answers = defaultdict(int)
    for hid, code, n in (Answer.objects
                         .filter(question__survey_section__survey_header_id__in=header_ids,
                                 question__parent_question_id__isnull=True,
                                 question__input_type__in=_geo_types())
                         .filter(SessionScope((), include_moderated=True).related_q('survey_session'))
                         .values('question__survey_section__survey_header_id', 'question__code')
                         .annotate(n=Count('id'))
                         .values_list('question__survey_section__survey_header_id', 'question__code', 'n')):
        answers[(family.get(hid), code)] += n

    # used by
    bound = defaultdict(int)
    # Questions on canonical surveys bound to any layer of the workspace — a linked dataset's
    # layer is bound from other surveys too (change data-links).
    for layer_id, n in (Question.objects.filter(layer__isnull=False, layer__organization=org,
                                                survey_section__survey_header__canonical_survey__isnull=True,
                                                survey_section__survey_header__published_version__isnull=True)
                        .values('layer_id').annotate(n=Count('id')).values_list('layer_id', 'n')):
        bound[layer_id] = n
    from data.models import DatasetLink
    links = dict(DatasetLink.objects.filter(dataset__organization=org).values('dataset_id')
                 .annotate(n=Count('id')).values_list('dataset_id', 'n'))
    pr_blocks = defaultdict(int)
    for sid, code in (PublicResultsBlock.objects.filter(page__survey_id__in=visible, question__isnull=False)
                      .values_list('page__survey_id', 'question__code')):
        pr_blocks[(family.get(sid, sid), code)] += 1
    site_blocks = defaultdict(int)
    for sid, data in (SiteBlock.objects.filter(kind='results', site_survey__survey_id__in=visible)
                      .values_list('site_survey__survey_id', 'data')):
        site_blocks[(family.get(sid, sid), (data or {}).get('question_code', ''))] += 1
    shared_from = defaultdict(int)
    for sid, code in (SurveyMapLayer.objects.filter(source='question', survey_id__in=visible)
                      .values_list('survey_id', 'source_question_code')):
        shared_from[(sid, code)] += 1
    shared_rows = dict(LayerObject.objects.filter(layer__source='question', layer__survey_id__in=visible)
                       .filter(SessionScope(()).related_q('source_session'))
                       .values('layer_id').annotate(n=Count('id')).values_list('layer_id', 'n'))

    out = []
    for ds in datasets:
        sid = ds.layer.survey_id if ds.layer_id else ds.survey_id
        workspace_owned = ds.layer_id is not None and sid is None
        if not workspace_owned and sid not in visible:
            continue
        survey = surveys.get(sid)
        row = Row(dataset=ds, survey=survey)
        if workspace_owned:
            row.rows = ds.layer.feature_count
            row.used_by = bound.get(ds.layer_id, 0) + links.get(ds.pk, 0)
            row.changed = ds.layer.updated_at
            row.extra['uploaded'] = True
        elif ds.kind == Dataset.KIND_LAYER:
            row.rows = ds.layer.feature_count
            row.used_by = 1 + bound.get(ds.layer_id, 0) + links.get(ds.pk, 0)
            row.changed = ds.layer.updated_at
            row.link = reverse('editor_survey_settings', args=[survey.uuid]) if survey else ''
        elif ds.kind == Dataset.KIND_SHARED_MAP:
            row.rows = shared_rows.get(ds.layer_id, 0)
            row.used_by = 1 + bound.get(ds.layer_id, 0)
            row.changed = ds.layer.updated_at
            row.link = reverse('editor_survey_settings', args=[survey.uuid]) if survey else ''
        elif ds.kind == Dataset.KIND_ANSWERS:
            key = (sid, ds.question_code)
            row.rows = answers.get(key, 0)
            row.used_by = pr_blocks.get(key, 0) + site_blocks.get(key, 0) + shared_from.get(key, 0)
            row.changed = last_seen.get(sid)
            row.link = reverse('editor_survey_analytics', args=[survey.uuid]) if survey else ''
        else:
            row.rows = responses.get(sid, 0)
            row.used_by = 1 + (1 if any(k[0] == sid for k in pr_blocks) else 0)
            row.changed = last_seen.get(sid)
            row.link = reverse('editor_survey_analytics', args=[survey.uuid]) if survey else ''
        out.append(row)
    return out
