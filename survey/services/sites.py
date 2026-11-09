"""The one write path for sites (change sites-service-layer, #617; Sites v1.1 wave B).

Everything that creates, edits, links, publishes or deletes a `Site`, `SiteSurvey`,
`SiteBlock` or `SiteFile` on a creator's behalf lives here, so the builder, the Translations
tab, templates, the future API/MCP tools and the AI wizard cannot drift: block data passes
`sites.clean_block`, uploads are checked by their bytes, a live site is re-screened, the
audit trail is written. The module conventions of `survey/services/` hold: an `Actor` and
plain values in (a block's posted fields arrive as a QueryDict-like `fields` with
`get`/`getlist` — what the panel form posts and what an API body is turned into), refusals
out as `errors.ServiceError` subclasses. Who may act (role) and whether the workspace may
make a NEW Pro use are checked by the caller (`site_views._refusal`), except where the write
itself is the use: creating and duplicating a site count the trial use here.
"""
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from billing import trial as billing_trial

from .. import product_events, sites
from ..audit import record as audit_record
from ..content_screening import screen_site
from ..models import Site, SiteBlock, SiteFile, SiteSurvey, SurveyHeader
from ..versioning import canonical_of
from .errors import ServiceError, ValidationFailed

# The survey-content language list (editor/partials/language_picker.html).
CONTENT_LANGUAGES = (
    'af am ar az be bg bn bs ca cs cy da de el en es et eu fa fi fr ga gl gu he hi hr hu hy id is it ja '
    'ka kk km kn ko ky lo lt lv mk ml mn mr ms my ne nl no pa pl pt ro ru si sk sl sq sr sv sw ta te tg '
    'th tk tl tr uk ur uz vi zh'
).split()


class SitesFeatureRequired(ServiceError):
    """The workspace may not make a new Sites use (no plan, trial used up)."""
    code = 'pro_required'


def touched(site, *, screen=True):
    """After any saved change: bump `updated_at`, and re-screen a live site."""
    Site.objects.filter(pk=site.pk).update(updated_at=timezone.now())
    if screen and site.is_published:
        screen_site(site, trigger='live_edit')


def _errors(fields):
    return ValidationFailed({k: [v] for k, v in fields.items()})


# ─── sites ────────────────────────────────────────────────────────────────────

def create_site(actor, org, *, title='', language='en'):
    """A new draft site. Counts the Sites use (plan or trial) and raises when there is none.
    An empty title gives the placeholder title and address (one-click New site)."""
    given = sites.clean_title(title)
    if not billing_trial.use(org, sites.FEATURE, actor=actor.user):
        raise SitesFeatureRequired()
    site = Site.objects.create(
        organization=org, title=given or _('Untitled site'), created_by=actor.user,
        slug=sites.unique_slug(given or sites.PLACEHOLDER_SLUG),
        language=language if language in CONTENT_LANGUAGES else 'en')
    product_events.emit('site_created', actor.user_id, {'organization_id': org.pk, 'site_id': site.pk})
    audit_record(actor, 'site_create', site_id=site.pk)
    return site


def duplicate_site(actor, site):
    """An unpublished copy to start the next engagement from (change site-duplicate). A new site,
    so it counts a Sites use like `create_site`."""
    org = site.organization
    if not billing_trial.use(org, sites.FEATURE, actor=actor.user):
        raise SitesFeatureRequired()
    title = sites.clean_title(_('%(title)s (copy)') % {'title': site.title})
    copy = sites.duplicate_site(site, actor.user, title)
    product_events.emit('site_created', actor.user_id,
                        {'organization_id': org.pk, 'site_id': copy.pk, 'from_site_id': site.pk})
    audit_record(actor, 'site_duplicate', site_id=copy.pk, from_site_id=site.pk)
    return copy


SETTINGS_FIELDS = ('title', 'summary', 'cover_alt', 'slug', 'language', 'visibility', 'width')


