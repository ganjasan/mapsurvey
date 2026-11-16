"""A report as a file (change reports-story, #704; owner decision 2026-11-16: import and export).

A ZIP holding `report.json` and `images/<n>.<ext>`: the report's settings and its blocks in order.
A report made by hand outside the product is converted to this file and imported; a report made
here leaves as one and comes back into any workspace its member may edit.

`report.json`:
    {"format": 1, "title", "eyebrow", "lead", "visibility", "k", "survey": <uuid | null>,
     "blocks": [{"type", "width", "title", "hidden", + what the type holds}]}
    heading → "text"; text → "html"; image → "image" (path in the ZIP), "caption";
    numbers → "items" [{value, label}], "note"; quotes → "items" [{text, source}];
    chart / map / objects / budget → "survey" (uuid), "question" (code), "viz", "basemap",
    "popup_fields".

An import never publishes: the report arrives unpublished and workspace-only. A question block is
re-bound when the workspace has that survey and question code, and dropped with a line in the
result otherwise. Text goes through the same sanitiser as the editor's.
"""
import io
import json
import os
import zipfile

from django.core.files.base import ContentFile
from django.utils.translation import gettext as _

from reports import story
from reports.models import QUESTION_BLOCK_TYPES, STORY_BLOCK_TYPES, Report, ReportBlock
from reports.render import bump_version, unique_slug

FORMAT = 1
MAX_ZIP_BYTES = 80 * 1024 * 1024
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_BLOCKS = 300
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif')


