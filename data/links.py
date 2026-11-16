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


def link_refusal(dataset, survey=None, view=None):
    """Why `dataset` (or its `view`) cannot be linked (into `survey` when given), or ''."""
    from survey.layers import MAX_LAYER_BYTES, MAX_LAYER_FEATURES, MAX_LAYERS_PER_SURVEY, layer_owner
    if view is not None and view.dataset_id != dataset.pk:
        return _('Pick a view of this dataset.')
    if view is not None and view.kind == 'grid':
        # Aggregated data leaves only as a grid of counts (change data-views): a Site block may
        # show it; a survey's reference layer is objects respondents open, never counts.
        return _('A grid of counts can be shown on a site, not as a survey layer.') if survey is not None else ''
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


def link_survey(dataset, survey, user=None, view=None):
    """Link `dataset` (or one of its views) into the canonical survey of `survey`; returns the
    link (an existing link of the dataset is returned as is). Raises LinkRefused."""
    from survey.layers import layer_owner
    owner = layer_owner(survey)
    existing = DatasetLink.objects.filter(dataset=dataset, survey=owner).first()
    if existing is not None:
        return existing
    reason = link_refusal(dataset, owner, view)
    if reason:
        raise LinkRefused(reason)
    if dataset.organization_id != owner.organization_id:
        raise LinkRefused(_('Only a dataset of this workspace can be linked.'))
    return DatasetLink.objects.create(dataset=dataset, survey=owner, view=view, created_by=user)


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


def sync_site_block(block, dataset_id, view_id=None):
    """Keep a Site map block's link in step with its `dataset` / `view` (None = no link)."""
    if not dataset_id:
        DatasetLink.objects.filter(site_block=block).delete()
        return
    link = DatasetLink.objects.filter(site_block=block).first()
    if link is None:
        DatasetLink.objects.create(site_block=block, dataset_id=dataset_id, view_id=view_id)
    elif (link.dataset_id, link.view_id) != (dataset_id, view_id):
        link.dataset_id, link.view_id = dataset_id, view_id
        link.save(update_fields=['dataset', 'view'])


def site_dataset(org, dataset_id, view_id=None):
    """(dataset, view, reason) a Site map block may show; dataset None when refused."""
    from data.models import DatasetView
    ds = (Dataset.objects.select_related('layer', 'survey').defer(*_LAYER_TEXT)
          .filter(pk=dataset_id, organization=org).first())
    if ds is None:
        return None, None, _('Pick a dataset of this workspace.')
    view = DatasetView.objects.filter(pk=view_id, dataset=ds).first() if view_id else None
    if view_id and view is None:
        return None, None, _('Pick a view of this dataset.')
    reason = link_refusal(ds, view=view)
    return (None, None, reason) if reason else (ds, view, '')


def _choices_with_views(datasets, refusal):
    """[(value, label, refusal)] — each dataset, then each of its views as "dataset › view"."""
    from data.models import DatasetView
    views = {}
    for v in DatasetView.objects.filter(dataset__in=[d.pk for d in datasets]).order_by('name'):
        views.setdefault(v.dataset_id, []).append(v)
    out = []
    for ds in datasets:
        if ds.kind == Dataset.KIND_LAYER:
            out.append((str(ds.pk), ds.name, refusal(ds, None)))
        for v in views.get(ds.pk, []):
            out.append((f'{ds.pk}:{v.pk}', f'{ds.name} › {v.name}', refusal(ds, v)))
    return out


def parse_choice(value):
    """'12' → (12, None); '12:5' → (12, 5); anything else → (None, None)."""
    parts = str(value or '').split(':')
    if not all(p.isdigit() for p in parts) or len(parts) > 2:
        return None, None
    return int(parts[0]), (int(parts[1]) if len(parts) == 2 else None)