def update_settings(actor, site, values, *, cover=None, remove_cover=False):
    """Site settings. Keys absent from `values` keep their value (the canvas autosaves the title
    and summary, the panel the rest, the publish popover only the visibility). While the address
    is the placeholder, it follows the first real title."""
    errors = {}
    title = sites.clean_title(values['title']) if 'title' in values else site.title
    if not title:
        errors['title'] = _('Give the site a title.')
    slug = (values.get('slug') or '').strip().lower() if 'slug' in values else site.slug
    if ('slug' not in values or slug == site.slug) and title != site.title and sites.has_placeholder_slug(site):
        slug = sites.unique_slug(title)
    slug_error = sites.slug_error(slug, site) if slug != site.slug else ''
    if slug_error:
        errors['slug'] = slug_error
    cover_error = sites.check_image(cover)
    if cover_error:
        errors['cover'] = cover_error
    if errors:
        raise _errors(errors)
    language = values.get('language') or site.language
    visibility = values.get('visibility')
    width = values.get('width')
    site.title = title
    if 'summary' in values:
        site.summary = ' '.join(str(values['summary']).split())[:sites.SUMMARY_MAX]
    if 'cover_alt' in values:
        site.cover_alt = ' '.join(str(values['cover_alt']).split())[:200]
    site.slug = slug
    site.language = language if language in CONTENT_LANGUAGES else site.language
    site.visibility = visibility if visibility in ('public', 'unlisted') else site.visibility
    site.width = width if width in sites.SITE_WIDTHS else site.width
    if cover is not None:
        site.cover = cover
    elif remove_cover:
        site.cover = None
    site.save()
    touched(site)
    return site


def publish(actor, site):
    first = site.published_at is None
    site.is_published = True
    site.published_at = site.published_at or timezone.now()
    site.save(update_fields=['is_published', 'published_at', 'updated_at'])
    screen_site(site, trigger='publish')
    product_events.emit('site_published', actor.user_id, {
        'organization_id': site.organization_id, 'site_id': site.pk, 'first': first,
        'blocks': site.blocks.count(), 'surveys': site.survey_links.count(), 'visibility': site.visibility})
    audit_record(actor, 'site_publish', site_id=site.pk)
    return site


def unpublish(actor, site):
    """Always allowed to a member who acts — a lapsed workspace can still take its page down."""
    Site.objects.filter(pk=site.pk).update(is_published=False, updated_at=timezone.now())
    site.is_published = False
    audit_record(actor, 'site_unpublish', site_id=site.pk)
    return site


def delete_site(actor, site):
    pk, title = site.pk, site.title
    site.delete()
    audit_record(actor, 'site_delete', site_id=pk, title=title)


def new_review_link(actor, site):
    """A new review link; every link handed out before stops working (change site-review-link)."""
    sites.rotate_review_salt(site)
    audit_record(actor, 'site_review_link', site_id=site.pk)
    return sites.review_token(site)


# ─── linked surveys ───────────────────────────────────────────────────────────

def link_survey(actor, site, survey, *, touch=True):
    """Link the canonical of `survey` (same workspace, linkable) and return the row, or None."""
    canonical = canonical_of(survey)
    if canonical.organization_id != site.organization_id:
        return None
    if not sites.linkable_surveys(site.organization).filter(pk=canonical.pk).exists():
        return None
    link, _created = SiteSurvey.objects.get_or_create(
        site=site, survey=canonical, defaults={'order': site.survey_links.count()})
    if touch:
        touched(site)
    return link


def unlink_survey(actor, site, link):
    """Unlinking removes the survey's cards too (CASCADE); always allowed — it only removes content."""
    link.delete()
    sites.renumber(list(site.blocks.order_by('order', 'id')))
    touched(site)


# ─── blocks ───────────────────────────────────────────────────────────────────

RAW_KEYS = ('body', 'alt', 'caption', 'label', 'url', 'style', 'size', 'button_label', 'description',
            'current', 'color', 'basemap', 'wide', 'viz', 'date', 'start', 'end', 'tz', 'place',
            'place_url', 'capacity', 'open', 'address', 'hours')

# Error key → the posted fields it is about (an error on a field left empty waits under autosave).
_ERROR_FIELDS = {'question': ('results_question',), 'area': ('geojson_file',), 'people': ('person_email',),
                 'image': ('image',), 'files': ('files',)}