class ReportFileRefused(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _en(value):
    if isinstance(value, dict):
        return value.get('en') or next(iter(value.values()), '') or ''
    return value or ''


# ── export ────────────────────────────────────────────────────────────────────

def export_report(report):
    """(file name, bytes) of the report's ZIP."""
    from reports.sources import attach_questions
    intro = report.intro or {}
    blocks_out = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        blocks = attach_questions(report.blocks.select_related('dataset__survey'))
        for index, block in enumerate(blocks):
            entry = {'type': block.block_type, 'width': block.width, 'hidden': block.is_hidden,
                     'title': _en(block.custom_title)}
            if block.block_type == 'heading':
                entry['text'] = _en(block.content)
            elif block.block_type == 'text':
                entry['html'] = _en(block.content)
            elif block.block_type == 'image':
                entry['caption'] = _en(block.content)
                if block.image:
                    ext = os.path.splitext(block.image.name)[1].lower() or '.png'
                    path = f'images/{index:03d}{ext}'
                    with block.image.open('rb') as handle:
                        archive.writestr(path, handle.read())
                    entry['image'] = path
            elif block.block_type in ('numbers', 'quotes'):
                entry['items'] = (block.config or {}).get('items') or []
                entry['note'] = _en(block.content)
            elif block.block_type in QUESTION_BLOCK_TYPES:
                survey = block.dataset.survey if block.dataset_id and block.dataset.survey_id else None
                entry.update(survey=str(survey.uuid) if survey is not None else None,
                             question=block.question_code, viz=block.viz, basemap=block.basemap,
                             popup_fields=list(block.geo_label_fields or []))
            blocks_out.append(entry)
        document = {
            'format': FORMAT,
            'title': _en(intro.get('title')), 'eyebrow': _en(intro.get('eyebrow')), 'lead': _en(intro.get('body')),
            'visibility': report.visibility, 'k': report.k_anonymity_threshold,
            'survey': str(report.survey.uuid) if report.survey_id else None,
            'blocks': blocks_out,
        }
        archive.writestr('report.json', json.dumps(document, ensure_ascii=False, indent=1))
    return f'{report.slug}.report.zip', buffer.getvalue()


# ── import ────────────────────────────────────────────────────────────────────

def _read(upload):
    size = getattr(upload, 'size', None)
    if size is not None and size > MAX_ZIP_BYTES:
        raise ReportFileRefused(_('The report file is larger than %(mb)s MB.') % {'mb': MAX_ZIP_BYTES // (1024 * 1024)})
    try:
        archive = zipfile.ZipFile(upload)
    except zipfile.BadZipFile:
        raise ReportFileRefused(_('This is not a report file: a .zip exported from Reports is expected.'))
    try:
        document = json.loads(archive.read('report.json').decode('utf-8'))
    except (KeyError, ValueError, UnicodeDecodeError):
        raise ReportFileRefused(_('This is not a report file: it has no readable report.json.'))
    if not isinstance(document, dict) or document.get('format') != FORMAT \
            or not isinstance(document.get('blocks'), list):
        raise ReportFileRefused(_('This report file was made by a version of Mapsurvey this one cannot read.'))
    if len(document['blocks']) > MAX_BLOCKS:
        raise ReportFileRefused(_('A report holds up to %(n)s blocks.') % {'n': MAX_BLOCKS})
    return archive, document


def _image(archive, path):
    """The bytes and extension of a picture in the ZIP, or None when it cannot be taken."""
    if not isinstance(path, str) or not path.startswith('images/') or '..' in path:
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        return None
    try:
        info = archive.getinfo(path)
    except KeyError:
        return None
    if info.file_size > MAX_IMAGE_BYTES:
        return None
    return archive.read(path), ext


def _surveys(organization, uuids):
    from survey.models import SurveyHeader
    wanted = [u for u in uuids if u]
    return {str(s.uuid): s for s in SurveyHeader.objects.filter(organization=organization, uuid__in=wanted,
                                                               deleted_at__isnull=True)}


def import_report(actor, organization, upload):
    """Create a report of `organization` from a report file. Returns (report, notes): the notes
    name what could not come along. Raises ReportFileRefused for a file that is not one."""
    from django.db import transaction
    from data.questions import question_of
    from reports.render import block_type_for_question
    from reports.sources import dataset_for
    from survey.versioning import canonical_of

    archive, document = _read(upload)
    notes = []
    block_surveys = [b.get('survey') for b in document['blocks'] if isinstance(b, dict)]
    surveys = _surveys(organization, [document.get('survey'), *block_surveys])
    home = surveys.get(str(document.get('survey') or ''))
    title = str(document.get('title') or '')[:200]
    intro = {'title': {'en': title}, 'body': {'en': str(document.get('lead') or '')[:2000]}}
    if document.get('eyebrow'):
        intro['eyebrow'] = {'en': str(document['eyebrow'])[:160]}
    try:
        k = max(1, int(document.get('k') or 3))
    except (TypeError, ValueError):
        k = 3

    with transaction.atomic():
        report = Report.objects.create(
            organization=organization, survey=canonical_of(home) if home is not None else None,
            slug=unique_slug(title or 'report'), intro=intro, visibility='workspace', is_published=False,
            k_anonymity_threshold=k, show_response_count=home is not None,
            show_participate_cta=False, show_on_thanks=False,
            scaffolded_at=None, created_by=actor.user)
        order = 0
        for raw in document['blocks']:
            if not isinstance(raw, dict):
                continue
            block_type = raw.get('type')
            common = dict(report=report, order=order, width=story.clean_width(raw.get('width')),
                          is_hidden=bool(raw.get('hidden')),
                          custom_title={'en': str(raw.get('title'))[:300]} if raw.get('title') else {})
            if block_type == 'heading':
                ReportBlock.objects.create(block_type='heading', content={'en': str(raw.get('text') or '')[:300]}, **common)
            elif block_type == 'text':
                ReportBlock.objects.create(block_type='text', content={'en': story.clean_html(raw.get('html'))}, **common)
            elif block_type in ('numbers', 'quotes'):
                ReportBlock.objects.create(block_type=block_type, config=story.clean_config(block_type, raw),
                                           content={'en': str(raw.get('note') or '')[:2000]}, **common)
            elif block_type == 'image':
                picture = _image(archive, raw.get('image'))
                if picture is None:
                    notes.append(_('A picture could not be read and was left out.'))
                    continue
                data, ext = picture
                block = ReportBlock(block_type='image', content={'en': str(raw.get('caption') or '')[:2000]}, **common)
                block.image.save(f'report-{report.pk}-{order}{ext}', ContentFile(data), save=False)
                block.save()
            elif block_type in QUESTION_BLOCK_TYPES:
                survey = surveys.get(str(raw.get('survey') or ''))
                question = question_of(canonical_of(survey), raw.get('question')) if survey is not None else None
                if question is None or block_type_for_question(question) != block_type:
                    notes.append(_('“%(title)s” shows a survey question this workspace does not have; the block was left out.')
                                 % {'title': raw.get('title') or raw.get('question') or block_type})
                    continue
                ReportBlock.objects.create(
                    block_type=block_type, dataset=dataset_for(question), question_code=question.code,
                    viz=str(raw.get('viz') or 'auto')[:20], basemap=str(raw.get('basemap') or 'streets')[:50],
                    geo_label_fields=[str(c) for c in (raw.get('popup_fields') or [])][:20], **common)
            else:
                continue
            order += 1
        # A scaffold must never add blocks to an imported report.
        from django.utils import timezone
        Report.objects.filter(pk=report.pk).update(scaffolded_at=timezone.now())
        bump_version(report)
    return report, notes


__all__ = ['FORMAT', 'ReportFileRefused', 'STORY_BLOCK_TYPES', 'export_report', 'import_report']