def site_choices(org):
    """[(value, label, refusal)] for the Site map block: layer datasets and every view."""
    rows = list(Dataset.objects.filter(organization=org, kind__in=(Dataset.KIND_LAYER, Dataset.KIND_ANSWERS))
                .select_related('layer').defer(*_LAYER_TEXT).order_by('name'))
    return _choices_with_views(rows, lambda ds, v: link_refusal(ds, view=v))


def survey_choices(org, survey):
    """(dataset, refusal) for the survey card's "From Data" picker: layer datasets of the
    workspace that the survey neither owns nor links yet."""
    from data.datasets import sync
    from survey.layers import layer_owner
    owner = layer_owner(survey)
    sync(org)
    linked = set(DatasetLink.objects.filter(survey=owner).values_list('dataset_id', flat=True))
    rows = [ds for ds in (Dataset.objects.filter(organization=org, kind=Dataset.KIND_LAYER).select_related('layer')
                          .defer(*_LAYER_TEXT).order_by('name'))
            if ds.pk not in linked and ds.layer.survey_id != owner.pk]
    return _choices_with_views(rows, lambda ds, v: link_refusal(ds, owner, v))


def card_field_names(survey, layer_id):
    """The field names a survey's link shows on the object card, or None (= every public field)."""
    from survey.layers import layer_owner
    link = (DatasetLink.objects.filter(survey=layer_owner(survey), dataset__layer_id=layer_id)
            .select_related('view').first())
    if link is None:
        return None
    if link.fields:
        return list(link.fields)
    if link.view is not None and link.view.fields:
        return list(link.view.fields)
    return None


def survey_view(survey, layer_id):
    """The view a survey shows of a linked layer, or None (the whole dataset / an own layer)."""
    from survey.layers import layer_owner
    link = (DatasetLink.objects.filter(survey=layer_owner(survey), dataset__layer_id=layer_id, view__isnull=False)
            .select_related('view__dataset__layer').first())
    return link.view if link else None


@dataclass
class Place:
    kind: str      # survey | link | site | question | report
    label: str
    url: str = ''


def used_by(dataset):
    """Every place that uses a dataset, for the dataset page, the delete page and the catalogue."""
    from django.urls import reverse
    places = []
    if dataset.layer_id and dataset.layer.survey_id:
        layer = dataset.layer
        places.append(Place('survey', layer.survey.name, reverse('editor_survey_settings', args=[layer.survey.uuid])))
    for link in dataset.links.select_related('survey', 'site_block__site', 'view'):
        suffix = f' › {link.view.name}' if link.view_id else ''
        if link.survey_id:
            places.append(Place('link', link.survey.name + suffix,
                                reverse('editor_survey_settings', args=[link.survey.uuid])))
        else:
            site = link.site_block.site
            places.append(Place('site', (site.title or site.slug) + suffix, reverse('editor_site', args=[site.uuid])))
    if dataset.layer_id:
        for q in bound_questions(dataset.layer_id):
            header = q.survey_section.survey_header
            if header.canonical_survey_id or header.published_version_id:
                continue   # a version's or draft's copy of a canonical question
            places.append(Place('question', f'{q.name} · {header.name}',
                                reverse('editor_survey_detail', args=[header.uuid])))
    places.extend(report_places(dataset=dataset))
    return places


def report_places(dataset=None, view=None):
    """The reports whose blocks read a dataset (or show a view), one place per report
    (change reports-object)."""
    from django.urls import reverse
    from reports.models import ReportBlock
    blocks = ReportBlock.objects.select_related('report__survey')
    blocks = blocks.filter(view=view) if view is not None else blocks.filter(dataset=dataset)
    places, seen = [], set()
    for block in blocks.order_by('report_id', 'order'):
        report = block.report
        if report.pk in seen:
            continue
        seen.add(report.pk)
        url = (reverse('editor_survey_public_results', args=[report.survey.uuid]) if report.survey_id
               else reverse('editor_reports'))
        places.append(Place('report', report.title, url))
    return places