def raw_block(kind, fields):
    """The posted fields of a block form as the dict `clean_block` reads."""
    raw = {key: fields.get(key, '') for key in RAW_KEYS}
    if kind == 'faq':
        raw['items'] = [{'q': q, 'a': a} for q, a in zip(fields.getlist('q'), fields.getlist('a'))]
    elif kind == 'contacts':
        raw['people'] = [{'name': n, 'role': r, 'email': e, 'phone': p} for n, r, e, p in
                         zip(fields.getlist('person_name'), fields.getlist('person_role'),
                             fields.getlist('person_email'), fields.getlist('person_phone'))]
    elif kind == 'timeline':
        raw['items'] = [{'title': t, 'when': w, 'body': b} for t, w, b in
                        zip(fields.getlist('phase_title'), fields.getlist('phase_when'), fields.getlist('phase_body'))]
    return raw


class BlockRefused(ValidationFailed):
    """A refused block save: `fields` as `ValidationFailed`, plus `errors` ({field: message}) and
    `raw` — what was posted, so the editor re-renders the creator's typing, not the stored block."""

    def __init__(self, errors, raw):
        ValidationFailed.__init__(self, {k: [v] for k, v in errors.items()})
        self.errors = errors
        self.raw = raw


def _document_changes(fields, files, block):
    errors = {}
    existing = list(block.files.all()) if block is not None else []
    renames, removals = {}, []
    for f in existing:
        if fields.get(f'remove_{f.pk}') == '1':
            removals.append(f)
            continue
        title = ' '.join((fields.get(f'file_title_{f.pk}') or '').split())[:200]
        if title and title != f.title:
            renames[f] = title
    uploads = files.getlist('files')
    problems = [msg for msg in (sites.check_document(u) for u in uploads) if msg]
    if problems:
        errors['files'] = ' '.join(problems)
    kept = len(existing) - len(removals)
    if not problems and kept + len(uploads) == 0:
        errors['files'] = _('Add at least one file.')
    elif kept + len(uploads) > sites.DOCUMENTS_MAX:
        errors['files'] = _('A documents block holds at most 20 files.')
    return renames, removals, uploads, errors


def _results_target(actor, site, value):
    """(link, question code, result kind) from the picker's '<survey uuid>:<code>', linking the
    survey when it is one of the workspace's; (None, '', '') for anything else."""
    from ..public_results import block_type_for_question
    uuid_part, _sep, code = value.partition(':')
    survey = SurveyHeader.objects.filter(uuid=uuid_part).first() if uuid_part and code else None
    if survey is None:
        return None, '', ''
    survey = canonical_of(survey)
    question = sites.results_question(survey, code)
    if question is None:
        return None, '', ''
    link = link_survey(actor, site, survey, touch=False)
    if link is None:
        return None, '', ''
    return link, code, block_type_for_question(question)


def _posted(fields, files, raw, key):
    for name in _ERROR_FIELDS.get(key, (key,)):
        if any(str(v).strip() for v in fields.getlist(name)) or files.getlist(name):
            return True
        value = raw.get(name)
        if isinstance(value, str) and value.strip():
            return True
    return False


class _NoFiles:
    def get(self, name, default=None):
        return default

    def getlist(self, name):
        return []


