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


def delete_report(actor, report):
    """Delete a report with its blocks, pictures and stored PDFs. The answers stay."""
    report.delete()


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


def comparable(question, other_survey):
    """The question with `question`'s code in `other_survey` when the two can be compared (both
    charts of the same kind), else None."""
    from data.questions import question_of
    from reports.render import CHART_INPUT_TYPES
    from survey.versioning import canonical_of
    if question is None or other_survey is None or question.input_type not in CHART_INPUT_TYPES:
        return None
    twin = question_of(canonical_of(other_survey), question.code)
    if twin is None or twin.input_type not in CHART_INPUT_TYPES:
        return None
    numeric = ('number', 'range')
    if (question.input_type in numeric) != (twin.input_type in numeric):
        return None
    return twin


def add_compare_block(actor, report, question, other_survey, **values):
    """One question in two rounds: `question` (of a survey of the workspace) beside the question
    with the same code in `other_survey`."""
    from survey.versioning import canonical_of
    if other_survey is None or other_survey.organization_id != report.organization_id:
        raise ReportRefused('no_other', _('Choose the other survey to compare with.'))
    dataset = dataset_for(question) if question is not None else None
    if dataset is None or dataset.organization_id != report.organization_id:
        raise ReportRefused('other_workspace', _('Only a survey of this workspace can be shown.'))
    other = canonical_of(other_survey)
    if other.pk == dataset.survey_id:
        raise ReportRefused('same_survey', _('Choose a different survey: a comparison needs two.'))
    if comparable(question, other) is None:
        raise ReportRefused('no_twin', _('“%(survey)s” has no comparable question with the code %(code)s.')
                            % {'survey': other.name, 'code': question.code})
    order = values.pop('order', None)
    block = ReportBlock.objects.create(
        report=report, block_type='compare', dataset=dataset, question_code=question.code,
        config={'other': str(other.uuid)}, order=_next_order(report) if order is None else order, **values)
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
    elif block.block_type in ('image', 'heading', 'numbers', 'quotes', 'map') and content is not None:
        # A map's content is its description for people who use a screen reader.
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


def set_published(actor, report, publish, ack=False, visibility=None, mode=None):
    """Publish or take down. Publishing a report that shows quotes or marks needs `ack`: the
    author confirmed having read them (`reports.checks`, change reports-review). `visibility` and
    `mode` ('live' | 'frozen') are the publish dialog's two other choices."""
    if publish and not _may_publish(report):
        raise ReportRefused('publish_survey_first', _('Publish the survey before publishing its results.'))
    if publish and not ack:
        from reports.checks import run
        if run(report).needs_ack:
            raise ReportRefused('ack_required', _('Read the quotes and maps listed under “Before you publish” and confirm.'))
    if publish and visibility in VISIBILITIES:
        report.visibility = visibility
    report.is_published = bool(publish)
    report.save(update_fields=['is_published', 'visibility'])
    if publish and mode == 'frozen':
        freeze_report(report)
    elif publish and mode == 'live' and report.mode == 'frozen':
        unfreeze_report(report)
    if publish:
        from survey import product_events as pe
        pe.emit(pe.REPORT_PUBLISHED, getattr(actor, 'user_id', None),
                {'report_id': str(report.pk), 'visibility': report.visibility, 'mode': report.mode})
    return report


def update_settings(actor, report, *, is_published=None, visibility=None, intro_title='', intro_body='',
                    intro_eyebrow=None, embed_hosts=None, tags=None, show_response_count=False, show_participate_cta=False, show_on_thanks=False,
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
    if embed_hosts is not None:
        from reports.embed import clean_hosts
        from survey.embedding import InvalidHost
        try:
            report.embed_allowed_hosts = clean_hosts(embed_hosts)
        except InvalidHost as bad:
            raise ReportRefused('bad_host', _('“%(host)s” is not a site address. Write one per line, like city.example.org.')
                                % {'host': str(bad)})
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
    if tags is not None:
        from data.tags import set_tags
        set_tags(report.organization, report, tags)
    return slug_taken


def pdf_stamp(report):
    """Which state of the report a PDF shows: the snapshot of a frozen report, else "now"."""
    from django.utils import timezone
    if report.mode == 'frozen' and report.frozen_at:
        import hashlib
        raw = '%s|%s' % (report.frozen_at.isoformat(), report.updated_at.isoformat())
        return 'frozen:' + hashlib.sha1(raw.encode()).hexdigest()
    return 'live:%s' % timezone.now().isoformat()


def ready_pdf(report):
    """The stored PDF of a FROZEN report's current snapshot, or None. A live report has none to
    hand out: its numbers have moved since any earlier rendering."""
    if report.mode != 'frozen' or not report.frozen_at:
        return None
    return report.pdfs.filter(kind='pdf', status='done', stamp=pdf_stamp(report)).first()


def request_pdf(actor, report, base_url='', kind='pdf'):
    """The `ReportPdf` to wait for: the stored one of a frozen report, one already on its way, or
    a new row handed to the worker. Never renders in the caller's request. `kind` 'zip' is the
    archive of every block's PNG and CSV (change reports-embed) — the same job, another file."""
    from reports.models import ReportPdf
    from reports.tasks import render_report_pdf
    kind = 'zip' if kind == 'zip' else 'pdf'
    stamp = pdf_stamp(report)
    if report.mode == 'frozen':
        existing = report.pdfs.filter(kind=kind, stamp=stamp, status__in=('queued', 'running', 'done')).first()
        if existing is not None:
            return existing
    job = ReportPdf.objects.create(report=report, kind=kind, stamp=stamp,
                                   requested_by=getattr(actor, 'user', None))
    try:
        render_report_pdf.delay(job.pk, base_url)
    except Exception:  # noqa: BLE001 — no broker (local dev): render here rather than leave it queued
        render_report_pdf(job.pk, base_url)
    # Keep the three newest renderings of a report; older files go with their rows.
    for old in report.pdfs.filter(kind=kind).exclude(pk=job.pk).order_by('-created_at')[3:]:
        if old.file:
            old.file.delete(save=False)
        old.delete()
    return job


def freeze(actor, report):
    return freeze_report(report)


def unfreeze(actor, report):
    return unfreeze_report(report)


__all__ = ['QUESTION_BLOCK_TYPES', 'ReportRefused', 'delete_report', 'add_compare_block', 'comparable', 'add_image_block', 'add_question_block', 'add_story_block',
           'add_text_block', 'add_view_block', 'pdf_stamp', 'ready_pdf', 'request_pdf',
           'create_report', 'delete_block', 'freeze', 'reorder_blocks', 'set_published', 'unfreeze',
           'update_block', 'update_settings']
