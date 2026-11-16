"""Every write to a report (change reports-object, #703).

The configuration screens call these with an `Actor` and plain values; the REST API and MCP
(#710) will call the same functions. Each refusal is a `ReportRefused` with a stable `code`; the
caller turns it into its own response. A change to blocks or settings bumps the report's version
stamp, which is what makes the live cache and the preview show it at once.
"""
from django.utils.text import slugify
from django.utils.translation import gettext as _

from reports.models import QUESTION_BLOCK_TYPES, Report, ReportBlock
from reports.render import (
    block_type_for_question, bump_version, freeze_report, unfreeze_report, unique_slug,
)
from reports.sources import dataset_for

VISIBILITIES = tuple(v for v, _label in Report._meta.get_field('visibility').choices)


class ReportRefused(Exception):
    def __init__(self, code, message=''):
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def create_report(actor, organization, survey=None, title='', **values):
    """A new, unpublished report of the workspace; `survey` makes it that survey's home report."""
    name = title or (survey.name if survey is not None else '')
    intro = {'title': {'en': title}} if title else {}
    return Report.objects.create(organization=organization, survey=survey, slug=unique_slug(name),
                                 intro=intro, created_by=actor.user, **values)


def _next_order(report):
    return report.blocks.count()


def add_text_block(actor, report):
    block = ReportBlock.objects.create(report=report, block_type='text', order=_next_order(report))
    bump_version(report)
    return block


def add_story_block(actor, report, block_type):
    """An empty heading, text, key-numbers or quotes block at the end of the story."""
    if block_type not in ('heading', 'text', 'numbers', 'quotes'):
        raise ReportRefused('unknown_block', _('Unknown block type.'))
    block = ReportBlock.objects.create(report=report, block_type=block_type, order=_next_order(report))
    bump_version(report)
    return block


def add_image_block(actor, report, image):
    if not image:
        raise ReportRefused('image_required', _('An image file is required.'))
    block = ReportBlock.objects.create(report=report, block_type='image', image=image, order=_next_order(report))
    bump_version(report)
    return block


def add_question_block(actor, report, question, **values):
    """A block about one question: a map for a geo question, a chart, an objects table or a
    budget otherwise. The question must belong to a survey of the report's workspace."""
    block_type = block_type_for_question(question)
    if block_type is None:
        # Text questions are never publishable.
        raise ReportRefused('not_publishable', _('Question type is not available for publication.'))
    dataset = dataset_for(question)
    if dataset.organization_id != report.organization_id:
        raise ReportRefused('other_workspace', _('Only a survey of this workspace can be shown.'))
    order = values.pop('order', None)
    block = ReportBlock.objects.create(
        report=report, block_type=block_type, dataset=dataset, question_code=question.code,
        order=_next_order(report) if order is None else order, **values)
    bump_version(report)
    return block


def add_view_block(actor, report, block_type, survey, rows='', columns=''):
    """A cross-tab or an engagement block of `survey`: the analysis view is made in the Data
    module (`data.services.create_view`, which refuses what the dataset does not allow) and the
    block points at it. The survey must belong to the report's workspace."""
    from data import services as data_services
    from data.models import DatasetView
    from data.responses_views import responses_dataset
    from survey.versioning import canonical_of
    if block_type not in ('crosstab', 'engagement'):
        raise ReportRefused('unknown_block', _('Unknown block type.'))
    survey = canonical_of(survey)
    if survey.organization_id != report.organization_id:
        raise ReportRefused('other_workspace', _('Only a survey of this workspace can be shown.'))
    dataset = responses_dataset(survey)
    config = {'rows': rows, 'columns': columns} if block_type == 'crosstab' else {}
    view = None
    if block_type == 'engagement':
        view = dataset.views.filter(kind=DatasetView.KIND_ENGAGEMENT).order_by('id').first()
    else:
        view = dataset.views.filter(kind=DatasetView.KIND_CROSSTAB, config=config).order_by('id').first()
    if view is None:
        name = ('%s × %s' % (rows, columns)) if block_type == 'crosstab' else str(_('Who took part'))
        try:
            view = data_services.create_view(actor, dataset, name[:120], kind=block_type, config=config)
        except data_services.DataRefused as refusal:
            raise ReportRefused('view_refused', refusal.message)
    block = ReportBlock.objects.create(report=report, block_type=block_type, dataset=dataset, view=view,
                                       order=_next_order(report))
    bump_version(report)
    return block