def save_block(actor, site, block, kind, fields, files=None, *, creating=False, lenient=False):
    """Validate a block's posted fields and save it; returns the block or raises `BlockRefused`.
    `creating` is the block library adding an EMPTY block (nothing required yet; the public page
    skips it until it is complete). `lenient` is the canvas autosave: an EMPTY field is not an
    error yet, a wrong value still is; a FAQ or timeline row without its question or title is
    kept and not drawn."""
    files = files if files is not None else _NoFiles()
    raw = raw_block(kind, fields)
    map_upload = files.get('geojson_file') if kind == 'map' else None
    map_error = ''
    if kind == 'map':
        if map_upload is not None:
            raw['area'], map_error = sites.parse_geojson(map_upload)
        elif block is not None:
            raw['area'] = block.data.get('area')
    results_link = None
    if kind == 'results':
        results_link, raw['question_code'], raw['result_kind'] = _results_target(
            actor, site, fields.get('results_question') or '')
    data, errors = sites.clean_block(kind, raw, org=site.organization, creating=creating)
    if map_error:
        errors['area'] = map_error
    renames, removals, uploads = {}, [], []
    if kind == 'documents' and not creating:
        renames, removals, uploads, doc_errors = _document_changes(fields, files, block)
        # An autosave may leave the block without files for a moment (remove, then add).
        if lenient and doc_errors.get('files') == _('Add at least one file.'):
            doc_errors.pop('files')
        errors.update(doc_errors)
    upload = files.get('image')
    image_error = sites.check_image(upload)
    if image_error:
        errors['image'] = image_error
    if kind == 'image' and upload is None and not (block and block.image) and not creating:
        errors['image'] = _('Choose a picture.')
    link = None
    if kind == 'survey':
        uuid = (fields.get('survey') or '').strip()
        survey = SurveyHeader.objects.filter(uuid=uuid).first() if uuid else None
        if survey is not None:
            link = link_survey(actor, site, survey, touch=False)
        if link is None and not creating:
            errors['survey'] = _('Pick one of this workspace’s surveys.')
    if errors and lenient:
        errors = {k: v for k, v in errors.items() if k != 'items' and _posted(fields, files, raw, k)}
    if errors:
        raise BlockRefused(errors, raw)
    with transaction.atomic():
        if block is None:
            block = SiteBlock(site=site, kind=kind, order=sites.next_order(site))
        block.title = sites.clean_title(fields.get('title'))
        if 'menu' in fields:  # the panel posts 0 then, when ticked, 1 (the last one wins)
            block.in_menu = fields.get('menu') == '1'
        block.data = data
        if kind == 'image' and upload is not None:
            block.image = upload
        if kind == 'survey':
            block.site_survey = link
        if kind == 'results':
            block.site_survey = results_link
        block.save()
        for f, title in renames.items():
            f.title = title
            f.save(update_fields=['title'])
        for f in removals:
            name = f.file.name
            f.delete()
            # A duplicated documents block shares the stored file; delete it with the last row.
            if not SiteFile.objects.filter(file=name).exists():
                f.file.storage.delete(name)
        last = block.files.order_by('-order').values_list('order', flat=True).first()
        nxt = 0 if last is None else last + 1
        for i, up in enumerate(uploads):
            SiteFile.objects.create(block=block, file=up, title=sites.document_title(up.name),
                                    size=up.size, content_type=(up.content_type or '')[:100], order=nxt + i)
    touched(site)
    return block


def move_after(site, block, after_id):
    """Put `block` right after the block `after_id` (None = first)."""
    rows = [b for b in site.blocks.order_by('order', 'id') if b.pk != block.pk]
    at = 0 if after_id is None else next((i + 1 for i, b in enumerate(rows) if b.pk == after_id), len(rows))
    rows.insert(at, block)
    sites.renumber(rows)


def duplicate_block(actor, site, block):
    """A copy right under the block: kind, heading, menu flag, data, picture, survey link and files
    (stored files shared; event registrations never copied)."""
    with transaction.atomic():
        copy = SiteBlock.objects.create(
            site=site, kind=block.kind, title=block.title, in_menu=block.in_menu, data=dict(block.data or {}),
            translations=_without_files(block.translations), image=block.image.name if block.image else None,
            site_survey=block.site_survey, order=sites.next_order(site))
        for f in block.files.all():
            SiteFile.objects.create(block=copy, file=f.file.name, title=f.title, size=f.size,
                                    content_type=f.content_type, order=f.order)
        move_after(site, copy, block.pk)
    touched(site)
    return copy


def _without_files(translations):
    """Block translations without the `file:<pk>` titles — a copied file has a new pk."""
    return {lang: {k: v for k, v in (row or {}).items() if not k.startswith('file:')}
            for lang, row in (translations or {}).items()}


def delete_block(actor, site, block):
    """Always allowed — it only removes content. A stored file goes with its last row."""
    names = [f.file.name for f in block.files.all()]
    block.delete()
    for name in names:
        if not SiteFile.objects.filter(file=name).exists():
            default_storage.delete(name)
    sites.renumber(list(site.blocks.order_by('order', 'id')))
    touched(site)


