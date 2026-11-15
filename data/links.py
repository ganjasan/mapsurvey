"""Datasets linked into surveys and Site map blocks, and who uses a dataset (change data-links, #670).

A link reads the dataset's own objects — nothing is copied — so an edit shows everywhere. The
survey side is resolved by `survey.layers.layers_for`, which adds the layers of the public
datasets linked to the canonical survey. Guards live here so the survey card and the site block
refuse for the same reasons in the same words.
"""
from dataclasses import dataclass

from django.utils.translation import gettext as _

from data.models import Dataset, DatasetLink


# A layer's geometry text never rides a dataset query (layer memory rules, change layer-memory-diet).
_LAYER_TEXT = ('layer__geojson_gz', 'layer__geojson_legacy')


class LinkRefused(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def linkable(dataset):
    """A layer dataset that is not a shared map (those are a survey's own respondents' marks)."""
    return dataset.kind == Dataset.KIND_LAYER and dataset.layer_id is not None


def link_refusal(dataset, survey=None):
    """Why `dataset` cannot be linked (into `survey` when given), or ''."""
    from survey.layers import MAX_LAYER_BYTES, MAX_LAYER_FEATURES, MAX_LAYERS_PER_SURVEY, layer_owner
    if not linkable(dataset):
        return _('Only a layer dataset can be shown on a map.')
    if dataset.privacy_class != Dataset.PRIVACY_PUBLIC:
        return _('This dataset is private. Make it public on its page in Data first.')
    if survey is None:
        return ''
    owner = layer_owner(survey)
    layer = dataset.layer
    if layer.survey_id == owner.pk:
        return _('This layer already belongs to the survey.')
    if layer.feature_count > MAX_LAYER_FEATURES:
        return _('The dataset has %(n)s objects; a survey map takes up to %(max)s.') % {
            'n': layer.feature_count, 'max': MAX_LAYER_FEATURES}
    if layer.size_bytes > MAX_LAYER_BYTES:
        return _('The dataset is larger than %(mb)s MB, the limit for a survey map.') % {
            'mb': MAX_LAYER_BYTES // (1024 * 1024)}
    if owner.map_layers.count() + DatasetLink.objects.filter(survey=owner).count() >= MAX_LAYERS_PER_SURVEY:
        return _('A survey has at most %(n)s reference layers.') % {'n': MAX_LAYERS_PER_SURVEY}
    return ''


def link_survey(dataset, survey, user=None):
    """Link `dataset` into the canonical survey of `survey`; returns the link (an existing one
    is returned as is). Raises LinkRefused."""
    from survey.layers import layer_owner
    owner = layer_owner(survey)
    existing = DatasetLink.objects.filter(dataset=dataset, survey=owner).first()
    if existing is not None:
        return existing
    reason = link_refusal(dataset, owner)
    if reason:
        raise LinkRefused(reason)
    if dataset.organization_id != owner.organization_id:
        raise LinkRefused(_('Only a dataset of this workspace can be linked.'))
    return DatasetLink.objects.create(dataset=dataset, survey=owner, created_by=user)


def bound_questions(layer_id, survey=None):
    """Questions bound to the layer (Objects on the map, budgets), optionally within a survey family."""
    from survey.models import Question
    qs = Question.objects.filter(layer_id=layer_id).select_related('survey_section__survey_header')
    if survey is not None:
        from survey.layers import layer_owner
        owner = layer_owner(survey)
        qs = qs.filter(survey_section__survey_header__in=_family_ids(owner))
    return list(qs)


def _family_ids(owner):
    from django.db.models import Q
    from survey.models import SurveyHeader
    return SurveyHeader.objects.filter(Q(pk=owner.pk) | Q(canonical_survey=owner) | Q(published_version=owner))


def unlink_survey(link):
    """Remove a survey link; refused while a question of that survey is bound to the layer."""
    questions = bound_questions(link.dataset.layer_id, link.survey)
    if questions:
        raise LinkRefused(_('The question “%(name)s” shows this layer. Remove the question or pick another layer first.')
                          % {'name': questions[0].name})
    link.delete()


def sync_site_block(block, dataset_id):
    """Keep a Site map block's link in step with its `dataset` (None = no link)."""
    if not dataset_id:
        DatasetLink.objects.filter(site_block=block).delete()
        return
    link = DatasetLink.objects.filter(site_block=block).first()
    if link is None:
        DatasetLink.objects.create(site_block=block, dataset_id=dataset_id)
    elif link.dataset_id != dataset_id:
        link.dataset_id = dataset_id
        link.save(update_fields=['dataset'])


def site_dataset(org, dataset_id):
    """The workspace's dataset a Site map block may show, or (None, reason)."""
    ds = Dataset.objects.select_related('layer').defer(*_LAYER_TEXT).filter(pk=dataset_id, organization=org).first()
    if ds is None:
        return None, _('Pick a dataset of this workspace.')
    reason = link_refusal(ds)
    return (None, reason) if reason else (ds, '')


def site_choices(org):
    """(dataset, refusal) for every layer dataset of the workspace — the block form's picker."""
    rows = (Dataset.objects.filter(organization=org, kind=Dataset.KIND_LAYER).select_related('layer')
            .defer(*_LAYER_TEXT).order_by('name'))
    return [(ds, link_refusal(ds)) for ds in rows]


def survey_choices(org, survey):
    """(dataset, refusal) for the survey card's "From Data" picker: layer datasets of the
    workspace that the survey neither owns nor links yet."""
    from data.datasets import sync
    from survey.layers import layer_owner
    owner = layer_owner(survey)
    sync(org)
    linked = set(DatasetLink.objects.filter(survey=owner).values_list('dataset_id', flat=True))
    out = []
    for ds in (Dataset.objects.filter(organization=org, kind=Dataset.KIND_LAYER).select_related('layer')
               .defer(*_LAYER_TEXT)
               .order_by('name')):
        if ds.pk in linked or ds.layer.survey_id == owner.pk:
            continue
        out.append((ds, link_refusal(ds, owner)))
    return out


def card_field_names(survey, layer_id):
    """The field names a survey's link shows on the object card, or None (= every public field)."""
    from survey.layers import layer_owner
    names = (DatasetLink.objects.filter(survey=layer_owner(survey), dataset__layer_id=layer_id)
             .values_list('fields', flat=True).first())
    return list(names) if names else None


@dataclass
class Place:
    kind: str      # survey | link | site | question
    label: str
    url: str = ''


def used_by(dataset):
    """Every place that uses a dataset, for the dataset page, the delete page and the catalogue."""
    from django.urls import reverse
    places = []
    if dataset.layer_id:
        layer = dataset.layer
        if layer.survey_id:
            places.append(Place('survey', layer.survey.name, reverse('editor_survey_settings', args=[layer.survey.uuid])))
        for link in dataset.links.select_related('survey', 'site_block__site'):
            if link.survey_id:
                places.append(Place('link', link.survey.name, reverse('editor_survey_settings', args=[link.survey.uuid])))
            else:
                site = link.site_block.site
                places.append(Place('site', site.title or site.slug, reverse('editor_site', args=[site.uuid])))
        for q in bound_questions(dataset.layer_id):
            header = q.survey_section.survey_header
            if header.canonical_survey_id or header.published_version_id:
                continue   # a version's or draft's copy of a canonical question
            places.append(Place('question', f'{q.name} · {header.name}',
                                reverse('editor_survey_detail', args=[header.uuid])))
    return places