def update_block(actor, block, *, viz=None, is_hidden=None, custom_title=None, content=None, image=None,
                 geo_label_fields=None, basemap=None, valid_basemaps=(), width=None, items=None,
                 show_marks=None):
    """Update what the block's type allows; None leaves a value as it is. `items` is the list of a
    key-numbers or quotes block ([{value, label}] / [{text, source}])."""
    from reports import story
    if viz is not None:
        block.viz = viz
    if is_hidden is not None:
        block.is_hidden = bool(is_hidden)
    if custom_title is not None:
        block.custom_title = {'en': custom_title}
    if width is not None:
        block.width = story.clean_width(width)
    if block.block_type == 'text' and content is not None:
        block.content = {'en': story.clean_html(content)}
    elif block.block_type in ('image', 'heading', 'numbers', 'quotes') and content is not None:
        block.content = {'en': str(content)[:2000]}
    if block.block_type in ('numbers', 'quotes') and items is not None:
        block.config = story.clean_config(block.block_type, {'items': items})
    if block.block_type == 'image' and image:
        block.image = image
    if block.block_type == 'map':
        if geo_label_fields is not None:
            block.geo_label_fields = list(geo_label_fields)
        if basemap in set(valid_basemaps):
            block.basemap = basemap
        if show_marks is not None:
            block.config = story.clean_config('map', {'marks': bool(show_marks)})
    block.save()
    bump_version(block.report)
    return block


def delete_block(actor, block):
    report = block.report
    block.delete()
    bump_version(report)


def reorder_blocks(actor, report, ids):
    """Number the report's blocks in the order of `ids`; unknown ids are skipped."""
    by_id = {b.id: b for b in report.blocks.all()}
    for index, raw in enumerate(ids):
        try:
            block = by_id.get(int(raw))
        except (TypeError, ValueError):
            continue
        if block is not None and block.order != index:
            block.order = index
            block.save(update_fields=['order'])
    bump_version(report)


def _may_publish(report):
    """A report with a home survey publishes once that survey has left draft."""
    return report.survey_id is None or report.survey.status != 'draft'


def set_published(actor, report, publish):
    if publish and not _may_publish(report):
        raise ReportRefused('publish_survey_first', _('Publish the survey before publishing its results.'))
    report.is_published = bool(publish)
    report.save(update_fields=['is_published'])
    return report


def update_settings(actor, report, *, is_published=None, visibility=None, intro_title='', intro_body='',
                    intro_eyebrow=None, show_response_count=False, show_participate_cta=False, show_on_thanks=False,
                    feature_in_listing=False, k=None, slug=''):
    """Save the report's settings form. Returns True when the requested slug was taken (the
    report then keeps its address). `is_published` None leaves the publication state alone."""
    if is_published is not None:
        if is_published and not _may_publish(report):
            raise ReportRefused('publish_survey_first', _('Publish the survey before publishing its results.'))
        report.is_published = bool(is_published)
    if visibility in VISIBILITIES:
        report.visibility = visibility
    eyebrow = (report.intro or {}).get('eyebrow') if intro_eyebrow is None else {'en': str(intro_eyebrow)[:160]}
    report.intro = {'title': {'en': intro_title or ''}, 'body': {'en': intro_body or ''}}
    if eyebrow:
        report.intro['eyebrow'] = eyebrow
    report.show_response_count = bool(show_response_count)
    report.show_participate_cta = bool(show_participate_cta)
    report.show_on_thanks = bool(show_on_thanks)
    # Only a public report may sit in the stories listing.
    report.feature_in_listing = bool(feature_in_listing)
    try:
        report.k_anonymity_threshold = max(1, int(k if k is not None else 3))
    except (ValueError, TypeError):
        report.k_anonymity_threshold = 3
    slug_taken = False
    new_slug = slugify(slug or report.slug)
    if new_slug and new_slug != report.slug:
        if Report.objects.filter(slug=new_slug).exclude(pk=report.pk).exists():
            slug_taken = True
        else:
            report.slug = new_slug
    report.save()
    return slug_taken


def freeze(actor, report):
    return freeze_report(report)


def unfreeze(actor, report):
    return unfreeze_report(report)


__all__ = ['QUESTION_BLOCK_TYPES', 'ReportRefused', 'add_image_block', 'add_question_block', 'add_story_block',
           'add_text_block', 'add_view_block',
           'create_report', 'delete_block', 'freeze', 'reorder_blocks', 'set_published', 'unfreeze',
           'update_block', 'update_settings']