def reorder_blocks(actor, site, order):
    """`order` lists every block id of this site once; anything else is refused."""
    blocks = {b.pk: b for b in site.blocks.all()}
    if sorted(order) != sorted(blocks):
        raise ValidationFailed.single('order', 'order must list every block of this site once')
    sites.renumber([blocks[pk] for pk in order])
    touched(site)


def remove_registrations(actor, block, registration_id=None):
    """The workspace removes one registration of an event block, or all of them (None). No Pro
    needed: removing personal data is always allowed."""
    rows = block.registrations.all()
    if registration_id is not None:
        rows = rows.filter(pk=registration_id if str(registration_id).isdigit() else 0)
    count = rows.count()
    rows.delete()
    audit_record(actor, 'site_registrations_remove', site_id=block.site_id, block_id=block.pk, count=count)


# ─── translations (change site-translations, #618) ───────────────────────────

def _clean_translation(kind, cap, text):
    from ..html_sanitize import coerce_creator_html
    from ..translation_table import RICH
    text = (text or '').strip()
    if not text:
        return ''
    if kind == RICH:
        return coerce_creator_html(text)
    text = ' '.join(text.split())
    return text[:cap] if cap else text


def set_translations(actor, site, language, items):
    """Write translations for `language`: `items = [(entity kind, entity, field, text)]` with
    entity kind `site` or `block`. Rich fields pass `coerce_creator_html`, plain ones are trimmed
    and capped; an empty text removes the translation. Every written field records the hash of
    its source text, so the Translations tab can call it outdated when the source changes."""
    from .. import site_translations as st
    from ..translation_table import source_hash
    if language not in st.languages(site)[1:]:
        raise ValidationFailed.single('language', _('This site is not offered in that language.'))
    hashes = dict(site.translation_sources or {})
    lang_hashes = dict(hashes.get(language) or {})
    site_tr = dict(site.translations or {})
    blocks = {}
    for entity_kind, entity, fld, text in items:
        if entity_kind == 'site':
            spec = next(((k, c) for n, k, c in st.SITE_FIELDS if n == fld), None)
            if spec is None:
                continue
            value = _clean_translation(spec[0], spec[1], text)
            row = dict(site_tr.get(language) or {})
            if value:
                row[fld] = value
            else:
                row.pop(fld, None)
            site_tr[language] = row
            key, source, kind = f'site:{fld}', getattr(site, fld) or '', spec[0]
        else:
            block = blocks.setdefault(entity.pk, entity)
            spec = st.field_spec(block, fld)
            if spec is None:
                continue
            value = _clean_translation(spec[0], spec[1], text)
            tr = dict(block.translations or {})
            row = dict(tr.get(language) or {})
            if value:
                row[fld] = value
            else:
                row.pop(fld, None)
            tr[language] = row
            block.translations = tr
            key = f'block:{block.pk}:{fld}'
            source = next(src for n, _k, _c, src in st.block_fields(block) if n == fld)
            kind = spec[0]
        if value:
            lang_hashes[key] = source_hash(source, kind)
        else:
            lang_hashes.pop(key, None)
    hashes[language] = lang_hashes
    with transaction.atomic():
        Site.objects.filter(pk=site.pk).update(translations=site_tr, translation_sources=hashes)
        site.translations, site.translation_sources = site_tr, hashes
        for block in blocks.values():
            SiteBlock.objects.filter(pk=block.pk).update(translations=block.translations)
    touched(site)
    audit_record(actor, 'site_translations', site_id=site.pk, language=language, count=len(items))


def add_language(actor, site, code):
    from .. import site_translations as st
    code = (code or '').strip().lower()
    if code not in CONTENT_LANGUAGES:
        raise ValidationFailed.single('language', _('Pick a language from the list.'))
    if code in st.languages(site):
        return site
    site.languages = list(site.languages or []) + [code]
    site.save(update_fields=['languages', 'updated_at'])
    audit_record(actor, 'site_language_add', site_id=site.pk, language=code)
    return site


def remove_language(actor, site, code):
    """Stop offering a language; its translations stay stored (adding it back restores them)."""
    if code not in (site.languages or []):
        return site
    site.languages = [c for c in site.languages if c != code]
    site.save(update_fields=['languages', 'updated_at'])
    audit_record(actor, 'site_language_remove', site_id=site.pk, language=code)
    return site
